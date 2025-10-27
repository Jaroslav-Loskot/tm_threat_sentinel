from pathlib import Path
import os


def get_base_path() -> Path:
    """Return project base (parent of src)."""
    return Path(__file__).resolve().parents[1]


def get_data_path(filename: str) -> Path:
    """
    Resolve path for data persistence.
    - In Docker: /app/data
    - Locally:   <project_root>/data
    """
    # Prefer Docker volume
    docker_data = Path("/app/data")
    if docker_data.exists() or os.environ.get("RUNNING_IN_DOCKER"):
        data_dir = docker_data
    else:
        data_dir = get_base_path() / "data"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / filename
