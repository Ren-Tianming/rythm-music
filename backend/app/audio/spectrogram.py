import librosa
import numpy as np


def get_spectrogram(y: np.ndarray, sr: int, max_frames: int = 180) -> list[list[float]]:
    """ブラウザ表示に適した低解像度メルスペクトログラムを生成する。"""
    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64)
    spec_db = librosa.power_to_db(mel, ref=np.max)
    if spec_db.shape[1] > max_frames:
        indexes = np.linspace(0, spec_db.shape[1] - 1, max_frames).astype(int)
        spec_db = spec_db[:, indexes]
    return [[float(value) for value in row] for row in np.round(spec_db, 2).tolist()]
