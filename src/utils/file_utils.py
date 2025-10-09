import json
from pathlib import Path

def load_json(path: str | Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path: str | Path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
