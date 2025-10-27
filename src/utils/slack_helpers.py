"""
============================================================
💬 Slack Helpers (Async-Safe)
============================================================
- posting messages and thread replies
- adding emoji reactions
- sending DM alerts
- building formatted Slack Block Kit messages
============================================================
"""

import asyncio
from typing import List, Dict, Optional
from loguru import logger
from slack_sdk.errors import SlackApiError
from src.services.slack_manager import client, send_direct_message


# ============================================================
# 💬 Message Posting
# ============================================================


def _post_thread_reply(
    channel_id: str, parent_ts: str, text: str, blocks: Optional[list] = None
):
    """Internal synchronous Slack thread post."""
    try:
        client.chat_postMessage(
            channel=channel_id, thread_ts=parent_ts, text=text, blocks=blocks or []
        )
        logger.info(f"💬 Posted thread reply in {channel_id} @ {parent_ts[:10]}")
    except SlackApiError as e:
        logger.error(
            f"❌ Slack API Error posting thread: {e.response.get('error')} ({e.response.data})"
        )
        raise
    except Exception as e:
        logger.error(f"❌ Failed to post Slack thread reply: {e}")
        raise


async def post_thread_reply_async(
    channel_id: str, parent_ts: str, text: str, blocks: Optional[list] = None
):
    await asyncio.to_thread(_post_thread_reply, channel_id, parent_ts, text, blocks)


# ============================================================
# 🎨 Emoji Reactions
# ============================================================


def _add_reaction(channel_id: str, ts: str, emoji: str):
    """Internal synchronous reaction adder."""
    try:
        client.reactions_add(channel=channel_id, timestamp=ts, name=emoji)
        logger.info(f"➕ Added reaction '{emoji}' to message {ts[:10]}")
    except SlackApiError as e:
        err = e.response.get("error")
        if err == "already_reacted":
            logger.debug(f"ℹ️ Already reacted with {emoji}")
        elif err == "invalid_name":
            fallback = {
                "green_circle": "large_green_circle",
                "orange_circle": "large_orange_circle",
            }.get(emoji)
            if fallback:
                try:
                    client.reactions_add(
                        channel=channel_id, timestamp=ts, name=fallback
                    )
                    logger.info(f"✅ Used fallback emoji: {fallback}")
                    return
                except Exception as e2:
                    logger.error(f"❌ Fallback emoji also failed: {e2}")
        else:
            logger.error(f"❌ Slack reaction error '{emoji}': {err}")
            raise
    except Exception as e:
        logger.error(f"❌ Failed to add reaction '{emoji}': {e}")
        raise


async def add_reaction_async(channel_id: str, ts: str, emoji: str):
    await asyncio.to_thread(_add_reaction, channel_id, ts, emoji)


# ============================================================
# 🚨 DM Alerts
# ============================================================


def _send_alert_dm(
    emails: List[str], url: str, severity: str, relevance: str, impact: str
):
    """Sync internal DM sender."""
    if severity.lower() not in ["critical", "red"]:
        logger.debug(f"ℹ️ No DM alert for severity={severity}")
        return
    alert_text = (
        f"🚨 *High-severity threat detected!*\n"
        f"<{url}>\n"
        f"Severity: {severity}\n"
        f"Relevance: {relevance}\n"
        f"Impact: {impact[:200]}..."
    )
    for email in emails:
        try:
            send_direct_message(email, alert_text)
            logger.info(f"📨 Sent DM alert to {email}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to send DM to {email}: {e}")


async def send_alert_dm_async(
    emails: List[str], url: str, severity: str, relevance: str, impact: str
):
    await asyncio.to_thread(_send_alert_dm, emails, url, severity, relevance, impact)


# ============================================================
# 🧠 Block Kit Builder
# ============================================================


def build_analysis_blocks(url: str, data: Dict[str, str]) -> List[Dict]:
    relevance = data.get("Relevance", "N/A")
    impact = data.get("Potential Impact", "N/A")

    fields = [
        {"type": "mrkdwn", "text": f"📝 *Summary:*\n{data.get('Summary','N/A')}"},
        {"type": "mrkdwn", "text": f"⚠️ *Impact:*\n{impact}"},
        {"type": "mrkdwn", "text": f"🔢 *Relevance:*\n{relevance}"},
        {
            "type": "mrkdwn",
            "text": f"🧭 *Actions:*\n{data.get('Recommended Actions','N/A')}",
        },
    ]

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🧠 ThreatMark Intelligence Analysis",
            },
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*URL:* <{url}>"}},
        {"type": "divider"},
        {"type": "section", "fields": fields},
    ]
