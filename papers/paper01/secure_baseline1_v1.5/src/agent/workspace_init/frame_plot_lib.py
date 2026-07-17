from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from client.ascii_to_png import DEFAULT_PNG_SCALE, frame_to_rgb_array


BROWN_RGB = (139, 69, 19)
MAGENTA_RGB = (255, 0, 255)
MISMATCH_RADIUS = 7


def save_ascii_frame_png(frame: np.ndarray, output_png_path: Path, scale: int = DEFAULT_PNG_SCALE) -> Path:
    rgb = frame_to_rgb_array(frame, scale=scale)
    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(output_png_path)
    return output_png_path


def _expanded_mismatch_mask(predicted_frame: np.ndarray, real_frame: np.ndarray) -> np.ndarray:
    if predicted_frame.shape != real_frame.shape:
        raise ValueError("Predicted and real frames must have the same shape.")
    mismatch = predicted_frame != real_frame
    expanded = np.zeros_like(mismatch, dtype=bool)
    height, width = mismatch.shape
    for mismatch_y, mismatch_x in np.argwhere(mismatch):
        y0 = max(0, mismatch_y - MISMATCH_RADIUS)
        y1 = min(height, mismatch_y + MISMATCH_RADIUS + 1)
        x0 = max(0, mismatch_x - MISMATCH_RADIUS)
        x1 = min(width, mismatch_x + MISMATCH_RADIUS + 1)
        for y in range(y0, y1):
            for x in range(x0, x1):
                dy = y - mismatch_y
                dx = x - mismatch_x
                if dx * dx + dy * dy <= MISMATCH_RADIUS * MISMATCH_RADIUS:
                    expanded[y, x] = True
    return expanded


def save_mismatch_region_png_v1(
    real_frame: np.ndarray,
    predicted_frame: np.ndarray,
    output_png_path: Path,
    scale: int = DEFAULT_PNG_SCALE,
) -> Path:
    # Shows only neighborhoods around mismatch pixels; everything else is plotted in brown, a color outside the game palette. This could be informative for localized mismatch, but can mislead when mismatches are spread out.
    region_mask = _expanded_mismatch_mask(predicted_frame, real_frame)
    rgb = frame_to_rgb_array(real_frame, scale=scale)
    for y in range(real_frame.shape[0]):
        for x in range(real_frame.shape[1]):
            if region_mask[y, x]:
                continue
            rgb[y * scale : (y + 1) * scale, x * scale : (x + 1) * scale] = BROWN_RGB
    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(output_png_path)
    return output_png_path


def save_mismatch_as_magneta_png_v2(
    real_frame: np.ndarray,
    predicted_frame: np.ndarray,
    output_png_path: Path,
    scale: int = DEFAULT_PNG_SCALE,
) -> Path:
    # Paints exact mismatch pixels as magenta on the full real frame; this can be more informative when mismatches are not localized.
    mismatch = predicted_frame != real_frame
    rgb = frame_to_rgb_array(real_frame, scale=scale)
    for y in range(real_frame.shape[0]):
        for x in range(real_frame.shape[1]):
            if not mismatch[y, x]:
                continue
            rgb[y * scale : (y + 1) * scale, x * scale : (x + 1) * scale] = MAGENTA_RGB
    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(output_png_path)
    return output_png_path
