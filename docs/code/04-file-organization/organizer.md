# `music_metadata/file_organization/organizer.py`

Source file: [music_metadata/file_organization/organizer.py](/C:/Users/Drew/Desktop/MusicScanIter/music_metadata/file_organization/organizer.py)

## Purpose

This module computes safe destination paths and handles file relocation.

## Main Functions

- `sanitize_component()`: removes Windows-invalid path characters and reserved names
- `_same_path()`: compares paths case-insensitively on Windows
- `_unique_destination()`: appends ` (1)`, ` (2)`, and so on when a destination already exists
- `build_destination_path()`: applies the selected organization strategy and rename policy
- `relocate_file()`: moves the file unless `dry_run` is enabled

## Supported Strategies

- `retain`
- `artist_album`
- `flat`
- `skip`

## Configuration Touchpoints

- `retain`: preserve the source-relative folder layout under the target root
- `artist_album`: place files under `TARGET_DIR/<Artist>/<Album>/`
- `flat`: place files directly under `TARGET_DIR`
- `skip`: keep the current parent folder and only rename when needed

## Testing Focus

- invalid filename characters should be removed from generated path components
- reserved Windows names should be rewritten safely
- duplicate destinations should receive ` (1)`, ` (2)`, and so on
- each organization strategy should resolve to the expected destination path
- relocation should be skipped when the source and destination are effectively the same path

## Mermaid

```mermaid
flowchart LR
    source["source file"] --> strategy["build_destination_path()"]
    strategy --> sanitize["sanitize_component()"]
    sanitize --> unique["_unique_destination()"]
    unique --> move["relocate_file()"]
```

## Notes

- Path sanitization is Windows-aware.
- `artist_album` uses normalized artist and album folder names.
- `skip` keeps the file in its current folder and only changes the filename if renaming is enabled.
