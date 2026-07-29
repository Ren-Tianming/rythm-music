from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class LyricsResult:
    text: str | None
    status: str


def extract_lyrics(path: Path) -> LyricsResult:
    """Use an OpenAI-compatible transcription endpoint only when configured."""
    settings = get_settings()
    if not settings.lyrics_api_url or not settings.lyrics_api_key:
        return LyricsResult(None, "NOT_CONFIGURED")
    try:
        with path.open("rb") as audio_file, httpx.Client(timeout=120) as client:
            response = client.post(
                settings.lyrics_api_url,
                headers={"Authorization": f"Bearer {settings.lyrics_api_key}"},
                data={"model": settings.lyrics_model, "response_format": "json"},
                files={"file": (path.name, audio_file, "application/octet-stream")},
            )
            response.raise_for_status()
        text = str(response.json().get("text", "")).strip()
        return LyricsResult(text or None, "READY" if text else "EMPTY")
    except Exception:
        return LyricsResult(None, "PROVIDER_ERROR")
