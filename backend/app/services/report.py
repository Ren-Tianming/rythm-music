from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.models import SongAnalysis


def create_analysis_report(analysis: SongAnalysis, username: str) -> BytesIO:
    """解析詳細を共有用 PDF として描画する。"""
    fig = plt.figure(figsize=(11.7, 8.3), facecolor="#090516")
    grid = fig.add_gridspec(3, 2, height_ratios=[0.8, 1.4, 1.4], hspace=0.5, wspace=0.3)
    title = fig.add_subplot(grid[0, :])
    title.axis("off")
    title.text(0, 0.8, "RyThM Music / Audio Analysis Report", color="#ff3cac", fontsize=20, weight="bold")
    title.text(0, 0.32, f"{analysis.original_filename}   |   ユーザー: {username}", color="#dbe7ff", fontsize=11)
    metrics = fig.add_subplot(grid[1, 0])
    metrics.axis("off")
    detail = (
        f"BPM      {analysis.bpm}\n"
        f"調性     {analysis.musical_key}\n"
        f"Genre   {analysis.genre or 'Not configured'}\n"
        f"再生時間 {analysis.duration_sec}s\n"
        f"LUFS     {analysis.lufs}\n"
        f"RMS      {analysis.rms}\n"
        f"形式     {analysis.file_format.upper()} / {analysis.sample_rate}Hz / {analysis.channels}ch"
    )
    metrics.text(0.02, 0.95, detail, va="top", color="#eef3ff", fontsize=12, linespacing=1.7)
    waveform = fig.add_subplot(grid[1, 1])
    waveform.set_facecolor("#100826")
    waveform.plot(analysis.waveform or [], color="#00e5ff", linewidth=1)
    waveform.set_title("波形", color="#ff3cac")
    spectrogram = fig.add_subplot(grid[2, :])
    spectrogram.set_facecolor("#100826")
    spectrogram.imshow(np.array(analysis.spectrogram or [[0]]), aspect="auto", origin="lower", cmap="magma")
    spectrogram.set_title("スペクトログラム", color="#ff3cac")
    for axis in (waveform, spectrogram):
        axis.tick_params(colors="#7890bb")
        for spine in axis.spines.values():
            spine.set_color("#32145f")
    output = BytesIO()
    fig.savefig(output, format="pdf", facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output
