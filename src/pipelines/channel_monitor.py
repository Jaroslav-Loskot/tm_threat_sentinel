# ============================================================
# 📦 Threat Intelligence Channel Monitor
# ============================================================
import asyncio
from datetime import datetime, timezone
import re
import json
import os
from typing import List, Dict, Set
from pathlib import Path
from dotenv import load_dotenv

from src.core.slack_manager import client, fetch_channel_messages
from src.core.crawler_manager import crawl_urls_playwright
from src.core.analyzer_manager import analyze_article
from src.utils.file_utils import load_json, save_json
from src.utils.path_utils import get_data_path

load_dotenv(override=True)


# ============================================================
# ⚙️ Environment
# ============================================================
ALERT_EMAILS = [
    e.strip() for e in os.getenv("ALERT_EMAILS", "").split(",") if e.strip()
]
ALERT_THRESHOLD = int(os.getenv("ALERT_THRESHOLD", "4"))

URL_PATTERN = re.compile(r"https?://[^\s<>|]+")
SECTION_PATTERN = re.compile(
    r"(?is)(?:\*\*|\*|#+|\s|^)*(Summary|Potential Impact|Relevance|Severity|Recommended Actions)[:\-]\s*(.*?)"
    r"(?=\n\s*(?:\*\*|\*|#+)?\s*(Summary|Potential Impact|Relevance|Severity|Recommended Actions)[:\-]|\Z)",
    re.DOTALL,
)


# ============================================================
# 📦 Helpers — Seen URL tracking
# ============================================================
def load_seen_urls() -> set[str]:
    """Load and auto-clean old seen URLs based on MAX_MESSAGE_AGE."""
    path = get_data_path("seen_urls.json")
    max_age_str = os.getenv("MAX_MESSAGE_AGE", "7d")

    # reuse the same helper logic as in slack_manager
    from src.core.slack_manager import parse_duration_to_timedelta
    cutoff_delta = parse_duration_to_timedelta(max_age_str)
    cutoff_time = datetime.now(timezone.utc) - cutoff_delta

    if not Path(path).exists():
        return set()

    try:
        data = load_json(path)
        # keep only recent entries (with timestamp if available)
        filtered = []
        for item in data:
            ts = item.get("timestamp")
            if not ts:
                filtered.append(item)
                continue
            try:
                if datetime.fromisoformat(ts) >= cutoff_time:
                    filtered.append(item)
            except Exception:
                filtered.append(item)
        if len(filtered) != len(data):
            save_json(filtered, path)
        return {d["url"] for d in filtered if "url" in d}
    except Exception:
        return set()

def save_seen_urls(urls: set[str]):
    """Save seen URLs with timestamp for pruning."""
    path = get_data_path("seen_urls.json")
    now = datetime.utcnow().isoformat()
    data = [{"url": u, "timestamp": now} for u in urls]
    save_json(data, path)

# ============================================================
# 🧠 Parsing + Formatting
# ============================================================
def parse_analysis_text(text: str) -> Dict[str, str]:
    """Parse LLM text output into structured fields."""
    sections = {
        "Summary": "",
        "Potential Impact": "",
        "Relevance": "",
        "Severity": "",
        "Recommended Actions": "",
    }

    if not text:
        print("⚠️ Empty LLM text received")
        return sections

    matches = list(SECTION_PATTERN.finditer(text.replace("\r", "").strip()))
    print(f"🔍 Found {len(matches)} structured sections")

    if not matches:
        sections["Summary"] = text.strip()
        return sections

    for match in matches:
        key = match.group(1).strip().title()
        val = re.sub(r"(^[\*\s:_\-]+|[\*\s:_\-]+$)", "", match.group(2), flags=re.MULTILINE).strip()
        if key.lower().startswith("relevance"):
            val = re.sub(r"(\d)\s*/\s*\d", r"\1", val)
        sections[key] = val
        print(f"✅ Parsed {key}: {val[:80]}")

    return sections


def build_slack_blocks(url: str, data: Dict[str, str]) -> List[Dict]:
    """Format analysis result as Slack Block Kit message."""
    relevance = data.get("Relevance", "N/A")
    impact = data.get("Potential Impact", "N/A")

    header = f"🧠 ThreatMark Intelligence Analysis"
    fields = [
        {"type": "mrkdwn", "text": f"📝 *Summary:*\n{data.get('Summary','N/A')}"},
        {"type": "mrkdwn", "text": f"⚠️ *Impact:*\n{impact}"},
        {"type": "mrkdwn", "text": f"🔢 *Relevance:*\n{relevance}"},
        {"type": "mrkdwn", "text": f"🧭 *Actions:*\n{data.get('Recommended Actions','N/A')}"},
    ]

    return [
        {"type": "header", "text": {"type": "plain_text", "text": header, "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*URL:* <{url}>"}},
        {"type": "divider"},
        {"type": "section", "fields": fields},
    ]


