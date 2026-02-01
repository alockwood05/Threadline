"""Configuration settings using Pydantic."""

from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
import yaml


class EmbeddingConfig(BaseModel):
    """Embedding model configuration."""

    model: str = "sentence-transformers/all-MiniLM-L6-v2"


class ClassificationConfig(BaseModel):
    """Entry classification configuration."""

    method: str = "local"  # 'local' or 'llm'
    model: str = "facebook/bart-large-mnli"
    labels: list[str] = Field(
        default_factory=lambda: [
            "thought",
            "todo list",
            "summary",
            "bullet list",
            "prayer",
            "reflection",
            "question",
        ]
    )
    confidence_threshold: float = 0.6


class TitleConfig(BaseModel):
    """Title generation configuration."""

    method: str = "local"  # 'local' or 'llm'


class OCRConfig(BaseModel):
    """OCR configuration."""

    default: str = "pytesseract"
    handwriting: str = "trocr"


class ThemeConfig(BaseModel):
    """Theme extraction configuration."""

    min_topic_size: int = 5
    nr_topics: str | int = "auto"


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "ollama"
    model: str = "llama3.2"
    api_key_env: str | None = None


class TUIConfig(BaseModel):
    """TUI display configuration."""

    page_size: int = 50
    date_format: str = "%Y-%m-%d"
    theme: str = "dark"


class StorageConfig(BaseModel):
    """Storage paths configuration."""

    path: str = "~/.threadline"
    backup_path: str = "~/.threadline/backups"


class Settings(BaseModel):
    """Root configuration object."""

    mode: str = "local"  # 'local' or 'hybrid'
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    classification: ClassificationConfig = Field(default_factory=ClassificationConfig)
    titles: TitleConfig = Field(default_factory=TitleConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    themes: ThemeConfig = Field(default_factory=ThemeConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tui: TUIConfig = Field(default_factory=TUIConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


def load_settings(config_path: Path | None = None) -> Settings:
    """Load settings from config file, falling back to defaults."""
    if config_path is None:
        from threadline.config.paths import get_config_path

        config_path = get_config_path()

    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
            return Settings(**data)

    return Settings()


def save_settings(settings: Settings, config_path: Path | None = None) -> None:
    """Save settings to config file."""
    if config_path is None:
        from threadline.config.paths import get_config_path

        config_path = get_config_path()

    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(settings.model_dump(), f, default_flow_style=False, sort_keys=False)
