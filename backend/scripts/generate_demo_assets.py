"""
Generates clearly-SYNTHETIC demo assets so the app has something to show
before real product photos/video exist:
  - data/sample_images/good_*.png   — a fixed fake "PCB" layout, good units
  - data/sample_images/defect_*.png — the same layout with an injected flaw
  - data/demo_video/sample_inspection.mp4 — the camera panning over one

Nothing here is real product data. Re-run any time with:
    conda run -n cognex-inspect python scripts/generate_demo_assets.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = BACKEND_DIR / "data" / "sample_images"
VIDEO_DIR = BACKEND_DIR / "data" / "demo_video"

BOARD_SIZE = (480, 640)  # h, w
# Fixed "component" positions so every "good" render is the same layout —
# a real golden-template diff detector needs this kind of consistency.
COMPONENTS = [(90, 100), (90, 220), (90, 340), (90, 460), (90, 540),
              (220, 100), (220, 220), (220, 340), (220, 460), (220, 540),
              (350, 160), (350, 300), (350, 440)]
COMPONENT_RADIUS = 22


def render_board(rng: np.random.Generator, defect: str | None = None) -> np.ndarray:
    img = np.full((*BOARD_SIZE, 3), (40, 90, 40), dtype=np.uint8)  # PCB-green background
    noise = rng.normal(0, 4, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    for i, (cy, cx) in enumerate(COMPONENTS):
        if defect == "missing" and i == 6:
            continue  # simulate a missing component
        color = (200, 200, 205)
        cv2.circle(img, (cx, cy), COMPONENT_RADIUS, color, thickness=-1)
        cv2.circle(img, (cx, cy), COMPONENT_RADIUS, (90, 90, 90), thickness=2)
        cv2.putText(img, f"{i+1}", (cx - 8, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 60, 60), 1)

    if defect == "scratch":
        cv2.line(img, (60, 300), (580, 260), (15, 15, 15), thickness=3)
    if defect == "blob":
        cv2.circle(img, (400, 200), 14, (10, 10, 120), thickness=-1)  # solder blob / burn mark

    return img


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    for i in range(8):
        cv2.imwrite(str(SAMPLE_DIR / f"good_{i:02d}.png"), render_board(rng))

    for i, defect in enumerate(["scratch", "blob", "missing", "scratch", "blob"]):
        cv2.imwrite(str(SAMPLE_DIR / f"defect_{i:02d}_{defect}.png"), render_board(rng, defect=defect))

    print(f"Wrote sample images to {SAMPLE_DIR}")

    # A short looping "inspection" clip: camera slowly pans across the board.
    video_path = VIDEO_DIR / "sample_inspection.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = 15
    out_w, out_h = 640, 480
    writer = cv2.VideoWriter(str(video_path), fourcc, fps, (out_w, out_h))
    if not writer.isOpened():
        print("ERROR: cv2.VideoWriter could not open for writing — codec unavailable", file=sys.stderr)
        sys.exit(1)

    base = render_board(rng)
    padded = cv2.copyMakeBorder(base, 40, 40, 60, 60, cv2.BORDER_REFLECT)
    n_frames = fps * 6
    for f in range(n_frames):
        t = f / n_frames
        pan_x = int(60 * (0.5 - abs(0.5 - t) * 2) * 2)  # 0 -> max -> 0 ping-pong-ish
        frame = padded[40:40 + out_h, 60 + pan_x:60 + pan_x + out_w]
        writer.write(frame)
    writer.release()
    print(f"Wrote demo video to {video_path}")


if __name__ == "__main__":
    main()
