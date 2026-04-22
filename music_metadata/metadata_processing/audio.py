import re
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp4 import MP4

SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav"}
FEATURE_REGEX = re.compile(r"\b(?:feat\.?|ft\.?|featuring|with)\s+(.+)$", re.IGNORECASE)


def discover_audio_files(music_dir: Path, limit: int | None = None) -> list[Path]:
    files = [p for p in music_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    files.sort()
    if limit and limit > 0:
        return files[:limit]
    return files


def clean_title_from_filename(file_path: Path) -> str:
    stem = file_path.stem
    stem = re.sub(r"^\d{1,3}[\s._-]*", "", stem)
    stem = stem.replace("_", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def split_artists(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r",|&| x | and ", raw, flags=re.IGNORECASE)
    cleaned = [p.strip() for p in parts if p.strip()]

    deduped: list[str] = []
    seen: set[str] = set()
    for item in cleaned:
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def infer_featured_artists(title: str) -> list[str]:
    match = FEATURE_REGEX.search(title)
    if not match:
        return []
    return split_artists(match.group(1))


def read_existing_tags(file_path: Path) -> dict[str, Any]:
    audio = MutagenFile(file_path, easy=True)
    if not audio or not audio.tags:
        return {}

    def first(key: str) -> str:
        value = audio.tags.get(key)
        if isinstance(value, list) and value:
            return str(value[0]).strip()
        if isinstance(value, str):
            return value.strip()
        return ""

    return {
        "title": first("title"),
        "album": first("album"),
        "artist": first("artist"),
        "album_artist": first("albumartist"),
        "genre": first("genre"),
        "year": first("date"),
        "track_number": first("tracknumber"),
    }


def build_merged_artist(primary_artist: str, featuring_artists: list[str]) -> str:
    merged_artist = primary_artist
    if featuring_artists:
        merged_artist = merged_artist + " feat. " + ", ".join(featuring_artists)
    return merged_artist.strip()


def compute_changes(existing: dict[str, Any], suggestion: dict[str, Any]) -> dict[str, dict[str, str]]:
    proposed = {
        "title": suggestion["title"],
        "album": suggestion["album"],
        "artist": build_merged_artist(suggestion["primary_artist"], suggestion["featuring_artists"]),
        "album_artist": suggestion["primary_artist"],
        "genre": suggestion["genre"],
        "year": suggestion["year"],
        "track_number": suggestion["track_number"],
    }

    changes: dict[str, dict[str, str]] = {}
    for key, new_value in proposed.items():
        old_value = str(existing.get(key, "")).strip()
        new_value = str(new_value).strip()
        if new_value and old_value != new_value:
            changes[key] = {"old": old_value, "new": new_value}
    return changes


def _write_mp3_tags(file_path: Path, tag_map: dict[str, str]) -> None:
    try:
        audio = EasyID3(file_path)
    except ID3NoHeaderError:
        audio = EasyID3()
        audio.save(file_path)
        audio = EasyID3(file_path)

    for key, value in tag_map.items():
        if value:
            audio[key] = [value]
    audio.save(file_path)


def _write_m4a_tags(file_path: Path, tag_map: dict[str, str]) -> None:
    audio = MP4(file_path)
    if tag_map["title"]:
        audio["\xa9nam"] = [tag_map["title"]]
    if tag_map["album"]:
        audio["\xa9alb"] = [tag_map["album"]]
    if tag_map["artist"]:
        audio["\xa9ART"] = [tag_map["artist"]]
    if tag_map["albumartist"]:
        audio["aART"] = [tag_map["albumartist"]]
    if tag_map["genre"]:
        audio["\xa9gen"] = [tag_map["genre"]]
    if tag_map["date"]:
        audio["\xa9day"] = [tag_map["date"]]

    track_number = tag_map["tracknumber"]
    if track_number:
        track_num = 0
        total = 0
        if "/" in track_number:
            left, right = track_number.split("/", 1)
            track_num = int(re.sub(r"\D", "", left) or 0)
            total = int(re.sub(r"\D", "", right) or 0)
        else:
            track_num = int(re.sub(r"\D", "", track_number) or 0)
        if track_num > 0:
            audio["trkn"] = [(track_num, total)]

    audio.save()


def write_tags(file_path: Path, suggestion: dict[str, Any]) -> None:
    tag_map = {
        "title": suggestion["title"],
        "album": suggestion["album"],
        "artist": build_merged_artist(suggestion["primary_artist"], suggestion["featuring_artists"]),
        "albumartist": suggestion["primary_artist"],
        "genre": suggestion["genre"],
        "date": suggestion["year"],
        "tracknumber": suggestion["track_number"],
    }

    suffix = file_path.suffix.lower()
    if suffix == ".mp3":
        _write_mp3_tags(file_path, tag_map)
        return

    if suffix == ".m4a":
        _write_m4a_tags(file_path, tag_map)
        return

    audio = MutagenFile(file_path)
    if audio is None:
        raise RuntimeError(f"Unsupported file type for writing tags: {file_path}")

    for key, value in tag_map.items():
        if value:
            audio[key] = [value]
    audio.save()


def has_required_metadata(existing: dict[str, Any]) -> bool:
    return bool(existing.get("title") and existing.get("artist") and existing.get("album"))
