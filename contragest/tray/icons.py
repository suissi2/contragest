"""Tray icon rendering for the Contragest tray agent.

Icons are generated at runtime with Pillow — no binary assets to ship.  Each
icon is the company logo (when available, falling back to a branded circle)
with a small coloured status dot in the bottom-right corner:

    green  = service healthy (running + fresh heartbeat)
    amber  = starting / stopping / paused / heartbeat stale
    red    = service stopped / not installed
    gray   = unknown (first ticks before any probe completes)
"""

from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from contragest.tray import paths
from contragest.tray.service_state import STATUS_COLORS

# Working size; pystray scales down as needed.  Keep it square and small.
_ICON_SIZE = 64
_DOT_RADIUS = 10
_DOT_MARGIN = 3

# Fonts: Pillow's bundled font has no bold variants per size, so pick by size.
def _load_font(size: int):
    candidates = (
        os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts"),
    )
    for folder in candidates:
        if not os.path.isdir(folder):
            continue
        for name in ("PlusJakartaSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
    try:
        return ImageFont.truetype("arialbd.ttf", size)
    except Exception:
        return ImageFont.load_default(size)


def _base_icon() -> Image.Image:
    """Branded base image (logo or branded circle), square RGBA."""
    logo = paths.company_logo()
    if logo:
        try:
            img = Image.open(logo).convert("RGBA")
            img.thumbnail((_ICON_SIZE, _ICON_SIZE), Image.LANCZOS)
            # Letterbox onto a transparent square.
            canvas = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
            x = (_ICON_SIZE - img.width) // 2
            y = (_ICON_SIZE - img.height) // 2
            canvas.paste(img, (x, y), img)
            return canvas
        except Exception:
            pass  # fall through to the drawn fallback

    # Fallback: dark circle + "C".
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, _ICON_SIZE - 1, _ICON_SIZE - 1),
                 fill="#1E293B", outline="#7DD3FC", width=2)
    font = _load_font(34)
    text = "C"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((_ICON_SIZE - tw) / 2 - bbox[0], (_ICON_SIZE - th) / 2 - bbox[1]),
              text, font=font, fill="#7DD3FC")
    return img


def _status_dot(color: str) -> Image.Image:
    """Small filled circle with a dark ring (visibility on any tray theme)."""
    r = _DOT_RADIUS
    img = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, r * 2 - 1, r * 2 - 1), fill=color, outline="#0F172A", width=2)
    return img


_cache: dict = {}


def generate_icon(status: str) -> Image.Image:
    """Return a cached status-tinted tray icon (PIL RGBA image)."""
    key = status or "unknown"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    base = _base_icon().copy()
    color = STATUS_COLORS.get(key, STATUS_COLORS["unknown"])
    dot = _status_dot(color)
    dx = _ICON_SIZE - dot.width - _DOT_MARGIN
    dy = _ICON_SIZE - dot.height - _DOT_MARGIN
    base.alpha_composite(dot, (dx, dy))

    _cache[key] = base
    return base


def clear_cache() -> None:
    """Drop cached icons (useful in tests)."""
    _cache.clear()
