from __future__ import annotations

from pathlib import Path

import numpy as np

from session_tools import _load_ascii_frame


INITIAL_FULL_FRAMES_DIR = Path(__file__).resolve().parent / "initial_full_frames"


def get_initial_full_frame_path(level_index: int) -> Path:
    return INITIAL_FULL_FRAMES_DIR / f"level_{int(level_index)}.txt"


def load_initial_full_frame(level_index: int) -> np.ndarray | None:
    """Load the current best reconstructed initial full frame for a partly visible world."""
    frame_path = get_initial_full_frame_path(level_index)
    if not frame_path.is_file():
        return None
    return _load_ascii_frame(frame_path)
