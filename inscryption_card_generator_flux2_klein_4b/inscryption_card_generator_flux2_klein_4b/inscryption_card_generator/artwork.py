"""Stage 12: turn generated artwork into an Act 1 card portrait.

InscryptionAPI's TextureHelper.ConvertTexture(SpriteType.CardPortrait) builds the
sprite from a fixed 114x94 rect anchored at (0, 0) and does NOT resize, so a
larger image is cropped and a smaller one is read out of bounds. The exporter
therefore always writes an exact 114x94 RGBA PNG. Vanilla portraits are drawn on
a transparent background, so a flat background colour is keyed out.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageOps

ACT1_PORTRAIT_SIZE = (114, 94)


def _border_color(img: Image.Image) -> tuple[int, int, int]:
    rgb = img.convert("RGB")
    w, h = rgb.size
    pixels = [rgb.getpixel((x, 0)) for x in range(w)] + [rgb.getpixel((x, h - 1)) for x in range(w)]
    pixels += [rgb.getpixel((0, y)) for y in range(h)] + [rgb.getpixel((w - 1, y)) for y in range(h)]
    return tuple(sorted(channel)[len(channel) // 2] for channel in zip(*pixels))  # per-channel median


def remove_flat_background(img: Image.Image, tolerance: int = 36) -> Image.Image:
    """Make the border-connected region close to the border colour transparent (flood fill)."""
    img = img.convert("RGBA")
    w, h = img.size
    bg = _border_color(img)
    px = img.load()
    seen = [[False] * h for _ in range(w)]
    queue = deque([(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)])

    def close(p) -> bool:
        return p[3] == 0 or max(abs(p[0] - bg[0]), abs(p[1] - bg[1]), abs(p[2] - bg[2])) <= tolerance

    while queue:
        x, y = queue.popleft()
        if not (0 <= x < w and 0 <= y < h) or seen[x][y]:
            continue
        seen[x][y] = True
        if not close(px[x, y]):
            continue
        px[x, y] = (0, 0, 0, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return img


def make_act1_portrait(source: Path | Image.Image, out_path: Path, remove_background: bool = True) -> Path:
    """Fit artwork inside 114x94 (aspect preserved, centred) and save as RGBA PNG."""
    img = source if isinstance(source, Image.Image) else Image.open(source)
    img = img.convert("RGBA")
    fill = _border_color(img) + (255,)
    fitted = ImageOps.contain(img, ACT1_PORTRAIT_SIZE, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", ACT1_PORTRAIT_SIZE, fill)
    canvas.alpha_composite(fitted, ((ACT1_PORTRAIT_SIZE[0] - fitted.width) // 2, (ACT1_PORTRAIT_SIZE[1] - fitted.height) // 2))
    if remove_background:
        canvas = remove_flat_background(canvas)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG")
    return out_path


def check_act1_portrait(path: Path) -> list[str]:
    """Problems that would stop the portrait loading correctly in Act 1 (empty list = OK)."""
    problems: list[str] = []
    if not path.is_file():
        return [f"portrait not found: {path}"]
    with Image.open(path) as img:
        if img.format != "PNG":
            problems.append(f"portrait must be PNG (got {img.format})")
        if img.size != ACT1_PORTRAIT_SIZE:
            problems.append(f"portrait must be exactly {ACT1_PORTRAIT_SIZE[0]}x{ACT1_PORTRAIT_SIZE[1]} (got {img.size[0]}x{img.size[1]})")
    return problems
