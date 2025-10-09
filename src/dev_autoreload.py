import sys
from pathlib import Path
from watchfiles import run_process, Change
from loguru import logger


def main():
    # Detect correct working directory (avoid /src/src nesting)
    project_root = Path(__file__).resolve().parent
    watch_path = project_root if project_root.name == "src" else project_root / "src"

    logger.info(f"👀 Watching for code changes in: {watch_path}")
    logger.info("🔁 Auto-reload enabled — editing any .py file will restart the bot.\n")

    run_process(
        str(watch_path),
        target="uv run -m src.main_channel",
        target_type="command",  # ✅ valid values: 'function', 'command', 'auto'
        watch_filter=lambda change, path: (
            path.endswith(".py")
            and change in (Change.modified, Change.added, Change.deleted)
        ),
        debounce=1000,  # milliseconds before restart
    )


if __name__ == "__main__":
    main()
