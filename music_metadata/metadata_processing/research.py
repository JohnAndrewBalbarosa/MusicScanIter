import json
import re
from pathlib import Path
from typing import Any

from google import genai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from music_metadata.metadata_processing.audio import clean_title_from_filename, infer_featured_artists


_GENAI_CLIENT: genai.Client | None = None


def configure_provider(api_key: str) -> None:
    global _GENAI_CLIENT
    _GENAI_CLIENT = genai.Client(api_key=api_key)


def build_prompt(file_name: str, title_guess: str, existing: dict[str, Any]) -> str:
    existing_json = json.dumps(existing, ensure_ascii=True)
    return f"""
You are a music metadata normalization assistant.

Task:
Infer the most likely canonical track metadata using the filename/title and existing tags.
Handle featured artists carefully: keep a single primary artist for canon identity, and place feature artists separately.

Input:
- File name: {file_name}
- Parsed title guess: {title_guess}
- Existing metadata: {existing_json}

Output rules:
1) Return ONLY valid JSON.
2) Use this exact schema:
{{
  "title": "string",
  "album": "string",
  "primary_artist": "string",
  "artists": ["string"],
  "featuring_artists": ["string"],
  "genre": "string",
  "year": "string",
  "track_number": "string",
  "confidence": 0.0,
  "notes": "string"
}}
3) If unknown, use empty string or empty list.
4) confidence must be between 0 and 1.
""".strip()


def build_batch_prompt(items: list[dict[str, Any]]) -> str:
    items_json = json.dumps(items, ensure_ascii=True)
    return f"""
You are a music metadata normalization assistant.

Task:
Infer canonical metadata for each track using filename/title and existing tags.
Handle featured artists carefully: keep a single primary artist for canon identity, and place feature artists separately.
Infer as much detail as possible for music categorization, including genre, publisher, parental advisory, composers, initial key, and any other relevant attributes for music organization and filtering.

Input:
- tracks: {items_json}

Output rules:
1) Return ONLY valid JSON.
2) Return this exact top-level schema:
{{
    "results": [
        {{
            "index": 0,
            "title": "string",
            "album": "string",
            "primary_artist": "string",
            "artists": ["string"],
            "featuring_artists": ["string"],
            "genre": "string",
            "publisher": "string",
            "parental_advisory": "string",  # e.g., "explicit", "clean", "none", or reason
            "composers": ["string"],
            "initial_key": "string",
            "year": "string",
            "track_number": "string",
            "confidence": 0.0,
            "notes": "string"
        }}
    ]
}}
3) Emit exactly one result per input track index.
4) Keep each result's index equal to the input index.
5) If unknown, use empty string or empty list.
6) confidence must be between 0 and 1.
""".strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def query_model(model_name: str, prompt: str) -> str:
    if _GENAI_CLIENT is None:
        raise RuntimeError("Provider is not configured. Call configure_provider first.")

    response = _GENAI_CLIENT.models.generate_content(model=model_name, contents=prompt)
    text = getattr(response, "text", "")
    if not text:
        raise RuntimeError("Model returned an empty response")
    return text


def extract_json_block(text: str) -> str:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\[{].*[\]}])\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    object_start = text.find("{")
    object_end = text.rfind("}")
    array_start = text.find("[")
    array_end = text.rfind("]")

    candidates: list[tuple[int, int]] = []
    if object_start != -1 and object_end > object_start:
        candidates.append((object_start, object_end))
    if array_start != -1 and array_end > array_start:
        candidates.append((array_start, array_end))

    if not candidates:
        raise ValueError("Could not find JSON in model output")

    start, end = min(candidates, key=lambda pair: pair[0])
    return text[start : end + 1]


