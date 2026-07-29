from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class SummaryResult:
    text: str
    source: str


def _local_summary(analysis: dict[str, object]) -> str:
    genre = analysis.get("genre") or "unclassified genre"
    bpm = analysis.get("bpm") or "unknown tempo"
    musical_key = analysis.get("musical_key") or "unknown key"
    loudness = analysis.get("lufs")
    loudness_text = f", {loudness} LUFS" if loudness is not None else ""
    return f"{genre} / {bpm} BPM / {musical_key}{loudness_text}. External AI commentary is not configured."


def create_music_summary(analysis: dict[str, object]) -> SummaryResult:
    settings = get_settings()
    local = _local_summary(analysis)
    if not settings.llm_api_key:
        return SummaryResult(local, "LOCAL")
    prompt = (
        "Analyze this song for a music creator. Be concise, factual, and avoid claiming certainty. "
        f"Metrics: BPM={analysis.get('bpm')}, key={analysis.get('musical_key')}, "
        f"genre={analysis.get('genre')}, LUFS={analysis.get('lufs')}. "
        f"Lyrics: {str(analysis.get('lyrics') or '')[:4000]}"
    )
    try:
        with httpx.Client(timeout=45) as client:
            response = client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 450,
                },
            )
            response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()
        return SummaryResult(text, "EXTERNAL_LLM")
    except Exception:
        return SummaryResult(local, "LOCAL_FALLBACK")
