from __future__ import annotations

from game_status import RUNNING


def world_model_engine(state: dict, action: dict) -> tuple[dict, str]:
    """Placeholder world-model dynamics."""
    return dict(state), RUNNING
