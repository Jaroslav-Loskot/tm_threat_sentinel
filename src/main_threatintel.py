import asyncio
from loguru import logger
from dotenv import load_dotenv
from src.pipelines.channel_monitor import ChannelMonitorPipeline
from src.services.slack_manager import get_channel_id_by_name
import os

load_dotenv()

CHANNEL_NAME = os.getenv("SLACK_CHANNEL_NAME","")
ALERT_EMAILS = os.getenv("SLACK_CHANNEL_NAME", "").split(",")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

async def main():
    # ✅ you can use channel name instead of ID
    channel_id = get_channel_id_by_name(CHANNEL_NAME)

    monitor = ChannelMonitorPipeline(
        channel_id=channel_id,
        poll_interval=POLL_INTERVAL,  # check every 60s
        alert_emails=ALERT_EMAILS,
    )

    logger.info("🚀 Starting ThreatMark Channel Monitor...")
    await monitor.execute()  # infinite loop


if __name__ == "__main__":
    asyncio.run(main())
