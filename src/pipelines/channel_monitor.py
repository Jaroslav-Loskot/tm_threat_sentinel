"""
============================================================
📦 Threat Intelligence Channel Monitor Pipeline
============================================================
Continuously monitors a Slack channel for URLs, crawls them,
analyzes their content with LLMs, and posts summarized results.
============================================================
"""

import asyncio
import re
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Set
from loguru import logger

from src.services.slack_manager import (
    client,
    fetch_channel_messages,
    parse_duration_to_timedelta,
    get_channel_id_by_name,
)
from src.services.crawler_manager import crawl_urls_playwright
from src.services.analyzer_manager import analyze_article
from src.utils.file_utils import load_json, save_json
from src.utils.path_utils import get_data_path
from src.utils.slack_helpers import (
    post_thread_reply_async,
    add_reaction_async,
    build_analysis_blocks,
    send_alert_dm_async,
)
from src.pipelines.base_pipeline import BasePipeline
from dotenv import load_dotenv

load_dotenv()

MAX_MESSAGE_AGE = os.getenv("MAX_MESSAGE_AGE", "7d")

class ChannelMonitorPipeline(BasePipeline):
    name = "Slack Channel Monitor"

    URL_PATTERN = re.compile(r"https?://[^\s<>|]+")
    SECTION_PATTERN = re.compile(
        r"(?is)(?:\*\*|\*|#+|\s|^)*(Summary|Potential Impact|Relevance|Severity|Recommended Actions)[:\-]\s*(.*?)"
        r"(?=\n\s*(?:\*\*|\*|#+)?\s*(Summary|Potential Impact|Relevance|Severity|Recommended Actions)[:\-]|\Z)",
        re.DOTALL,
    )

    def __init__(
        self,
        channel_id: str,
        model_name: str = "claude",
        poll_interval: int = 60,
        alert_emails: List[str] | None = None,
    ):
        super().__init__(
            channel_id=channel_id,
            model_name=model_name,
            poll_interval=poll_interval,
            alert_emails=alert_emails,
        )

        # 🧭 Resolve channel name → ID if needed
        if not channel_id.startswith("C"):
            try:
                resolved_id = get_channel_id_by_name(channel_id)
                logger.info(f"✅ Resolved channel '{channel_id}' → {resolved_id}")
                channel_id = resolved_id
            except Exception as e:
                logger.error(f"❌ Failed to resolve channel '{channel_id}': {e}")

        self.channel_id = channel_id
        self.model_name = model_name
        self.poll_interval = poll_interval
        self.alert_emails = alert_emails or []
        self.seen_urls = self._load_seen_urls()
        self.bot_user_id = self._get_bot_user_id()

    # ============================================================
    # 🔁 Main loop
    # ============================================================
    async def execute(self):
        logger.info(f"👀 Monitoring Slack channel {self.channel_id}...")
        logger.info(f"🤖 Bot user ID: {self.bot_user_id}")

        while True:
            messages = fetch_channel_messages(self.channel_id)
            logger.info(f"💬 Scanned {len(messages)} messages")

            new_urls = await self._find_new_urls(messages)
            if not new_urls:
                logger.info(f"🕐 No new URLs found. Sleeping {self.poll_interval}s...")
                await asyncio.sleep(self.poll_interval)
                continue

            for ts, url in new_urls:
                await self._process_url(ts, url)

    # ============================================================
    # 🔍 Message scanning
    # ============================================================
    async def _find_new_urls(self, messages) -> List[tuple[str, str]]:
        new_urls = []
        for msg in messages:
            if (
                msg.get("subtype") == "bot_message"
                or msg.get("user") == self.bot_user_id
            ):
                continue
            ts = msg.get("ts", "")
            for url in self.URL_PATTERN.findall(msg.get("text", "")):
                if url not in self.seen_urls:
                    new_urls.append((ts, url))
        return new_urls

    # ============================================================
    # 🧩 URL processing (crawl → analyze → post)
    # ============================================================
    async def _process_url(self, ts: str, url: str):
        logger.info(f"\n🔗 Processing URL: {url}")

        # --- Crawl ---
        content = await self._crawl_url(url)
        if not content:
            return

        # --- Analyze ---
        analysis_text = await self._analyze_content(url, content)
        if not analysis_text:
            return

        # --- Parse ---
        parsed = self._parse_analysis(analysis_text)
        severity = parsed.get("Severity", "").strip()
        relevance = parsed.get("Relevance", "").strip()
        impact = parsed.get("Potential Impact", "")

        # --- Post to Slack ---
        try:
            blocks = build_analysis_blocks(url, parsed)
            await post_thread_reply_async(
                self.channel_id,
                ts,
                text=f"📊 ThreatMark Analysis for {url}",
                blocks=blocks,
            )
            logger.success(f"✅ Posted analysis for {url}")
        except Exception as e:
            logger.error(f"❌ Failed to post analysis for {url}: {e}")

        # --- React + Alert ---
        await self._add_reactions(ts, severity, relevance)
        await send_alert_dm_async(self.alert_emails, url, severity, relevance, impact)

        # --- Mark as processed ---
        self._mark_processed(url, severity, relevance, parsed)

    # ============================================================
    # 🌐 Crawl stage
    # ============================================================
    async def _crawl_url(self, url: str) -> str | None:
        try:
            logger.info(f"🕷️ Crawling {url}...")
            crawled = await crawl_urls_playwright([url])
            if not crawled or "error" in crawled[0]:
                raise ValueError(crawled[0].get("error", "Crawl failed"))

            content = crawled[0].get("content", "")
            if not content.strip():
                raise ValueError("Empty content")

            logger.success(f"✅ Crawled successfully ({len(content)} chars)")
            return content
        except Exception as e:
            logger.error(f"❌ Crawl failed for {url}: {e}")
            self._mark_seen(url)
            return None

    # ============================================================
    # 🧠 Analysis stage
    # ============================================================
    async def _analyze_content(self, url: str, content: str) -> str | None:
        try:
            logger.info(f"🧠 Analyzing with {self.model_name}...")
            result = analyze_article(url, content)
            analysis_text = result.get("analysis", "")
            if not analysis_text:
                raise ValueError("Empty analysis result")

            logger.success("✅ Analysis complete")
            logger.debug(f"📝 Preview: {analysis_text[:200]}...")
            return analysis_text
        except Exception as e:
            logger.error(f"❌ Analysis failed for {url}: {e}")
            self._mark_seen(url)
            return None

    # ============================================================
    # 📊 Parsing stage
    # ============================================================
    def _parse_analysis(self, text: str) -> Dict[str, str]:
        sections = {
            "Summary": "",
            "Potential Impact": "",
            "Relevance": "",
            "Severity": "",
            "Recommended Actions": "",
        }

        if not text:
            return sections

        matches = list(self.SECTION_PATTERN.finditer(text.replace("\r", "").strip()))
        if not matches:
            sections["Summary"] = text.strip()
            return sections

        for match in matches:
            key = match.group(1).strip().title()
            val = re.sub(
                r"(^[\*\s:_\-]+|[\*\s:_\-]+$)", "", match.group(2), flags=re.MULTILINE
            ).strip()
            if key.lower().startswith("relevance"):
                val = re.sub(r"(\d)\s*/\s*\d", r"\1", val)
            sections[key] = val
        return sections

    # ============================================================
    # 🎨 Reactions
    # ============================================================
    async def _add_reactions(self, ts: str, severity: str, relevance: str):
        emojis = self._get_severity_emojis(severity, relevance)
        for emoji in emojis:
            await add_reaction_async(self.channel_id, ts, emoji)

    def _get_severity_emojis(self, severity: str, relevance_text: str) -> List[str]:
        severity = (severity or "").strip().lower()
        match = re.search(r"\d+", relevance_text or "")
        relevance = int(match.group()) if match else 0

        if severity == "critical":
            return ["red_circle", "bangbang"]
        if severity == "red":
            return ["red_circle"]
        if severity == "amber":
            return ["large_orange_circle"]
        if severity == "green":
            return ["large_green_circle"]
        if relevance >= 5:
            return ["red_circle", "bangbang"]
        if relevance >= 4:
            return ["red_circle"]
        if relevance >= 3:
            return ["large_orange_circle"]
        return ["large_green_circle"]

    # ============================================================
    # 🧾 Persistence
    # ============================================================
    def _mark_processed(
        self, url: str, severity: str, relevance: str, analysis: Dict[str, str]
    ):
        self._mark_seen(url)
        log_path = get_data_path("channel_analysis_log.json")
        logs = load_json(log_path) if Path(log_path).exists() else []
        logs.append(
            {
                "url": url,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": severity,
                "relevance": relevance,
                "analysis": analysis,
            }
        )
        save_json(logs, log_path)

    def _mark_seen(self, url: str):
        self.seen_urls.add(url)
        self._save_seen_urls(self.seen_urls)

    def _load_seen_urls(self) -> Set[str]:
        path = get_data_path("seen_urls.json")
        cutoff_delta = parse_duration_to_timedelta(MAX_MESSAGE_AGE)
        cutoff_time = datetime.now(timezone.utc) - cutoff_delta
        if not Path(path).exists():
            return set()
        try:
            data = load_json(path)
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

    def _save_seen_urls(self, urls: Set[str]):
        now = datetime.utcnow().isoformat()
        data = [{"url": u, "timestamp": now} for u in urls]
        save_json(data, get_data_path("seen_urls.json"))

    def _get_bot_user_id(self) -> str:
        try:
            return client.auth_test().get("user_id", "")
        except Exception as e:
            logger.warning(f"⚠️ Failed to get bot user ID: {e}")
            return ""
