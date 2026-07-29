import librosa
import numpy as np

KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def calculate_key(y: np.ndarray, sr: int) -> str:
    """クロマ特徴と調性プロファイルから major / minor を推定する。"""
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    major_scores = [np.corrcoef(chroma, np.roll(MAJOR_PROFILE, index))[0, 1] for index in range(12)]
    minor_scores = [np.corrcoef(chroma, np.roll(MINOR_PROFILE, index))[0, 1] for index in range(12)]
    major_index = int(np.argmax(major_scores))
    minor_index = int(np.argmax(minor_scores))
    if major_scores[major_index] >= minor_scores[minor_index]:
        return f"{KEYS[major_index]} major"
    return f"{KEYS[minor_index]} minor"