# ==============================================================
# 🎨 Emoji + Alerts - IMPROVED VERSION
# ==============================================================

def get_severity_emojis(severity: str, relevance_text: str) -> List[str]:
    """Choose emojis based on severity and relevance."""
    severity = (severity or "").strip().lower()
    relevance = 0
    match = re.search(r"\d+", relevance_text or "")
    if match:
        relevance = int(match.group())
    
    print(f"🎨 Determining emoji - Severity: '{severity}', Relevance: {relevance}")
    
    if severity == "critical":
        return ["red_circle", "bangbang"]  # 🔴‼️
    if severity == "red":
        return ["red_circle"]  # 🔴
    if severity == "amber":
        return ["large_orange_circle"]  # 🟠 (note: changed from orange_circle)
    if severity == "green":
        return ["large_green_circle"]  # 🟢 (note: changed from green_circle)
    
    # fallback by relevance
    if relevance >= 5:
        return ["red_circle", "bangbang"]
    if relevance >= 4:
        return ["red_circle"]
    if relevance >= 3:
        return ["large_orange_circle"]
    
    return ["large_green_circle"]


def send_dm_alert(url: str, severity: str, relevance: str, impact: str):
    """DM alert for high-severity threats."""
    from src.core.slack_manager import send_direct_message  # lazy import to avoid circulars

    if severity.lower() not in ["critical", "red"]:
        print(f"ℹ️ No DM alert for severity={severity}")
        return

    alert_text = (
        f"🚨 *High-severity threat detected!*\n"
        f"<{url}>\n"
        f"Severity: {severity}\n"
        f"Relevance: {relevance}\n"
        f"Impact: {impact[:200]}..."
    )
    for email in ALERT_EMAILS:
        send_direct_message(email, alert_text)
    print(f"📨 Sent {severity.upper()} DM alert → {url}")


# ============================================================
# 💬 Slack helpers
# ============================================================
def get_bot_user_id() -> str:
    try:
        return client.auth_test().get("user_id", "")
    except Exception as e:
        print(f"⚠️ Failed to get bot user ID: {e}")
        return ""


def post_thread_reply(channel_id: str, parent_ts: str, text: str, blocks: list | None = None):
    try:
        client.chat_postMessage(channel=channel_id, thread_ts=parent_ts, text=text, blocks=blocks or [])
    except Exception as e:
        print(f"⚠️ Failed to post Slack message: {e}")


def add_reaction(channel_id: str, ts: str, emoji: str):
    """Add emoji reaction to a Slack message with detailed error logging."""
    try:
        print(f"➕ Adding reaction '{emoji}' to message {ts[:10]}...")
        client.reactions_add(channel=channel_id, timestamp=ts, name=emoji)
        print(f"✅ Successfully added reaction: {emoji}")
    except Exception as e:
        error_msg = str(e)
        if "already_reacted" in error_msg:
            print(f"ℹ️ Already reacted with {emoji}")
        elif "invalid_name" in error_msg:
            print(f"⚠️ Invalid emoji name: {emoji} - trying fallback")
            # Try fallback emojis
            fallback_map = {
                "green_circle": "large_green_circle",
                "orange_circle": "large_orange_circle",
                "red_circle": "red_circle",
                "bangbang": "bangbang"
            }
            fallback = fallback_map.get(emoji)
            if fallback and fallback != emoji:
                try:
                    client.reactions_add(channel=channel_id, timestamp=ts, name=fallback)
                    print(f"✅ Used fallback emoji: {fallback}")
                except Exception as e2:
                    print(f"❌ Fallback also failed: {e2}")
            else:
                print(f"❌ No fallback available for {emoji}")
        else:
            print(f"⚠️ Failed to add reaction '{emoji}': {e}")


# ==============================================================
# 🔁 Core logic — Single URL analysis - IMPROVED VERSION
# ==============================================================


