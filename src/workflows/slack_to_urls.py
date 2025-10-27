# src/pipelines/slack_to_urls.py
from typing import Optional
from src.core.slack_manager import extract_urls_from_channel
from src.utils.file_utils import save_json
from src.utils.path_utils import get_data_path

async def run_slack_to_urls(channel_name: str, limit: Optional[int]) -> str:
    urls = await extract_urls_from_channel(channel_name, limit=limit)
    out_path = str(get_data_path(f"{channel_name}_urls.json"))
    save_json(urls, out_path)
    return out_path
