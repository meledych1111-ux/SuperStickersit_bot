import random
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from aiogram import types
from bot import dp
from bot.db.models import save_sticker

@dp.message_handler()
async def text_handler(message: types.Message):
    if len(message.text) > 50: return
    img = Image.new("RGBA", (512,512), (random.randint(0,80), 0, random.randint(120,255), 255))
    draw = ImageDraw.Draw(img)
    text = message.text.upper()
    try:
        font = ImageFont.truetype("arial.ttf", 100)
    except:
        font = ImageFont.load_default()
    tw = draw.textlength(text, font)
    pos = ((512-tw)//2, 200)
    for color in ["#00FFFF", "#FF00FF", "#FFFF00", "white"]:
        draw.text(pos, text, font=font, fill=color, stroke_width=10, stroke_fill="black")
    
    bio = BytesIO()
    img.save(bio, "WEBP")
    bio.seek(0)
    sent = await message.answer_sticker(types.InputFile(bio))
    save_sticker(message.from_user, "static", sent.sticker.file_id, text)
