from datetime import datetime, timedelta
import os
import re
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from tqdm import tqdm
from loguru import logger

load_dotenv(override=True)

# ----------------------------------------------------------------------
# ⚙️ Initialization
# ----------------------------------------------------------------------
TOKEN = os.getenv("SLACK_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Missing SLACK_BOT_TOKEN in environment (.env)")

client = WebClient(token=TOKEN)


# ==============================================================
# 🧭 Helper — parse flexible duration (e.g. 2d, 24h, 3M, 1w)
# ==============================================================
def parse_duration_to_timedelta(value: str) -> timedelta:
    if not value:
        return timedelta(days=7)
    value = value.strip().lower()
    num = int(''.join([c for c in value if c.isdigit()]))
    unit = ''.join([c for c in value if c.isalpha()])
    if not num:
        num = 7
    if unit == "h":
        return timedelta(hours=num)
    elif unit == "d":
        return timedelta(days=num)
    elif unit == "w":
        return timedelta(weeks=num)
    elif unit == "m":  # months approximated to 30 days
        return timedelta(days=num * 30)
    return timedelta(days=num)


# src/services/slack_manager.py


def fetch_channel_messages_last_k(
    channel_id: str, bot_user_id: str | None = None, k: int = 100
) -> list[dict]:
    """
    Fetch up to K most recent messages from a Slack channel, with pagination.
    Returns messages sorted newest → oldest.
    """
    logger.debug(f"🧭 Fetching up to {k} messages for channel={channel_id}")

    all_messages: list[dict] = []
    cursor: str | None = None
    total_fetched = 0
    batch_size = 200  # Slack max per call = 200

    try:
        while True:
            remaining = k - total_fetched if k else batch_size
            limit = min(batch_size, remaining)

            resp = client.conversations_history(
                channel=channel_id,
                limit=limit,
                cursor=cursor or "",
            )
            messages = resp.get("messages") or []
            if not messages:
                break

            logger.debug(
                f"📬 Got batch of {len(messages)} messages (total so far {total_fetched + len(messages)})"
            )

            # Filter out system / bot messages
            for m in messages:
                subtype = m.get("subtype")
                user = m.get("user")
                bot_id = m.get("bot_id")
                if subtype in {"channel_join", "channel_leave", "channel_topic"}:
                    continue
                if bot_user_id and (user == bot_user_id or bot_id == bot_user_id):
                    continue
                all_messages.append(m)

            total_fetched = len(all_messages)

            # Stop when we have enough
            if k and total_fetched >= k:
                break

            # Cursor for next page
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

            time.sleep(0.6)  # avoid rate limits

        # Slack returns newest first — keep that order
        logger.debug(f"✅ Total fetched = {len(all_messages)} messages (newest→oldest)")
        return all_messages

    except SlackApiError as e:
        logger.error(f"⚠️ Slack API error: {e.response['error']}")
        return []
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")
        return []


def fetch_channel_messages(channel_id: str, max_messages: int = 0) -> list[dict]:
    """
    Fetch Slack messages strictly between (now - MAX_MESSAGE_AGE) and now.
    """
    from loguru import logger
    from datetime import datetime, timezone

    max_age_str = os.getenv("MAX_MESSAGE_AGE", "7h")
    cutoff_delta = parse_duration_to_timedelta(max_age_str)
    now_utc = datetime.now(timezone.utc)
    cutoff_dt = now_utc - cutoff_delta

    logger.debug(f"⏱️ Time-window fetch for channel={channel_id}")
    logger.debug(
        f"🕓 Cutoff datetime={cutoff_dt.isoformat()} → Now={now_utc.isoformat()}"
    )

    cursor = None
    messages_out: list[dict] = []
    total_fetched = 0

    while True:
        try:
            resp = client.conversations_history(
                channel=channel_id,
                limit=200,
                cursor=cursor or "",
                latest=str(now_utc.timestamp()),
                oldest=str(cutoff_dt.timestamp()),
                inclusive=True,
            )
            messages = resp.get("messages") or []
            if not messages:
                logger.debug("⚠️ No messages returned in time window.")
                break

            logger.debug(
                f"📬 Batch fetched {len(messages)} messages within time window"
            )

            for msg in messages:
                ts_val = float(msg.get("ts", 0))
                msg_dt = datetime.fromtimestamp(ts_val, timezone.utc)
                if msg_dt < cutoff_dt or msg_dt > now_utc:
                    continue  # out of window

                if msg.get("subtype") == "bot_message":
                    continue
                if "thread_ts" in msg and msg["thread_ts"] != msg["ts"]:
                    continue

                messages_out.append(msg)
                total_fetched += 1

                if max_messages and total_fetched >= max_messages:
                    break

            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

            logger.debug(f"↩️ Paging backward, cursor exists → fetching next batch...")
            time.sleep(0.8)

        except SlackApiError as e:
            logger.error(f"⚠️ Slack API error: {e}")
            break

    logger.debug(
        f"✅ Finished fetch — kept {len(messages_out)} messages in last {max_age_str}"
    )
    return messages_out


