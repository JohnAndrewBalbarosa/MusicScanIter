import json
from datetime import datetime
from pathlib import Path
from typing import Any

from music_metadata.file_organization.organizer import build_destination_path, relocate_file
from music_metadata.metadata_processing.audio import (
    compute_changes,
    discover_audio_files,
    has_required_metadata,
    read_existing_tags,
    write_tags,
)
from music_metadata.metadata_processing.research import suggest_metadata_batch
from music_metadata.runtime_control.types import CliOptions, Settings


REPORT_BATCH_SIZE = 50
MODEL_BATCH_SIZE = 50


def ensure_reports_dir() -> Path:
    reports = Path(".cache") / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports


def _chunk_records(records: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    return [records[i : i + chunk_size] for i in range(0, len(records), chunk_size)]


def write_report_batches(report: list[dict[str, Any]], reports_dir: Path, stamp: str, batch_size: int = REPORT_BATCH_SIZE) -> list[Path]:
    chunks = _chunk_records(report, batch_size) or [[]]
    paths: list[Path] = []

    for index, chunk in enumerate(chunks, start=1):
        report_path = reports_dir / f"metadata_report_{stamp}_part{index:03d}.json"
        report_path.write_text(json.dumps(chunk, indent=2, ensure_ascii=True), encoding="utf-8")
        paths.append(report_path)

    return paths


def process_library(settings: Settings, options: CliOptions) -> Path:
    # --- Caching logic: load previous model response and prompt user ---
    reports_dir = ensure_reports_dir()
    processed_files = set()
    cached_results = {}
    # Find the latest model response file
    model_response_files = sorted(reports_dir.glob("metadata_model_*.json"), reverse=True)
    user_rescan = False
    if model_response_files:
        latest_model_response = model_response_files[0]
        # Ask user if they want to rescan or continue
        print(f"Found previous model response: {latest_model_response}")
        while True:
            answer = input("Rescan all files (ignore cache)? [y/N]: ").strip().lower()
            if answer in ("y", "yes"):
                user_rescan = True
                break
            elif answer in ("n", "no", ""):
                user_rescan = False
                break
            else:
                print("Please enter 'y' or 'n'.")
        if not user_rescan:
            try:
                with latest_model_response.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    for entry in data:
                        file_path = entry.get("file")
                        scanned_by = entry.get("scanned_by")
                        if file_path and scanned_by:
                            processed_files.add(file_path)
                            cached_results[file_path] = entry
            except Exception:
                pass  # Ignore corrupt or partial files
    dry_run = False  # Always apply changes by default

    files = discover_audio_files(settings.music_dir, limit=options.limit if options.limit > 0 else None)
    if not files:
        print(f"No supported audio files found in: {settings.music_dir}")
        return Path()

    print(f"Found {len(files)} audio files in {settings.music_dir}")
    print("Mode: APPLY (writing tags)")
    print(f"Organization: {options.organize_strategy} -> {options.target_dir}")
    print("Filename mode:", "TITLE ONLY" if options.rename_to_title else "KEEP CURRENT")

    report: list[dict[str, Any]] = []
    local_song_list: list[dict[str, Any]] = []

    for index, file_path in enumerate(files, start=1):
        # Skip files already processed (cached)
        if str(file_path) in processed_files:
            print(f"[{index}/{len(files)}] Skipping already processed: {file_path.name}")
            continue

        existing = read_existing_tags(file_path)
        if options.only_missing and has_required_metadata(existing):
            print(f"[{index}/{len(files)}] Skipping complete: {file_path.name}")
            continue

        local_song_list.append(
            {
                "scan_index": index,
                "file_path": file_path,
                "existing": existing,
            }
        )

    if not local_song_list:
        print("No tracks matched the processing filters.")
        if processed_files:
            print(f"All files have already been processed and cached.")
        return Path()


    # Write pre-model scan to .cache/reports
    reports_dir = ensure_reports_dir()
    scan_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scan_report = [
        {
            "scan_index": item["scan_index"],
            "file": str(item["file_path"]),
            "existing": item["existing"],
            # Placeholder for model suggestion, will be filled after model call
            "suggestion": {},
        }
        for item in local_song_list
    ]
    scan_report_path = reports_dir / f"metadata_scan_{scan_stamp}.json"
    scan_report_path.write_text(json.dumps(scan_report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Wrote pre-model scan to: {scan_report_path}")

    # Prepare to save all model batch responses
    all_model_suggestions = []

    total_batches = (len(local_song_list) + MODEL_BATCH_SIZE - 1) // MODEL_BATCH_SIZE if local_song_list else 0

    for batch_index, start in enumerate(range(0, len(local_song_list), MODEL_BATCH_SIZE), start=1):
        batch = local_song_list[start : start + MODEL_BATCH_SIZE]
        batch_tracks = [(item["file_path"], item["existing"]) for item in batch]
        print(f"Batch {batch_index}/{total_batches}: sending {len(batch_tracks)} tracks to model")
        print(f"[Model] Sending request to model '{settings.model_name}' for batch {batch_index}...")

        try:
            suggestions = suggest_metadata_batch(settings.model_name, batch_tracks)
            print(f"[Model] Received response from model for batch {batch_index}.")
            # Save the raw suggestions for this batch
            for item, suggestion in zip(batch, suggestions):
                all_model_suggestions.append({
                    "scan_index": item["scan_index"],
                    "file": str(item["file_path"]),
                    "suggestion": suggestion,
                    "scanned_by": {
                        "model": settings.model_name,
                        "timestamp": scan_stamp
                    }
                })
        except Exception as exc:
            print(f"[Model] ERROR: Could not get response from model for batch {batch_index} ({type(exc).__name__}): {exc}")
            for item in batch:
                report.append(
                    {
                        "file": str(item["file_path"]),
                        "existing": item["existing"],
                        "suggestion": {},
                        "changes": {},
                        "applied": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            continue

        for item, suggestion in zip(batch, suggestions):
            file_path = item["file_path"]
            existing = item["existing"]
            scan_index = item["scan_index"]
            print(f"[{scan_index}/{len(files)}] Processing: {file_path.name}")

            try:
                changes = compute_changes(existing, suggestion)
                destination_path = build_destination_path(
                    source_path=file_path,
                    source_root=settings.music_dir,
                    target_root=options.target_dir,
                    strategy=options.organize_strategy,
                    title=suggestion.get("title", ""),
                    primary_artist=suggestion.get("primary_artist", ""),
                    album=suggestion.get("album", ""),
                    rename_to_title=options.rename_to_title,
                )

                destination_change = str(destination_path) != str(file_path)

                item_report = {
                    "file": str(file_path),
                    "existing": existing,
                    "suggestion": suggestion,
                    "changes": changes,
                    "destination": str(destination_path),
                    "relocated": False,
                    "applied": False,
                    "error": "",
                }

                # Update scan_report with model suggestion for this file
                for scan_item in scan_report:
                    if scan_item["file"] == str(file_path):
                        scan_item["suggestion"] = suggestion

                if suggestion["confidence"] < options.min_confidence:
                    item_report["error"] = f"Skipped due to low confidence ({suggestion['confidence']:.2f})"
                    print("  ->", item_report["error"])
                    report.append(item_report)
                    continue

                if not changes and not destination_change:
                    print("  -> No change needed")
                    report.append(item_report)
                    continue

                if dry_run:
                    print(f"  -> Suggested {len(changes)} tag updates (dry run)")
                    if destination_change:
                        print(f"  -> Planned file path: {destination_path}")
                    report.append(item_report)
                    continue

                if changes:
                    write_tags(file_path, suggestion)
                item_report["applied"] = True
                if destination_change:
                    final_path = relocate_file(file_path, destination_path, dry_run=False)
                    item_report["destination"] = str(final_path)
                    item_report["relocated"] = True
                    print(f"  -> Relocated to: {final_path}")

                print(f"  -> Applied {len(changes)} tag updates")
                report.append(item_report)

            except Exception as exc:
                print(f"  -> Error ({type(exc).__name__}): {exc}")
                report.append(
                    {
                        "file": str(file_path),
                        "existing": existing,
                        "suggestion": suggestion,
                        "changes": {},
                        "applied": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    # Save the full model batch response for caching/reference
    model_response_path = reports_dir / f"metadata_model_{scan_stamp}.json"
    model_response_path.write_text(json.dumps(all_model_suggestions, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Wrote model batch response to: {model_response_path}")

    # Update scan report with suggestions
    scan_report_path.write_text(json.dumps(scan_report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Updated scan report with model suggestions: {scan_report_path}")

    reports_dir = ensure_reports_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_paths = write_report_batches(report, reports_dir, stamp)

    applied = sum(1 for r in report if r.get("applied"))
    changed = sum(1 for r in report if r.get("changes"))
    errored = sum(1 for r in report if r.get("error"))
    print("\nSummary")
    print(f"- Tracks reviewed: {len(report)}")
    print(f"- Tracks with suggested changes: {changed}")
    print(f"- Tracks updated: {applied}")
    print(f"- Tracks skipped/errored: {errored}")
    print(f"- Report batches: {len(report_paths)} (up to {REPORT_BATCH_SIZE} tracks per file)")
    for path in report_paths:
        print(f"- Report: {path}")
    return report_paths[0]
