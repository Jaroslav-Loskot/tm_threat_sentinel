import asyncio
from typing import Optional
from src.services.slack_manager import extract_urls_from_channel
from src.utils.file_utils import save_json
from src.utils.path_utils import get_data_path
from src.pipelines.base_pipeline import BasePipeline


class SlackToUrlsPipeline(BasePipeline):
    name = "Slack → URLs"

    def __init__(self, channel_name: str, limit: Optional[int] = 10):
        super().__init__(channel_name=channel_name, limit=limit)
        self.channel_name = channel_name
        self.limit = limit

    async def execute(self) -> str:
        urls = await extract_urls_from_channel(self.channel_name, limit=self.limit)
        out_path = get_data_path(f"{self.channel_name}_urls.json")
        save_json(urls, out_path)
        return str(out_path)
