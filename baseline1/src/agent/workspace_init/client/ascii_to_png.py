from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

COLOR_MAP: dict[int, str] = {
    0: "#FFFFFFFF",
    1: "#CCCCCCFF",
    2: "#999999FF",
    3: "#666666FF",
    4: "#333333FF",
    5: "#000000FF",
    6: "#E53AA3FF",
    7: "#FF7BCCFF",
    8: "#F93C31FF",
    9: "#1E93FFFF",
    10: "#88D8F1FF",
    11: "#FFDC00FF",
    12: "#FF851BFF",
    13: "#921231FF",
    14: "#4FCC30FF",
    15: "#A356D6FF",
}
DEFAULT_PNG_SCALE = 8


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def frame_to_rgb_array(frame: np.ndarray, scale: int = DEFAULT_PNG_SCALE) -> np.ndarray:
    height, width = frame.shape
    rgb_array = np.zeros((height * scale, width * scale, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            rgb = hex_to_rgb(COLOR_MAP.get(int(frame[y, x]), "#000000FF"))
            for dy in range(scale):
                for dx in range(scale):
                    rgb_array[y * scale + dy, x * scale + dx] = rgb
    return rgb_array


def parse_ascii_grid(path: Path) -> np.ndarray:
    rows: list[list[int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append([int(ch, 16) for ch in stripped])

    if not rows:
        raise ValueError(f"No frame data found in {path}")

    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError(f"Inconsistent row widths in {path}")

    return np.array(rows, dtype=np.int16)


def convert_ascii_to_png(input_path: Path, output_path: Path, scale: int) -> None:
    frame = parse_ascii_grid(input_path)
    rgb = frame_to_rgb_array(frame=frame, scale=scale)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a raw ASCII ARC frame dump into a PNG using the official ARC color map."
    )
    parser.add_argument("input", help="Path to a frame_XX.txt file.")
    parser.add_argument("--output", default=None, help="Output PNG path. Defaults to the same basename with .png.")
    parser.add_argument("--scale", type=int, default=DEFAULT_PNG_SCALE, help="Pixel upscale factor.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = Path(args.output).resolve() if args.output else input_path.with_suffix(".png")
    convert_ascii_to_png(input_path, output_path, args.scale)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
