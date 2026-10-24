from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

CARD_SIZE = (768, 1152)
PORTRAIT_BOX = (60, 188, 708, 782)
NAME_BOX = (34, 28, 734, 162)
ATTACK_BOX = (40, 808, 215, 1115)
SIGIL_BOX = (223, 808, 545, 1115)
HEALTH_BOX = (553, 808, 728, 1115)


def _font(size: int):
    for candidate in ["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Arial.ttf"]:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _parchment(img: Image.Image, rect, base=(229, 197, 165), speck=(191, 150, 120)):
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=22, fill=base, outline=(40, 25, 18), width=5)
    for x in range(x0 + 8, x1 - 8, 31):
        for y in range(y0 + 8, y1 - 8, 37):
            if (x * 7 + y * 13) % 5 == 0:
                draw.point((x, y), fill=speck)
                draw.point((min(x + 1, x1 - 1), y), fill=speck)


def _draw_blood_drop(draw, center, scale=1.0):
    cx, cy = center
    pts = [(cx, cy - 34 * scale), (cx + 26 * scale, cy + 4 * scale), (cx, cy + 36 * scale), (cx - 26 * scale, cy + 4 * scale)]
    draw.polygon(pts, fill=(177, 31, 28), outline=(111, 13, 13))


def render_card(card, portrait_path: Path, out_path: Path):
    img = Image.new("RGBA", CARD_SIZE, (11, 8, 7, 255))
    _parchment(img, (14, 14, CARD_SIZE[0] - 14, CARD_SIZE[1] - 14), base=(214, 181, 148), speck=(188, 146, 118))
    _parchment(img, NAME_BOX)
    _parchment(img, ATTACK_BOX)
    _parchment(img, SIGIL_BOX)
    _parchment(img, HEALTH_BOX)
    draw = ImageDraw.Draw(img)

    # portrait frame
    draw.rounded_rectangle(PORTRAIT_BOX, radius=18, fill=(8, 8, 8), outline=(40, 25, 18), width=5)
    portrait = Image.open(portrait_path).convert("RGBA")
    portrait = ImageOps.contain(portrait, (PORTRAIT_BOX[2] - PORTRAIT_BOX[0] - 12, PORTRAIT_BOX[3] - PORTRAIT_BOX[1] - 12), Image.Resampling.NEAREST)
    px = PORTRAIT_BOX[0] + ((PORTRAIT_BOX[2] - PORTRAIT_BOX[0]) - portrait.width) // 2
    py = PORTRAIT_BOX[1] + ((PORTRAIT_BOX[3] - PORTRAIT_BOX[1]) - portrait.height) // 2
    img.alpha_composite(portrait, (px, py))

    # name
    name_font = _font(72)
    name = card.name.upper()
    bbox = draw.textbbox((0, 0), name, font=name_font)
    nx = (CARD_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((nx, 52), name, fill=(18, 12, 10), font=name_font)

    # blood cost
    _draw_blood_drop(draw, (650, 270), scale=1.2)
    cost_font = _font(54)
    ctext = str(card.cost_blood)
    cb = draw.textbbox((0, 0), ctext, font=cost_font)
    draw.text((650 - (cb[2]-cb[0])//2, 252), ctext, fill=(247, 224, 207), font=cost_font)

    # attack and health
    big_font = _font(124)
    draw.text((85, 870), str(card.attack), fill=(18, 12, 10), font=big_font)
    draw.text((605, 870), str(card.health), fill=(18, 12, 10), font=big_font)

    # bottom icons / text
    small_font = _font(18)
    label_font = _font(36)
    draw.text((84, 1050), "ATK", fill=(18, 12, 10), font=small_font)
    draw.text((600, 1050), "HP", fill=(18, 12, 10), font=small_font)

    # sigil icon: simple spiky emblem
    cx = (SIGIL_BOX[0] + SIGIL_BOX[2]) // 2
    cy = 930
    spikes = [(cx, cy - 78), (cx + 22, cy - 20), (cx + 78, cy - 8), (cx + 28, cy + 8),
              (cx + 46, cy + 58), (cx, cy + 20), (cx - 46, cy + 58), (cx - 28, cy + 8),
              (cx - 78, cy - 8), (cx - 22, cy - 20)]
    draw.polygon(spikes, fill=(18, 12, 10))
    sigil_text = card.sigil_name.upper()
    sb = draw.textbbox((0, 0), sigil_text, font=label_font)
    draw.text((cx - (sb[2]-sb[0])//2, 1036), sigil_text, fill=(18, 12, 10), font=label_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path
