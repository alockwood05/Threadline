"""Path management for Threadline data directory."""

from pathlib import Path
import os


def get_threadline_dir() -> Path:
    """Get the Threadline data directory, respecting THREADLINE_HOME env var."""
    env_path = os.environ.get("THREADLINE_HOME")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path.home() / ".threadline"


def get_db_path() -> Path:
    """Get the path to the SQLite database."""
    return get_threadline_dir() / "threadline.db"


def get_originals_dir() -> Path:
    """Get the directory for storing original source files."""
    return get_threadline_dir() / "originals"


def get_models_dir() -> Path:
    """Get the directory for caching ML models."""
    return get_threadline_dir() / "models"


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_threadline_dir() / "config.yaml"


def get_backups_dir() -> Path:
    """Get the directory for database backups."""
    return get_threadline_dir() / "backups"


def ensure_directories() -> None:
    """Create all required directories if they don't exist."""
    dirs = [
        get_threadline_dir(),
        get_originals_dir(),
        get_models_dir(),
        get_backups_dir(),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
