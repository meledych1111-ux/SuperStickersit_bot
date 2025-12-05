from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from rembg import remove

try:
    FONT = ImageFont.truetype("arial.ttf", 100)
except:
    FONT = ImageFont.load_default()

def add_caption(img: Image.Image, text: str):
    if not text.strip(): return
    draw = ImageDraw.Draw(img)
    w, h = img.size
    lines = [l for l in text.upper().split("\n") if l.strip()][:2]
    y = h // 2 - len(lines) * 70
    for line in lines:
        tw = draw.textlength(line, FONT)
        pos = ((w - tw) // 2, y)
        for color in ["#FF00FF", "#00FFFF", "#FFFF00", "white"]:
            draw.text(pos, line, font=FONT, fill=color, stroke_width=12, stroke_fill="black")
        y += 140

def fire_effect(img: Image.Image, caption: str = "") -> Image.Image:
    img = img.convert("RGBA")
    img = remove(img)
    img = ImageEnhance.Contrast(img).enhance(2.5)
    add_caption(img, caption or "FIRE")
    return img

def neon_effect(img: Image.Image, caption: str = "") -> Image.Image:
    img = img.convert("RGBA")
    img = remove(img)
    img = img.filter(ImageFilter.GaussianBlur(3))
    add_caption(img, caption or "NEON")
    return img

def glitch_effect(img: Image.Image, caption: str = "") -> Image.Image:
    import numpy as np
    arr = np.array(img.convert("RGBA"))
    arr[::8] = np.roll(arr[::8], 40, axis=1)
    img = Image.fromarray(arr)
    add_caption(img, caption or "GLITCH")
    return img
