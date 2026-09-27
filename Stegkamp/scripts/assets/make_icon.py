"""Draws the Stegkamp app icon and launch mark.

Run: python3 scripts/assets/make_icon.py   (requires Pillow)
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "Stegkamp" / "Resources" / "Assets.xcassets"
SCALE = 4
SIZE = 1024 * SCALE

GLOW_START = (255, 90, 54)
GLOW_END = (255, 45, 135)
WHITE = (255, 255, 255, 255)


def gradient(size):
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            pixels[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(GLOW_START, GLOW_END))
    return image


def fast_gradient(size):
    small = gradient(256)
    return small.resize((size, size), Image.BICUBIC)


def draw_ring(draw, center, radius, width, start_deg, end_deg):
    """Arc with round caps. Angles in degrees, 0 = 3 o'clock, clockwise (PIL convention)."""
    cx, cy = center
    box = [cx - radius, cy - radius, cx + radius, cy + radius]
    draw.arc(box, start_deg, end_deg, fill=WHITE, width=width)
    inner = radius - width / 2
    for angle in (start_deg, end_deg):
        a = math.radians(angle)
        px, py = cx + inner * math.cos(a), cy + inner * math.sin(a)
        r = width / 2
        draw.ellipse([px - r, py - r, px + r, py + r], fill=WHITE)


def rotated_ellipse(layer, center, size, angle, fill):
    w, h = size
    pad = int(max(w, h))
    piece = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(piece).ellipse([pad - w / 2, pad - h / 2, pad + w / 2, pad + h / 2], fill=fill)
    piece = piece.rotate(angle, resample=Image.BICUBIC)
    layer.alpha_composite(piece, (int(center[0] - pad), int(center[1] - pad)))


def footprint(layer, center, unit, angle):
    """One shoe print: a sole and a heel, pointing `angle` degrees clockwise from straight up."""
    rad = math.radians(angle)
    forward = (math.sin(rad), -math.cos(rad))
    sole_c = (center[0] + forward[0] * unit * 0.4, center[1] + forward[1] * unit * 0.4)
    heel_c = (center[0] - forward[0] * unit * 0.88, center[1] - forward[1] * unit * 0.88)
    rotated_ellipse(layer, sole_c, (unit * 1.12, unit * 1.5), -angle, WHITE)
    rotated_ellipse(layer, heel_c, (unit * 0.84, unit * 0.86), -angle, WHITE)


def mark(size, ring_width_ratio=0.085):
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    center = (size / 2, size / 2)
    radius = size * 0.34
    width = int(size * ring_width_ratio)
    # The ring is almost closed; the gap at the top right is where the steps walk out.
    heading = 40  # degrees clockwise from straight up
    gap_center = heading - 90  # PIL angles: 0 = 3 o'clock, clockwise
    draw_ring(draw, center, radius, width, gap_center + 38, gap_center + 360 - 38)

    rad = math.radians(heading)
    forward = (math.sin(rad), -math.cos(rad))
    right = (math.cos(rad), math.sin(rad))
    unit = size * 0.078
    base = (size * 0.53, size * 0.50)
    stride, spread = unit * 1.45, unit * 0.5
    left_foot = (base[0] - forward[0] * stride - right[0] * spread, base[1] - forward[1] * stride - right[1] * spread)
    right_foot = (base[0] + forward[0] * stride + right[0] * spread, base[1] + forward[1] * stride + right[1] * spread)
    footprint(layer, left_foot, unit, heading - 6)
    footprint(layer, right_foot, unit, heading + 6)
    return layer


def app_icon():
    background = fast_gradient(SIZE).convert("RGBA")
    shadow = mark(SIZE)
    alpha = shadow.split()[3].filter(ImageFilter.GaussianBlur(SIZE * 0.012))
    tint = Image.new("RGBA", (SIZE, SIZE), (120, 10, 40, 0))
    tint.putalpha(alpha.point(lambda v: int(v * 0.35)))
    background.alpha_composite(tint, (0, int(SIZE * 0.01)))
    background.alpha_composite(mark(SIZE))
    icon = background.convert("RGB").resize((1024, 1024), Image.LANCZOS)
    icon.save(ASSETS / "AppIcon.appiconset" / "AppIcon.png")


def launch_mark():
    """The launch screen shows the mark in the brand gradient on the system background."""
    for scale in (1, 2, 3):
        size = 120 * scale
        big = mark(size * SCALE)
        colored = fast_gradient(size * SCALE).convert("RGBA")
        colored.putalpha(big.split()[3])
        colored.resize((size, size), Image.LANCZOS).save(
            ASSETS / "LaunchMark.imageset" / f"LaunchMark@{scale}x.png"
        )


if __name__ == "__main__":
    app_icon()
    launch_mark()
    print("Wrote AppIcon.png and LaunchMark@1-3x.png")
