"""
Base pipeline utilities and abstractions.
Each pipeline stage should subclass BasePipeline
and implement `execute()`.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger
import asyncio


class BasePipeline(ABC):
    """Abstract base for all pipeline steps."""

    name: str = "BasePipeline"

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @abstractmethod
    async def execute(self) -> Any:
        """Run the pipeline step."""
        ...

    @staticmethod
    def ensure_path(path: str | Path) -> Path:
        """Ensure file or directory exists."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"❌ Path not found: {p}")
        return p

    async def run_with_logging(self) -> Any:
        """Wrapper with logging and timing."""
        import time

        start = time.time()
        logger.info(f"🚀 Starting pipeline: {self.name}")
        try:
            result = await self.execute()
            elapsed = time.time() - start
            logger.success(f"✅ Finished {self.name} in {elapsed:.2f}s")
            return result
        except Exception as e:
            logger.error(f"❌ {self.name} failed: {e}")
            raise
