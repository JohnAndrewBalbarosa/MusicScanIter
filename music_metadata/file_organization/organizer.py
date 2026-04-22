import os
import re
import shutil
from pathlib import Path

from music_metadata.runtime_control.types import OrganizeStrategy

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def sanitize_component(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*]", " ", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(".")
    if not cleaned:
        cleaned = fallback

    if cleaned.upper() in _WINDOWS_RESERVED_NAMES:
        cleaned = f"{cleaned}_"

    return cleaned[:120]


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _unique_destination(destination: Path, source_path: Path) -> Path:
    if not destination.exists() or _same_path(destination, source_path):
        return destination

    base = destination.stem
    suffix = destination.suffix
    counter = 1
    while True:
        candidate = destination.with_name(f"{base} ({counter}){suffix}")
        if not candidate.exists() or _same_path(candidate, source_path):
            return candidate
        counter += 1


def build_destination_path(
    source_path: Path,
    source_root: Path,
    target_root: Path,
    strategy: OrganizeStrategy,
    title: str,
    primary_artist: str,
    album: str,
    rename_to_title: bool,
) -> Path:
    if strategy == "artist_album":
        artist = sanitize_component(primary_artist, "Unknown Artist")
        album_name = sanitize_component(album, "Unknown Album")
        destination_dir = target_root / artist / album_name
    elif strategy == "flat":
        destination_dir = target_root
    elif strategy == "skip":
        destination_dir = source_path.parent
    else:
        try:
            relative_parent = source_path.parent.relative_to(source_root)
        except ValueError:
            relative_parent = Path()
        destination_dir = target_root / relative_parent

    if rename_to_title:
        new_stem = sanitize_component(title, source_path.stem)
    else:
        new_stem = sanitize_component(source_path.stem, source_path.stem)

    return destination_dir / f"{new_stem}{source_path.suffix.lower()}"


def relocate_file(source_path: Path, destination_path: Path, dry_run: bool) -> Path:
    final_destination = _unique_destination(destination_path, source_path)

    if dry_run:
        return final_destination

    final_destination.parent.mkdir(parents=True, exist_ok=True)
    if _same_path(source_path, final_destination):
        return final_destination

    shutil.move(str(source_path), str(final_destination))
    return final_destination
