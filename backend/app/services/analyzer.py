from pathlib import Path

import librosa
import numpy as np
import pyloudnorm as pyln

from app.audio.bpm import calculate_bpm
from app.audio.key import calculate_key
from app.audio.spectrogram import get_spectrogram
from app.audio.waveform import get_waveform
from app.core.config import get_settings
from app.core.errors import AppError
from app.services.genre import predict_genre
from app.services.lyrics import extract_lyrics
from app.services.summary import create_music_summary

settings = get_settings()


def analyze_audio(path: Path) -> dict[str, object]:
    """音源を一度だけロードして解析結果と可視化用データを生成する。"""
    try:
        raw, sr = librosa.load(path, sr=None, mono=False)
    except Exception as exc:
        raise AppError(422, "AUDIO_ANALYSIS_FAILED", "音源を読み込めませんでした。") from exc

    sample_rate = int(sr)
    channels = 1 if raw.ndim == 1 else raw.shape[0]
    y = raw if raw.ndim == 1 else librosa.to_mono(raw)
    duration = float(librosa.get_duration(y=y, sr=sample_rate))
    if duration > settings.max_audio_duration_sec:
        raise AppError(413, "AUDIO_TOO_LONG", "音源の長さが上限を超えています。")
    if y.size == 0:
        raise AppError(422, "AUDIO_ANALYSIS_FAILED", "音源データが空です。")

    rms = float(np.sqrt(np.mean(np.square(y))))
    try:
        loudness = float(pyln.Meter(sample_rate).integrated_loudness(y))
    except ValueError:
        loudness = float(20 * np.log10(max(rms, 1e-12)))

    genre = predict_genre(y, sample_rate)
    lyrics = extract_lyrics(path)
    result: dict[str, object] = {
        "file_format": path.suffix.removeprefix(".").lower(),
        "duration_sec": round(duration, 3),
        "sample_rate": sample_rate,
        "channels": channels,
        "bpm": calculate_bpm(y, sample_rate),
        "musical_key": calculate_key(y, sample_rate),
        "rms": round(rms, 6),
        "lufs": round(loudness, 3),
        "waveform": get_waveform(y),
        "spectrogram": get_spectrogram(y, sample_rate),
        "genre": genre.genre,
        "genre_confidence": genre.confidence,
        "genre_model_status": genre.status,
        "genre_model_version": genre.model_version,
        "lyrics": lyrics.text,
        "lyrics_status": lyrics.status,
    }
    summary = create_music_summary(result)
    result["ai_summary"] = summary.text
    result["ai_summary_source"] = summary.source
    return result
