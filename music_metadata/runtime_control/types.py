from dataclasses import dataclass
from pathlib import Path
from typing import Literal


OrganizeStrategy = Literal["retain", "artist_album", "flat", "skip"]


@dataclass
class Settings:
    provider: str
    model_name: str
    api_key: str
    music_dir: Path
    target_dir: Path
    dry_run: bool


@dataclass
class CliOptions:
    limit: int
    apply: bool
    only_missing: bool
    min_confidence: float
    organize_strategy: OrganizeStrategy
    target_dir: Path
    rename_to_title: bool
