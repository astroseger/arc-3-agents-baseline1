from __future__ import annotations

from pathlib import Path

from frame_plot_lib import save_ascii_frame_png
from load_initial_full_frame import INITIAL_FULL_FRAMES_DIR, load_initial_full_frame

def plot_initial_full_frames() -> list[Path]:
    written_png_paths: list[Path] = []
    if not INITIAL_FULL_FRAMES_DIR.is_dir():
        return written_png_paths

    for ascii_path in sorted(INITIAL_FULL_FRAMES_DIR.glob("level_*.txt")):
        level_index = int(ascii_path.stem.removeprefix("level_"))
        frame = load_initial_full_frame(level_index)
        if frame is None:
            continue
        png_path = ascii_path.with_suffix(".png")
        save_ascii_frame_png(frame, png_path)
        written_png_paths.append(png_path)
    return written_png_paths


def main() -> int:
    written_png_paths = plot_initial_full_frames()
    if not written_png_paths:
        print("plot_initial_full_frames.py: no initial_full_frames/level_*.txt files found")
        return 0

    print("plot_initial_full_frames.py: wrote PNG files")
    for png_path in written_png_paths:
        print(png_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