async def process_url(
    channel_id: str, ts: str, url: str, model_name: str, seen_urls: Set[str]
):
    """Crawl → analyze → post results → react. Only post if successful."""
    print(f"\n{'='*60}")
    print(f"🔗 Processing URL: {url}")
    print(f"📍 Message timestamp: {ts}")
    print(f"{'='*60}\n")

    # --- Crawl ---
    try:
        print(f"🕷️ Crawling {url}...")
        crawled = await crawl_urls_playwright([url])
        if not crawled or "error" in crawled[0]:
            raise ValueError(crawled[0].get("error", "Crawl failed"))
        content = crawled[0].get("content", "")
        if not content.strip():
            raise ValueError("Empty content")
        print(f"✅ Crawled successfully ({len(content)} chars)")
    except Exception as e:
        print(f"❌ Crawl failed: {e}")
        # Don't post anything to Slack on crawl failure
        # Just mark as seen to avoid retrying
        seen_urls.add(url)
        save_seen_urls(seen_urls)
        return

    # --- Analyze ---
    print(f"🧠 Analyzing with {model_name}...")
    try:
        result = analyze_article(url, content)

        # Check if analysis returned an error
        if "error" in result:
            raise Exception(result["error"])

        analysis_text = result.get("analysis", "")

        if not analysis_text or not analysis_text.strip():
            raise Exception("Empty analysis result")

        print(f"✅ Analysis complete")
        print(f"📝 Analysis preview: {analysis_text[:200]}...")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        # Don't post anything to Slack on analysis failure
        # Mark as seen to avoid infinite retries
        seen_urls.add(url)
        save_seen_urls(seen_urls)
        return

    # --- Parse ---
    print(f"📊 Parsing analysis results...")
    try:
        parsed = parse_analysis_text(analysis_text)
        severity = parsed.get("Severity", "").strip()
        relevance = parsed.get("Relevance", "").strip()
        impact = parsed.get("Potential Impact", "")

        print(f"🎯 Parsed Results:")
        print(f"   Severity: '{severity}'")
        print(f"   Relevance: '{relevance}'")
        print(f"   Impact: {impact[:100]}...")

    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        # Don't post malformed results
        seen_urls.add(url)
        save_seen_urls(seen_urls)
        return

    # --- Post thread (only if everything succeeded) ---
    try:
        print(f"💬 Posting analysis to Slack thread...")
        blocks = build_slack_blocks(url, parsed)
        post_thread_reply(
            channel_id, ts, text=f"📊 ThreatMark Analysis for {url}", blocks=blocks
        )
        print(f"✅ Posted analysis to thread")
    except Exception as e:
        print(f"⚠️ Failed to post to Slack: {e}")
        # Continue anyway - we at least tried

    # --- Add emoji reactions (only if analysis succeeded) ---
    try:
        print(f"\n🎨 Adding severity emoji reactions...")
        emojis = get_severity_emojis(severity, relevance)
        print(f"   Selected emojis: {emojis}")

        for emoji in emojis:
            add_reaction(channel_id, ts, emoji)

        print(f"✅ Added {len(emojis)} reaction(s)")
    except Exception as e:
        print(f"⚠️ Failed to add reactions: {e}")
        # Non-critical failure, continue

    # --- DM alert if critical ---
    try:
        if severity.lower() in ["critical", "red"]:
            print(f"🚨 Sending DM alert for {severity.upper()} severity")
            send_dm_alert(url, severity, relevance, impact)
    except Exception as e:
        print(f"⚠️ Failed to send DM alert: {e}")
        # Non-critical failure, continue

    # --- Log + mark processed ---
    seen_urls.add(url)
    log_path = get_data_path("channel_analysis_log.json")
    try:
        logs = load_json(log_path) if Path(log_path).exists() else []
        logs.append(
            {
                "url": url,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": severity,
                "relevance": relevance,
                "analysis": parsed,
            }
        )
        save_json(logs, log_path)
    except Exception as e:
        print(f"⚠️ Failed to save log: {e}")

    save_seen_urls(seen_urls)

    print(f"\n✅ Completed processing: {url}")
    print(f"{'='*60}\n")


# ============================================================
# 🚀 Monitor Channel Loop
# ============================================================
async def monitor_channel(channel_id: str, model_name="claude", poll_interval=60):
    print(f"👀 Monitoring Slack channel {channel_id}...")
    seen_urls = load_seen_urls()
    bot_user_id = get_bot_user_id()
    print(f"🤖 Bot user ID: {bot_user_id}")

    while True:
        messages = fetch_channel_messages(channel_id)
        print(f"💬 Scanned {len(messages)} messages")

        new_found = False
        for msg in messages:
            if msg.get("subtype") == "bot_message" or msg.get("user") == bot_user_id:
                continue

            urls = URL_PATTERN.findall(msg.get("text", ""))
            ts = msg.get("ts", "")
            for url in urls:
                if url not in seen_urls:
                    new_found = True
                    await process_url(channel_id, ts, url, model_name, seen_urls)

        if not new_found:
            print(f"🕐 No new URLs found. Sleeping {poll_interval}s...")
        await asyncio.sleep(poll_interval)
