"""
============================================================
🧠 Threat Intelligence Orchestrator
============================================================
High-level orchestration of the full intelligence pipeline:

    1️⃣ Slack → URLs
    2️⃣ URLs → Crawled
    3️⃣ Crawled → Analysis

Optionally, can run individual stages or all combined.
============================================================
"""

import asyncio
from pathlib import Path
from loguru import logger

from src.pipelines.slack_to_urls import SlackToUrlsPipeline
from src.pipelines.urls_to_crawled import UrlsToCrawledPipeline
from src.pipelines.crawled_to_analysis import CrawledToAnalysisPipeline


class ThreatIntelPipeline:
    """Unified orchestrator chaining all three intelligence pipelines."""

    def __init__(
        self,
        channel_name: str = "threat-intelligence",
        limit: int = 10,
        headless: bool = True,
        intermediate_dir: str | Path | None = None,
    ):
        self.channel_name = channel_name
        self.limit = limit
        self.headless = headless
        self.intermediate_dir = Path(intermediate_dir) if intermediate_dir else None

    # ============================================================
    # 🚀 Run all stages end-to-end
    # ============================================================
    async def run_full(self) -> Path:
        logger.info("🚀 Starting full Threat Intelligence pipeline chain")

        # 1️⃣ Slack → URLs
        urls_path = await SlackToUrlsPipeline(
            channel_name=self.channel_name,
            limit=self.limit,
        ).run_with_logging()

        # 2️⃣ URLs → Crawled
        crawled_path = await UrlsToCrawledPipeline(
            urls_path=urls_path,
            headless=self.headless,
        ).run_with_logging()

        # 3️⃣ Crawled → Analysis
        analysis_path = await CrawledToAnalysisPipeline(
            input_path=crawled_path,
        ).run_with_logging()

        logger.success(f"🎯 Threat Intelligence pipeline completed → {analysis_path}")
        return Path(analysis_path)

    # ============================================================
    # ⚙️ Run individual stages manually
    # ============================================================
    async def run_stage(self, stage: str):
        """Run a specific stage only (useful for debugging)."""
        stage = stage.lower()

        if stage == "slack_to_urls":
            return await SlackToUrlsPipeline(
                channel_name=self.channel_name,
                limit=self.limit,
            ).run_with_logging()

        elif stage == "crawled_to_analysis":
            crawled_path = self._latest_intermediate("results")
            return await CrawledToAnalysisPipeline(
                input_path=str(crawled_path),  # ✅ cast Path → str
            ).run_with_logging()


        elif stage == "crawled_to_analysis":
            crawled_path = self._latest_intermediate("results")
            return await CrawledToAnalysisPipeline(
                input_path=crawled_path,
            ).run_with_logging()

        else:
            raise ValueError(f"Unknown stage: {stage}")

    # ============================================================
    # 🧩 Utility — find last intermediate files
    # ============================================================
    def _latest_intermediate(self, keyword: str) -> Path:
        """Try to locate the latest intermediate JSON file."""
        search_dir = (
            self.intermediate_dir
            or Path(__file__).resolve().parents[2] / "data" / "slack_channel_export"
        )
        candidates = sorted(
            search_dir.glob(f"*{keyword}*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(
                f"No intermediate file containing '{keyword}' found in {search_dir}"
            )
        logger.info(f"📂 Using latest intermediate: {candidates[0].name}")
        return candidates[0]
