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

# ==============================================================
# 💬 Channel message fetcher (with age cutoff)
# ==============================================================
def fetch_channel_messages(channel_id: str, max_messages: int = 0) -> list[dict]:
    """Fetch top-level messages from a Slack channel, limited by MAX_MESSAGE_AGE."""
    max_age_str = os.getenv("MAX_MESSAGE_AGE", "7d")
    cutoff_delta = parse_duration_to_timedelta(max_age_str)
    cutoff_ts = (datetime.now() - cutoff_delta).timestamp()

    cursor: str | None = None
    messages_out: list[dict] = []
    pbar = tqdm(total=max_messages if max_messages else None,
                desc=f"📥 Messages {channel_id}", unit="msg")

    while True:
        try:
            resp = client.conversations_history(channel=channel_id, limit=200, cursor=cursor or "")
            messages = resp.get("messages") or []

            for msg in messages:
                ts_val = float(msg.get("ts", 0))
                if ts_val < cutoff_ts:
                    # 🧹 stop early if we’ve reached older messages
                    pbar.close()
                    print(f"⏹️  Reached cutoff ({max_age_str}), stopping at {len(messages_out)} messages.")
                    return messages_out

                # only main messages
                if "thread_ts" in msg and msg["thread_ts"] != msg["ts"]:
                    continue

                if msg.get("reply_count", 0) > 0:
                    msg["replies_full"] = fetch_thread_replies(channel_id, msg["ts"])

                messages_out.append(msg)
                pbar.update(1)
                if max_messages and len(messages_out) >= max_messages:
                    pbar.close()
                    return messages_out

            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.8)

        except SlackApiError as e:
            print(f"⚠️ Error fetching messages: {e}")
            break

    pbar.close()
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