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
    # Windows ships arialbd.ttf/arial.ttf (Pillow cannot find "Arial Bold.ttf"); DejaVu covers Linux.
    for candidate in ["DejaVuSans-Bold.ttf", "arialbd.ttf", "arial.ttf", "Arial Bold.ttf", "Arial.ttf",
                      "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
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

    # name (shrinks to fit) and tribe
    name = card.name.upper()
    for size in (72, 60, 48, 40):
        name_font = _font(size)
        bbox = draw.textbbox((0, 0), name, font=name_font)
        if bbox[2] - bbox[0] <= NAME_BOX[2] - NAME_BOX[0] - 40:
            break
    nx = (CARD_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((nx, 40), name, fill=(18, 12, 10), font=name_font)
    tribe_font = _font(24)
    tribe = str(getattr(card, "tribe", "")).upper()
    tb = draw.textbbox((0, 0), tribe, font=tribe_font)
    draw.text(((CARD_SIZE[0] - (tb[2] - tb[0])) // 2, 124), tribe, fill=(70, 45, 32), font=tribe_font)

    # blood cost: one drop per blood (Act 1 cost decal), or FREE
    cost = int(card.cost_blood)
    if cost == 0:
        draw.text((590, 250), "FREE", fill=(247, 224, 207), font=_font(40))
    for i in range(cost):
        _draw_blood_drop(draw, (650 - i * 62, 270), scale=1.0)
    if getattr(card, "rescan_recommended", False):
        draw.text((80, 740), "RESCAN RECOMMENDED", fill=(230, 190, 90), font=_font(26))

    # attack and health
    big_font = _font(124)
    draw.text((85, 870), str(card.attack), fill=(18, 12, 10), font=big_font)
    draw.text((605, 870), str(card.health), fill=(18, 12, 10), font=big_font)

    # bottom icons / text
    small_font = _font(18)
    label_font = _font(36)
    draw.text((84, 1050), "ATK", fill=(18, 12, 10), font=small_font)
    draw.text((600, 1050), "HP", fill=(18, 12, 10), font=small_font)

    # sigils: one emblem + label per sigil (Act 1 cards show at most two)
    sigils = [s["display_name"] for s in getattr(card, "sigils", [])] or (
        [] if card.sigil_name in ("", "No sigil") else [card.sigil_name])
    cx = (SIGIL_BOX[0] + SIGIL_BOX[2]) // 2
    slots = [(cx, 930)] if len(sigils) <= 1 else [(cx - 78, 920), (cx + 78, 920)]
    for sx, sy in slots[:len(sigils)]:
        scale = 1.0 if len(sigils) <= 1 else 0.6
        spikes = [(sx + dx * scale, sy + dy * scale) for dx, dy in
                  [(0, -78), (22, -20), (78, -8), (28, 8), (46, 58), (0, 20), (-46, 58), (-28, 8), (-78, -8), (-22, -20)]]
        draw.polygon(spikes, fill=(18, 12, 10))
    for i, label in enumerate(sigils):
        font = label_font if len(sigils) <= 1 else _font(24)
        text = label.upper()
        sb = draw.textbbox((0, 0), text, font=font)
        draw.text((cx - (sb[2] - sb[0]) // 2, 1010 + i * 34), text, fill=(18, 12, 10), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path
