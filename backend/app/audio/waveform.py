import numpy as np


def get_waveform(y: np.ndarray, max_points: int = 1200) -> list[float]:
    """正負の相殺を避け、描画用のピーク包絡を返す。"""
    samples = np.asarray(y, dtype=np.float32).reshape(-1)
    if samples.size == 0:
        return []
    frames = np.array_split(samples, min(max_points, samples.size))
    return [round(float(np.max(np.abs(frame))), 5) for frame in frames]
