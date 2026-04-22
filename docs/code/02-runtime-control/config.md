# `music_metadata/runtime_control/config.py`

Source file: [music_metadata/runtime_control/config.py](/C:/Users/Drew/Desktop/MusicScanIter/music_metadata/runtime_control/config.py)

## Purpose

This module loads `.env`, normalizes environment values, validates required settings, and returns a `Settings` object.

## Main Functions

- `to_bool(value, default=True)`: converts env-style strings like `true`, `1`, or `yes` into booleans
- `load_settings()`: loads environment variables, validates them, creates the target directory if needed, and returns `Settings`

## Environment Variables Used

- `RESEARCH_PROVIDER`
- `RESEARCH_MODEL`
- `RESEARCH_API_KEY`
- `MUSIC_DIR`
- `TARGET_DIR`
- `DRY_RUN`

## Configuration Rules

- `RESEARCH_PROVIDER` must currently be `gemini`
- `RESEARCH_MODEL` defaults to `gemma-4-31b-it`
- `RESEARCH_API_KEY` is required
- `MUSIC_DIR` is required and must exist as a directory
- `TARGET_DIR` is optional and defaults to `MUSIC_DIR`
- `TARGET_DIR` is created automatically when needed
- `DRY_RUN` is parsed into the returned `Settings` object

## Example `.env`

```env
RESEARCH_PROVIDER=gemini
RESEARCH_MODEL=gemma-4-31b-it
RESEARCH_API_KEY=YOUR_API_KEY
MUSIC_DIR=C:/Users/Drew/Music
TARGET_DIR=C:/Users/Drew/Music/Organized
DRY_RUN=true
```

## Testing Focus

- invalid provider values should raise `ValueError`
- missing `RESEARCH_API_KEY` should raise `ValueError`
- missing or invalid `MUSIC_DIR` should raise `ValueError`
- omitted `TARGET_DIR` should resolve to `MUSIC_DIR`
- `DRY_RUN` parsing should behave correctly for common true-like values

## Mermaid

```mermaid
flowchart LR
    env[".env"] --> load["load_settings()"]
    load --> validate["path and provider validation"]
    validate --> settings["Settings dataclass"]
    settings --> cli["runtime_control/cli.py"]
```

## Notes

- The current implementation only accepts `RESEARCH_PROVIDER=gemini`.
- `TARGET_DIR` defaults to `MUSIC_DIR` when omitted.
- `DRY_RUN` is parsed here but not honored later by `metadata_processing/service.py`.