# ----------------------------------------------------------------------
# 🧩 Channel helpers
# ----------------------------------------------------------------------
def get_channel_id_by_name(name: str) -> str:
    """Resolve human-readable name → Slack channel ID."""
    cursor: str | None = None
    while True:
        resp = client.conversations_list(
            types="public_channel,private_channel",
            limit=1000,
            cursor=cursor or "",
        )
        channels = resp.get("channels") or []
        for ch in channels:
            if ch.get("name") == name or ch.get("id") == name:
                return ch["id"]
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    raise ValueError(f"Channel '{name}' not found.")


# ----------------------------------------------------------------------
# 🧵 Thread replies
# ----------------------------------------------------------------------
def fetch_thread_replies(channel_id: str, thread_ts: str) -> list[dict]:
    """Fetch all replies for a given thread safely."""
    replies: list[dict] = []
    cursor: str | None = None

    while True:
        try:
            resp = client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=200,
                cursor=cursor or "",
            )
            messages = resp.get("messages") or []
            if len(messages) > 1:
                replies.extend(messages[1:])  # skip parent
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.5)
        except SlackApiError as e:
            print(f"⚠️ Error fetching thread replies: {e}")
            break
    return replies


# ----------------------------------------------------------------------
# 🔗 URL Extraction
# ----------------------------------------------------------------------
def extract_urls_from_messages(messages: list[dict]) -> list[str]:
    """Extract all URLs from Slack messages and their replies."""
    url_pattern = re.compile(r"https?://[^\s<>|]+")
    urls: Set[str] = set()

    for msg in messages:
        text = msg.get("text", "")
        for match in url_pattern.findall(text):
            urls.add(match)

        # Include replies if present
        for reply in msg.get("replies_full", []):
            text = reply.get("text", "")
            for match in url_pattern.findall(text):
                urls.add(match)

    return sorted(urls)


# ----------------------------------------------------------------------
# 🚀 Combined high-level function
# ----------------------------------------------------------------------
async def extract_urls_from_channel(channel_name: str, limit: Optional[int]) -> List[str]:
    """
    Main entrypoint: fetch Slack messages from a channel and extract URLs.
    Args:
        channel_name: Slack channel name (e.g. "threat-intelligence")
        limit: max number of messages (0 = all)
    Returns:
        list[str]: unique URLs found
    """
    print(f"📡 Fetching messages from Slack channel: {channel_name}")

    if limit is None:
        limit = 0

    channel_id = get_channel_id_by_name(channel_name)
    messages = fetch_channel_messages(channel_id, max_messages=limit)
    print(f"💬 Retrieved {len(messages)} messages from {channel_name}")

    urls = extract_urls_from_messages(messages)
    print(f"🔗 Extracted {len(urls)} unique URLs")

    return urls


def send_direct_message(user_email: str, text: str):
    """
    Send a direct message to a specific Slack user via email lookup.
    Requires users:read.email, chat:write, and im:write scopes.
    """
    try:
        # Lookup Slack user by email
        resp = client.users_lookupByEmail(email=user_email)

        # Convert SlackResponse to dict safely
        data = resp.data if hasattr(resp, "data") else resp
        if not isinstance(data, dict):
            raise ValueError(f"Unexpected Slack response type: {type(data)}")

        user_obj = data.get("user")
        if not user_obj or not isinstance(user_obj, dict):
            raise ValueError(f"User not found or malformed response for {user_email}")

        user_id = user_obj.get("id")
        if not user_id:
            raise ValueError(f"Missing user ID in Slack response for {user_email}")

        # Send the message
        client.chat_postMessage(channel=user_id, text=text)
        print(f"📩 Sent DM to {user_email} (user_id={user_id})")

    except Exception as e:
        print(f"⚠️ Failed to send DM to {user_email}: {e}")
