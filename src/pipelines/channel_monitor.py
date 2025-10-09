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


# ============================================================
# 🎨 Emoji + Alerts
# ============================================================
def get_severity_emojis(severity: str, relevance_text: str) -> List[str]:
    """Choose emojis based on severity and relevance."""
    severity = (severity or "").strip().lower()
    relevance = 0
    match = re.search(r"\d+", relevance_text or "")
    if match:
        relevance = int(match.group())

    if severity == "critical":
        return ["red_circle", "bangbang"]  # 🔴‼️
    if severity == "red":
        return ["red_circle"]  # 🔴
    if severity == "amber":
        return ["orange_circle"]  # 🟠
    if severity == "green":
        return ["green_circle"]  # 🟢

    # fallback by relevance
    if relevance >= 5:
        return ["red_circle", "bangbang"]
    if relevance >= 4:
        return ["red_circle"]
    if relevance >= 3:
        return ["orange_circle"]
    return ["green_circle"]


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
    try:
        client.reactions_add(channel=channel_id, timestamp=ts, name=emoji)
    except Exception as e:
        if "already_reacted" not in str(e):
            print(f"⚠️ Failed to add reaction: {e}")


# ============================================================
# 🔁 Core logic — Single URL analysis
# ============================================================
async def process_url(channel_id: str, ts: str, url: str, model_name: str, seen_urls: Set[str]):
    """Crawl → analyze → post results → react."""
    print(f"🔗 Processing URL: {url}")

    # --- Crawl ---
    try:
        crawled = await crawl_urls_playwright([url])
        if not crawled or "error" in crawled[0]:
            raise ValueError(crawled[0].get("error", "Crawl failed"))
        content = crawled[0].get("content", "")
        if not content.strip():
            raise ValueError("Empty content")
    except Exception as e:
        post_thread_reply(channel_id, ts, f"❌ Crawl failed for <{url}> → {e}")
        seen_urls.add(url)
        return

    # --- Analyze ---
    try:
        result = analyze_article(url, content, model=model_name)
        analysis_text = result.get("analysis") or result.get("error", "No analysis result")
    except Exception as e:
        analysis_text = f"Error during analysis: {e}"

    # --- Parse ---
    parsed = parse_analysis_text(analysis_text)
    severity = parsed.get("Severity", "")
    relevance = parsed.get("Relevance", "")
    impact = parsed.get("Potential Impact", "")

    # --- Post thread ---
    blocks = build_slack_blocks(url, parsed)
    post_thread_reply(channel_id, ts, text=f"📊 ThreatMark Analysis for {url}", blocks=blocks)

    # --- Add emoji reactions ---
    for emoji in get_severity_emojis(severity, relevance):
        add_reaction(channel_id, ts, emoji)

    # --- DM alert if critical ---
    send_dm_alert(url, severity, relevance, impact)

    # --- Log + mark processed ---
    seen_urls.add(url)
    log_path = get_data_path("channel_analysis_log.json")
    logs = load_json(log_path) if Path(log_path).exists() else []
    logs.append({"url": url, "analysis": parsed})
    save_json(logs, log_path)
    save_seen_urls(seen_urls)


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
