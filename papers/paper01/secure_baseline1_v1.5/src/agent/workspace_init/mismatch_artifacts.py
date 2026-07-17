from __future__ import annotations

from pathlib import Path

import numpy as np

from frame_plot_lib import save_ascii_frame_png, save_mismatch_as_magneta_png_v2, save_mismatch_region_png_v1


MISMATCH_ROOT = Path(__file__).resolve().parent / "mismatch_frames"
AUX_PLANNER_ROOT = Path(__file__).resolve().parent / "aux_planner_frames"


def frame_to_ascii(frame: np.ndarray) -> str:
    return "\n".join("".join(format(int(value), "X") for value in row) for row in frame) + "\n"


def next_mismatch_dir() -> Path:
    return next_numbered_dir(MISMATCH_ROOT)


def next_numbered_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    existing = [int(path.name) for path in root.iterdir() if path.is_dir() and path.name.isdigit()]
    next_index = max(existing, default=0) + 1
    numbered_dir = root / str(next_index)
    numbered_dir.mkdir(parents=True, exist_ok=False)
    return numbered_dir


def next_aux_planner_dir() -> Path:
    return next_numbered_dir(AUX_PLANNER_ROOT)


def save_named_frame(output_dir: Path, stem: str, frame: np.ndarray) -> tuple[Path, Path]:
    ascii_path = output_dir / f"{stem}.txt"
    png_path = output_dir / f"{stem}.png"
    ascii_path.write_text(frame_to_ascii(frame), encoding="utf-8")
    save_ascii_frame_png(frame, png_path)
    return ascii_path, png_path


def save_simulated_frame(mismatch_dir: Path, predicted_frame: np.ndarray) -> tuple[Path, Path]:
    return save_named_frame(mismatch_dir, "simulated_frame", predicted_frame)


def save_mismatch_region_png(mismatch_dir: Path, real_frame: np.ndarray, predicted_frame: np.ndarray) -> Path:
    output_path = mismatch_dir / "mismatch_region.png"
    return save_mismatch_region_png_v1(real_frame, predicted_frame, output_path)


def save_mismatch_as_magneta_png(mismatch_dir: Path, real_frame: np.ndarray, predicted_frame: np.ndarray) -> Path:
    output_path = mismatch_dir / "mismatch_as_magneta.png"
    return save_mismatch_as_magneta_png_v2(real_frame, predicted_frame, output_path)
