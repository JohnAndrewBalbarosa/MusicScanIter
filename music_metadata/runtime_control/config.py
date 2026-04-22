import os
from pathlib import Path

from dotenv import load_dotenv

from music_metadata.runtime_control.types import Settings


def to_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    load_dotenv()

    provider = os.getenv("RESEARCH_PROVIDER", "gemini").strip().lower()
    model_name = os.getenv("RESEARCH_MODEL", "gemma-4-31b-it").strip()
    api_key = os.getenv("RESEARCH_API_KEY", "").strip()
    music_dir_raw = os.getenv("MUSIC_DIR", "").strip()
    target_dir_raw = os.getenv("TARGET_DIR", "").strip()
    dry_run = to_bool(os.getenv("DRY_RUN"), default=True)

    if provider != "gemini":
        raise ValueError(f"Unsupported RESEARCH_PROVIDER: {provider}")
    if not api_key:
        raise ValueError("Missing RESEARCH_API_KEY in .env")
    if not music_dir_raw:
        raise ValueError("Missing MUSIC_DIR in .env")

    music_dir = Path(music_dir_raw).expanduser()
    if not music_dir.exists() or not music_dir.is_dir():
        raise ValueError(f"MUSIC_DIR does not exist or is not a folder: {music_dir}")

    target_dir = Path(target_dir_raw).expanduser() if target_dir_raw else music_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        music_dir=music_dir,
        target_dir=target_dir,
        dry_run=dry_run,
    )
