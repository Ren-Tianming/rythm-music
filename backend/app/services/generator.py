import hashlib
from dataclasses import dataclass
from uuid import uuid4

import httpx
import numpy as np
import soundfile as sf

from app.core.config import get_settings
from app.core.errors import AppError


@dataclass(frozen=True)
class GenerationResult:
    title: str
    provider: str
    status: str
    audio_url: str | None
    provider_job_id: str | None
    duration_sec: int


def _demo_generation(prompt: str, duration_sec: int) -> GenerationResult:
    """Create a short procedural preview so the MVP works before provider keys are added."""
    settings = get_settings()
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    sample_rate = 22050
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    roots = [110.0, 130.81, 146.83, 164.81, 196.0]
    root = roots[seed % len(roots)]
    progression = [1.0, 4 / 3, 3 / 2, 6 / 5]
    segment_count = 4
    segment_samples = int(sample_rate * duration_sec / segment_count)
    chunks: list[np.ndarray] = []
    for ratio in progression:
        t = np.arange(segment_samples, dtype=np.float32) / sample_rate
        fundamental = root * ratio
        chord = sum(np.sin(2 * np.pi * fundamental * interval * t) for interval in (1.0, 1.25, 1.5))
        pulse = 0.35 + 0.65 * (np.sin(2 * np.pi * (2 + seed % 3) * t) > 0).astype(np.float32)
        sparkle = 0.08 * rng.normal(size=segment_samples) * np.exp(-3 * (t % 0.5))
        envelope = np.minimum(t * 8, 1.0) * np.minimum((t[::-1]) * 8, 1.0)
        chunks.append(((0.12 * chord * pulse + sparkle) * envelope).astype(np.float32))
    audio = np.concatenate(chunks)
    audio /= max(float(np.max(np.abs(audio))), 1.0)
    filename = f"demo-{uuid4().hex}.wav"
    sf.write(settings.generated_dir / filename, audio, sample_rate, subtype="PCM_16")
    title = prompt.strip().splitlines()[0][:60] or "RyThM Demo"
    return GenerationResult(title, "demo", "SUCCESS", f"/media/generated/{filename}", None, duration_sec)


def _external_generation(prompt: str, instrumental: bool, duration_sec: int) -> GenerationResult:
    settings = get_settings()
    if not settings.music_api_url or not settings.music_api_key:
        raise AppError(503, "MUSIC_PROVIDER_NOT_CONFIGURED", "Music generation API is not configured.")
    try:
        with httpx.Client(timeout=120) as client:
            response = client.post(
                settings.music_api_url,
                headers={"Authorization": f"Bearer {settings.music_api_key}"},
                json={"prompt": prompt, "instrumental": instrumental, "duration_seconds": duration_sec},
            )
            response.raise_for_status()
        payload = response.json()
        return GenerationResult(
            title=str(payload.get("title") or prompt[:60]),
            provider=settings.music_provider,
            status=str(payload.get("status", "PROCESSING")),
            audio_url=payload.get("audio_url"),
            provider_job_id=str(payload.get("id")) if payload.get("id") is not None else None,
            duration_sec=duration_sec,
        )
    except AppError:
        raise
    except Exception as exc:
        raise AppError(502, "MUSIC_PROVIDER_ERROR", "Music generation provider request failed.") from exc


def generate_music(prompt: str, instrumental: bool, duration_sec: int) -> GenerationResult:
    settings = get_settings()
    if settings.music_provider.lower() == "demo":
        return _demo_generation(prompt, duration_sec)
    return _external_generation(prompt, instrumental, duration_sec)


def get_generation_status(provider_job_id: str, duration_sec: int) -> GenerationResult:
    """Poll an OpenAI-compatible provider status endpoint for an asynchronous job."""
    settings = get_settings()
    if not settings.music_api_key:
        raise AppError(503, "MUSIC_PROVIDER_NOT_CONFIGURED", "Music generation API is not configured.")
    template = settings.music_status_url or (
        f"{settings.music_api_url.rstrip('/')}/{{job_id}}" if settings.music_api_url else None
    )
    if not template:
        raise AppError(503, "MUSIC_STATUS_NOT_CONFIGURED", "Music generation status endpoint is not configured.")
    url = template.replace("{job_id}", provider_job_id)
    try:
        with httpx.Client(timeout=45) as client:
            response = client.get(url, headers={"Authorization": f"Bearer {settings.music_api_key}"})
            response.raise_for_status()
        payload = response.json()
        return GenerationResult(
            title=str(payload.get("title") or "RyThM Generation"),
            provider=settings.music_provider,
            status=str(payload.get("status", "PROCESSING")).upper(),
            audio_url=payload.get("audio_url"),
            provider_job_id=provider_job_id,
            duration_sec=int(payload.get("duration_seconds") or duration_sec),
        )
    except Exception as exc:
        raise AppError(502, "MUSIC_PROVIDER_ERROR", "Music generation provider status request failed.") from exc
