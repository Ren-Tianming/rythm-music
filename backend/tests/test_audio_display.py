import numpy as np

from app.audio import bpm, key
from app.audio.waveform import get_waveform


def test_bpm_is_rounded_to_an_integer(monkeypatch) -> None:
    monkeypatch.setattr(bpm.librosa.beat, "beat_track", lambda **_: (np.array([127.6]), None))
    assert bpm.calculate_bpm(np.zeros(32, dtype=np.float32), 44100) == 128
    assert isinstance(bpm.calculate_bpm(np.zeros(32, dtype=np.float32), 44100), int)


def test_key_uses_english_mode_names(monkeypatch) -> None:
    monkeypatch.setattr(
        key.librosa.feature,
        "chroma_cqt",
        lambda **_: np.tile(key.MAJOR_PROFILE[:, None], (1, 2)),
    )
    result = key.calculate_key(np.zeros(32, dtype=np.float32), 44100)
    assert result.endswith((" major", " minor"))
    assert "メジャー" not in result and "マイナー" not in result


def test_waveform_downsampling_preserves_peaks_instead_of_cancelling_them() -> None:
    samples = np.tile(np.array([1.0, -1.0], dtype=np.float32), 100)
    waveform = get_waveform(samples, max_points=10)
    assert len(waveform) == 10
    assert waveform == [1.0] * 10
