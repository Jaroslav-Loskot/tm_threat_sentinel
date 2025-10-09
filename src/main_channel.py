import asyncio
from src.pipelines.channel_monitor import monitor_channel
from src.core.slack_manager import get_channel_id_by_name
from dotenv import load_dotenv, find_dotenv
import os

_ = load_dotenv(find_dotenv())

SLACK_CHANNEL_NAME = os.getenv("SLACK_CHANNEL_NAME", "test_channel")

if __name__ == "__main__":
    
    channel_id = get_channel_id_by_name(SLACK_CHANNEL_NAME)
    asyncio.run(monitor_channel(channel_id, model_name="claude", poll_interval=60))
