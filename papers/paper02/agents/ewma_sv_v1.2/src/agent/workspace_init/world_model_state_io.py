from __future__ import annotations

import numpy as np


def initial_state_reconstruction(level_index: int, initial_frame: np.ndarray) -> dict:
    """Placeholder initial-state reconstruction."""
    # Placeholder initial-state reconstruction.
    return {
        "level": int(level_index),
    }


def apply_render_overrides(
    frame: np.ndarray,
    state: dict,
    level_index: int,
    attempt_index: int | None,
    step_count: int | None,
) -> np.ndarray:
    """
    Verification-only escape hatch for unresolved frame-specific mismatches.

    Keep this temporary, narrow, and purely visual. Every override here should
    be treated as evidence that the actual model is still missing a mechanic or
    observation rule.
    """
    return frame


def state_renderer(state: dict) -> np.ndarray:
    """Placeholder renderer."""
    return np.zeros((64, 64), dtype=np.int16)
