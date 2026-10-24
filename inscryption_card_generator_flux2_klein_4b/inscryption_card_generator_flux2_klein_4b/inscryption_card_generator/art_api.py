"""No-model placeholder portrait for quick smoke tests. No external requests."""
from pathlib import Path
from PIL import Image

def make_placeholder_portrait(out_path: Path, card_name: str, size: int = 128) -> Path:
    from PIL import ImageDraw, ImageFont

    img = Image.new("RGBA", (size, size), (8, 8, 8, 255))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        shade = int(18 + (y / size) * 16)
        draw.line((0, y, size, y), fill=(shade, shade, shade, 255))
    draw.ellipse((18, 10, 112, 92), fill=(89, 58, 42, 255), outline=(190, 145, 110, 255), width=2)
    draw.polygon([(64, 18), (92, 54), (64, 102), (36, 54)], fill=(120, 78, 54, 255), outline=(210, 170, 125, 255))
    draw.ellipse((48, 52, 58, 62), fill=(255, 174, 30, 255))
    draw.ellipse((70, 52, 80, 62), fill=(255, 174, 30, 255))
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 10)
    except Exception:
        font = ImageFont.load_default()
    draw.text((6, size - 14), card_name[:18], fill=(220, 205, 182, 255), font=font)
    img.save(out_path, format="PNG")
    return out_path
