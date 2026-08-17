"""Small preview renders for fixture or processed heightfields."""

from __future__ import annotations

from pathlib import Path

from .sample import HeightField


def render_preview(field: HeightField, output_path: Path, scale: int = 24) -> Path:
    from PIL import Image

    minimum, maximum = field.min_elevation_m, field.max_elevation_m
    span = max(maximum - minimum, 1e-9)
    image = Image.new("L", (field.columns * scale, field.rows * scale))
    pixels = image.load()
    for y, row in enumerate(field.values):
        for x, value in enumerate(row):
            shade = int(round(255 * (value - minimum) / span))
            for yy in range(y * scale, (y + 1) * scale):
                for xx in range(x * scale, (x + 1) * scale):
                    pixels[xx, yy] = shade
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path
