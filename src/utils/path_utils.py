from pathlib import Path

def get_base_path() -> Path:
    return Path(__file__).resolve().parents[1]

def get_data_path(filename: str) -> Path:
    base = get_base_path() / "data" / "slack_channel_export"
    base.mkdir(parents=True, exist_ok=True)
    return base / filename
