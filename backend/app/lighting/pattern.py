"""
Direct port of `LightUI.setPattern()` from the old app (see
legacy-csharp/README.md) — black/white stripes of a tunable width, shifted
and rotated, shown on a second monitor aimed at the product. This *is* the
"pattern light" in "pattern-light defect detection": raking light across
stripe edges makes surface defects (dents, scratches, bumps) show up as
distortions in the stripe pattern.

The backend owns this as the source of truth for validation and for
generating preview/thumbnail PNGs (e.g. to embed in a saved recipe step).
The actual full-screen projection on the second monitor is rendered live by
the frontend on an HTML canvas using the same math (see
`frontend/src/lib/pattern.ts`) — redoing it in JS avoids a network round
trip for every animation frame.
"""
from __future__ import annotations

from PIL import Image


def generate_pattern(
    width_px: int,
    height_px: int,
    stripe_width: int,
    rotation_deg: int,
    shift: int,
    intensity: int,
) -> Image.Image:
    if stripe_width <= 0:
        raise ValueError("stripe_width must be > 0")
    if not 0 <= intensity <= 255:
        raise ValueError("intensity must be 0-255")

    img = Image.new("L", (width_px, height_px))
    pixels = img.load()

    # Same running-count/toggle logic as the C# original: walk columns,
    # flip between the light and dark stripe color every `stripe_width`
    # pixels, with `shift` offsetting where the first toggle happens.
    if shift == 0:
        count = 0
        white_region = False
    elif shift <= stripe_width:
        count = stripe_width - shift
        white_region = True
    else:
        count = stripe_width - (shift - stripe_width)
        white_region = False

    light = intensity
    dark = 255 - intensity
    for x in range(width_px):
        if count == stripe_width:
            white_region = not white_region
            count = 0
        count += 1
        color = light if white_region else dark
        for y in range(height_px):
            pixels[x, y] = color

    return img.rotate(rotation_deg, resample=Image.BICUBIC, expand=False, fillcolor=0)


def pattern_to_png_bytes(
    width_px: int,
    height_px: int,
    stripe_width: int,
    rotation_deg: int,
    shift: int,
    intensity: int,
) -> bytes:
    import io

    img = generate_pattern(width_px, height_px, stripe_width, rotation_deg, shift, intensity)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
