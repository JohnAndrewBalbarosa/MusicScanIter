import argparse
from pathlib import Path

from music_metadata.metadata_processing.research import configure_provider
from music_metadata.metadata_processing.service import process_library
from music_metadata.runtime_control.config import load_settings
from music_metadata.runtime_control.types import CliOptions, OrganizeStrategy, Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-assisted music metadata checker and tagger")
    parser.add_argument("--limit", type=int, default=0, help="Only process first N files")
    parser.add_argument("--apply", action="store_true", help="Write metadata tags to files")
    parser.add_argument("--only-missing", action="store_true", help="Only process tracks missing title/artist/album")
    parser.add_argument("--min-confidence", type=float, default=0.45, help="Skip suggestions below this score")
    parser.add_argument(
        "--organize-strategy",
        choices=["retain", "artist_album", "flat", "skip"],
        default="",
        help="Folder strategy: retain, artist_album, flat, or skip",
    )
    parser.add_argument("--target-dir", default="", help="Destination root for organized files")
    parser.add_argument(
        "--keep-filename",
        action="store_true",
        help="Keep current filename instead of renaming to the track title",
    )
    return parser.parse_args()


def _ask_strategy() -> OrganizeStrategy:
    print("\nFolder organization strategy:")
    print("1) retain       -> Keep source subfolders under target directory")
    print("2) artist_album -> Organize as target/Artist/Album")
    print("3) flat         -> Put every track directly in target directory")
    print("4) skip         -> Do not move folders (rename in place only)")

    while True:
        answer = input("Choose 1/2/3/4 [default: 1]: ").strip() or "1"
        mapping: dict[str, OrganizeStrategy] = {
            "1": "retain",
            "2": "artist_album",
            "3": "flat",
            "4": "skip",
        }
        if answer in mapping:
            return mapping[answer]
        print("Invalid choice. Please enter 1, 2, 3, or 4.")


def build_options(args: argparse.Namespace, settings: Settings) -> CliOptions:
    strategy: OrganizeStrategy
    if args.organize_strategy:
        strategy = args.organize_strategy
    else:
        try:
            strategy = _ask_strategy()
        except EOFError:
            strategy = "retain"

    default_target = settings.target_dir
    if args.target_dir:
        target_dir = Path(args.target_dir).expanduser()
    else:
        try:
            entered = input(f"Target folder [default: {default_target}]: ").strip()
        except EOFError:
            entered = ""
        target_dir = Path(entered).expanduser() if entered else default_target

    target_dir.mkdir(parents=True, exist_ok=True)

    return CliOptions(
        limit=args.limit,
        apply=args.apply,
        only_missing=args.only_missing,
        min_confidence=args.min_confidence,
        organize_strategy=strategy,
        target_dir=target_dir,
        rename_to_title=not args.keep_filename,
    )


def main() -> None:
    options = parse_args()
    settings = load_settings()
    runtime_options = build_options(options, settings)
    configure_provider(settings.api_key)
    process_library(settings, runtime_options)
