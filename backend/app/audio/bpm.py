import librosa
import numpy as np


def calculate_bpm(y: np.ndarray, sr: int) -> int:
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return round(float(np.asarray(tempo).reshape(-1)[0]))
