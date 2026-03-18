"""CutAI configuration management.

Config file location: ~/.cutai/config.yaml
Environment variables override config file values.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".cutai"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
FFMPEG_PATH = os.environ.get("CUTAI_FFMPEG_PATH", "/opt/homebrew/bin/ffmpeg")
FFPROBE_PATH = os.environ.get("CUTAI_FFPROBE_PATH", "/opt/homebrew/bin/ffprobe")


class CutAIConfig(BaseModel):
    """Application configuration."""

    openai_api_key: str = Field(default="", description="OpenAI API key")
    default_whisper_model: str = Field(default="base", description="Whisper model size")
    default_llm: str = Field(default="gpt-4o", description="Default LLM model")
    output_dir: str = Field(default="./output", description="Default output directory")
    ffmpeg_path: str = Field(default=FFMPEG_PATH, description="Path to FFmpeg binary")
    ffprobe_path: str = Field(default=FFPROBE_PATH, description="Path to FFprobe binary")


def load_config() -> CutAIConfig:
    """Load configuration from file and environment variables.

    Priority (highest first):
    1. Environment variables (OPENAI_API_KEY, CUTAI_WHISPER_MODEL, etc.)
    2. Config file (~/.cutai/config.yaml)
    3. Defaults
    """
    file_values: dict = {}

    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                file_values = yaml.safe_load(f) or {}
            logger.debug("Loaded config from %s", CONFIG_PATH)
        except Exception as exc:
            logger.warning("Failed to read config file %s: %s", CONFIG_PATH, exc)

    # Environment variable overrides
    env_map = {
        "OPENAI_API_KEY": "openai_api_key",
        "CUTAI_WHISPER_MODEL": "default_whisper_model",
        "CUTAI_LLM": "default_llm",
        "CUTAI_OUTPUT_DIR": "output_dir",
        "CUTAI_FFMPEG_PATH": "ffmpeg_path",
        "CUTAI_FFPROBE_PATH": "ffprobe_path",
    }

    for env_key, config_key in env_map.items():
        value = os.environ.get(env_key)
        if value is not None:
            file_values[config_key] = value

    return CutAIConfig(**file_values)


def save_config(config: CutAIConfig) -> None:
    """Save configuration to ~/.cutai/config.yaml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(exclude_defaults=False)
    # Don't persist the API key to disk if it came from env
    if os.environ.get("OPENAI_API_KEY") and data.get("openai_api_key"):
        data.pop("openai_api_key", None)
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)
    logger.info("Config saved to %s", CONFIG_PATH)


def ensure_ffmpeg(config: CutAIConfig | None = None) -> str:
    """Verify FFmpeg is available and return its path.

    Raises:
        FileNotFoundError: If FFmpeg binary is not found.
    """
    path = (config or load_config()).ffmpeg_path
    if not Path(path).exists():
        # Try PATH lookup as fallback
        import shutil

        found = shutil.which("ffmpeg")
        if found:
            return found
        raise FileNotFoundError(
            f"FFmpeg not found at '{path}' and not in PATH. "
            "Install FFmpeg: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
        )
    return path


def ensure_ffprobe(config: CutAIConfig | None = None) -> str:
    """Verify FFprobe is available and return its path."""
    path = (config or load_config()).ffprobe_path
    if not Path(path).exists():
        import shutil

        found = shutil.which("ffprobe")
        if found:
            return found
        raise FileNotFoundError(
            f"FFprobe not found at '{path}' and not in PATH. "
            "Install FFmpeg (includes FFprobe): brew install ffmpeg"
        )
    return path
