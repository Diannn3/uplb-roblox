from __future__ import annotations

import math
from pathlib import Path
from typing import Any

CAMERAS = {
    "CAM_TOPDOWN": {"target": [0.0, 0.0, 0.0], "position": [0.0, 900.0, 0.0]},
    "CAM_OBLATION": {"target": [0.0, 0.0, 0.0], "position": [120.0, 80.0, 120.0]},
    "CAM_FREEDOM_PARK": {"target": [16.34, -411.74, 0.0], "position": [130.0, 80.0, 80.0]},
    "CAM_BAKER": {"target": [129.13, -359.65, 0.0], "position": [250.0, 70.0, 0.0]},
    "CAM_DL_UMALI": {"target": [-155.66, -107.55, 0.0], "position": [-30.0, 70.0, 80.0]},
    "CAM_ROAD_LEVEL": {"target": [0.0, -200.0, 0.0], "position": [150.0, 35.0, -150.0]},
}


def write_camera_config(path: Path) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CAMERAS, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def render_python_previews(objects: list[dict[str, Any]], output_dir: Path) -> list[str]:
    from PIL import Image, ImageDraw

    output_dir.mkdir(parents=True, exist_ok=True)
    names = ["topdown.png", "oblation.png", "freedom-park.png", "baker-context.png", "dl-umali-context.png", "road-level.png"]
    east_values = [float(obj["transformLocalMeters"]["eastM"]) for obj in objects]
    north_values = [float(obj["transformLocalMeters"]["northM"]) for obj in objects]
    global_west, global_east = min(east_values, default=-100.0), max(east_values, default=100.0)
    global_south, global_north = min(north_values, default=-100.0), max(north_values, default=100.0)
    camera_targets = {
        "topdown.png": ((global_west + global_east) / 2.0, (global_south + global_north) / 2.0, max(global_east - global_west, global_north - global_south, 1.0) * 1.1),
        "oblation.png": (0.0, 0.0, 220.0),
        "freedom-park.png": (16.34, -411.74, 220.0),
        "baker-context.png": (129.13, -359.65, 260.0),
        "dl-umali-context.png": (-155.66, -107.55, 240.0),
        "road-level.png": (0.0, -200.0, 320.0),
    }
    for filename in names:
        target_e, target_n, view_extent = camera_targets[filename]
        west, east = target_e - view_extent / 2.0, target_e + view_extent / 2.0
        south, north = target_n - view_extent / 2.0, target_n + view_extent / 2.0
        span_e, span_n = max(east - west, 1.0), max(north - south, 1.0)
        image = Image.new("RGB", (800, 800), (229, 235, 226))
        draw = ImageDraw.Draw(image)
        for obj in objects:
            x = int((float(obj["transformLocalMeters"]["eastM"]) - west) / span_e * 720 + 40)
            y = int((north - float(obj["transformLocalMeters"]["northM"])) / span_n * 720 + 40)
            role = obj.get("worldgenRole")
            color = {"hero": (193, 44, 44), "context-building": (117, 81, 56), "road": (50, 50, 50), "walkway": (150, 115, 75), "water": (40, 130, 180), "green-space": (74, 140, 70)}.get(role, (90, 90, 90))
            radius = 5 if role in {"road", "walkway"} else 7
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
        draw.text((20, 15), f"{filename} — semantic POC preview (Blender unavailable)", fill=(20, 20, 20))
        image.save(output_dir / filename)
    return names