def normalize_suggestion(data: dict[str, Any], title_guess: str) -> dict[str, Any]:
    title = str(data.get("title", "")).strip() or title_guess
    album = str(data.get("album", "")).strip()
    primary_artist = str(data.get("primary_artist", "")).strip()

    artists = data.get("artists", [])
    if not isinstance(artists, list):
        artists = []
    artists = [str(x).strip() for x in artists if str(x).strip()]

    featuring = data.get("featuring_artists", [])
    if not isinstance(featuring, list):
        featuring = []
    featuring = [str(x).strip() for x in featuring if str(x).strip()]

    composers = data.get("composers", [])
    if not isinstance(composers, list):
        composers = []
    composers = [str(x).strip() for x in composers if str(x).strip()]

    if not primary_artist and artists:
        primary_artist = artists[0]
    if primary_artist and primary_artist not in artists:
        artists.insert(0, primary_artist)

    confidence = data.get("confidence", 0)
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "title": title,
        "album": album,
        "primary_artist": primary_artist,
        "artists": artists,
        "featuring_artists": featuring,
        "genre": str(data.get("genre", "")).strip(),
        "publisher": str(data.get("publisher", "")).strip(),
        "parental_advisory": str(data.get("parental_advisory", "")).strip(),
        "composers": composers,
        "initial_key": str(data.get("initial_key", "")).strip(),
        "year": str(data.get("year", "")).strip(),
        "track_number": str(data.get("track_number", "")).strip(),
        "confidence": confidence,
        "notes": str(data.get("notes", "")).strip(),
    }


def suggest_metadata(model_name: str, file_path: Path, existing: dict[str, Any]) -> dict[str, Any]:
    title_guess = clean_title_from_filename(file_path)
    prompt = build_prompt(file_path.name, title_guess, existing)

    text = query_model(model_name, prompt)
    payload = extract_json_block(text)
    suggestion = normalize_suggestion(json.loads(payload), title_guess=title_guess)

    title_features = infer_featured_artists(title_guess)
    for artist in title_features:
        if artist not in suggestion["featuring_artists"]:
            suggestion["featuring_artists"].append(artist)

    if suggestion["primary_artist"] and suggestion["primary_artist"] in suggestion["featuring_artists"]:
        suggestion["featuring_artists"].remove(suggestion["primary_artist"])

    return suggestion


def suggest_metadata_batch(model_name: str, tracks: list[tuple[Path, dict[str, Any]]]) -> list[dict[str, Any]]:
    if not tracks:
        return []

    prompt_items: list[dict[str, Any]] = []
    title_guesses: list[str] = []
    for index, (file_path, existing) in enumerate(tracks):
        title_guess = clean_title_from_filename(file_path)
        title_guesses.append(title_guess)
        prompt_items.append(
            {
                "index": index,
                "file_name": file_path.name,
                "title_guess": title_guess,
                "existing": existing,
            }
        )

    prompt = build_batch_prompt(prompt_items)
    text = query_model(model_name, prompt)
    payload = extract_json_block(text)
    parsed = json.loads(payload)

    results_payload: Any
    if isinstance(parsed, dict):
        results_payload = parsed.get("results", [])
    elif isinstance(parsed, list):
        results_payload = parsed
    else:
        raise ValueError("Batch model output must be a JSON object or array")

    if not isinstance(results_payload, list):
        raise ValueError("Batch model output field 'results' must be a list")

    suggestions = [normalize_suggestion({}, title_guess=title_guesses[i]) for i in range(len(tracks))]

    for item in results_payload:
        if not isinstance(item, dict):
            continue

        try:
            output_index = int(item.get("index", -1))
        except Exception:
            continue

        if output_index < 0 or output_index >= len(tracks):
            continue

        suggestion = normalize_suggestion(item, title_guess=title_guesses[output_index])
        title_features = infer_featured_artists(title_guesses[output_index])
        for artist in title_features:
            if artist not in suggestion["featuring_artists"]:
                suggestion["featuring_artists"].append(artist)

        if suggestion["primary_artist"] and suggestion["primary_artist"] in suggestion["featuring_artists"]:
            suggestion["featuring_artists"].remove(suggestion["primary_artist"])

        suggestions[output_index] = suggestion

    return suggestions
