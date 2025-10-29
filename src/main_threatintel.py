from dotenv import load_dotenv
import os

load_dotenv(override=True)

import asyncio
from loguru import logger
from src.pipelines.channel_monitor import ChannelMonitorPipeline
from src.services.slack_manager import get_channel_id_by_name

CHANNEL_NAME = os.getenv("SLACK_CHANNEL_NAME", "")
MAX_K_MESSAGES = int(
    os.getenv("MAX_K_MESSAGES", "10")
)  # ✅ uppercase + explicit default
ALERT_EMAILS = (
    os.getenv("ALERT_EMAILS", "").split(",") if os.getenv("ALERT_EMAILS") else []
)
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

logger.debug(
    f"🔧 Env config — CHANNEL_NAME={CHANNEL_NAME}, "
    f"MAX_K_MESSAGES={MAX_K_MESSAGES}, "
    f"ALERT_EMAILS={ALERT_EMAILS}, "
    f"POLL_INTERVAL={POLL_INTERVAL}"
)


async def main():
    logger.info("🚀 Starting ThreatMark Channel Monitor...")

    try:
        channel_id = get_channel_id_by_name(CHANNEL_NAME)
        logger.debug(f"✅ Resolved channel name '{CHANNEL_NAME}' → ID {channel_id}")
    except Exception as e:
        logger.error(f"❌ Could not resolve channel '{CHANNEL_NAME}': {e}")
        return

    monitor = ChannelMonitorPipeline(
        channel_id=channel_id,
        max_k_messages=MAX_K_MESSAGES,  # ✅ explicitly pass here
        poll_interval=POLL_INTERVAL,
        alert_emails=ALERT_EMAILS,
    )

    await monitor.execute()


if __name__ == "__main__":
    logger.remove()
    logger.add(lambda msg: print(msg, end=""), level="DEBUG")
    asyncio.run(main())
