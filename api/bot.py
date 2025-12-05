# api/bot.py — РАБОЧАЯ ВЕРСИЯ ДЛЯ VERCEL (декабрь 2025, aiogram 3.13.1)
import os
import uuid
import random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

# ТОКЕН
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ОШИБКА: BOT_TOKEN не задан!")
    raise SystemExit(1)

# Правильная инициализация aiogram 3.13+
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# === Приветствие ===
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "<b>SuperStickersit Bot 2025</b>\n\n"
        "Присылай фото, видео или текст — получишь крутой стикер!\n"
        "15 эффектов для видео, неон, шейк, глитч и многое другое\n\n"
        "Просто пришли что угодно!",
    )

# === Фото → стикер ===
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    file_path = f"/tmp/photo_{uuid.uuid4()}.jpg"
    await message.photo[-1].download(destination_file=file_path)
    img = Image.open(file_path).convert("RGBA")
    img = img.resize((512, 512))

    # Эффект: неон + контраст
    img = ImageEnhance.Contrast(img).enhance(2.5)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 80)
    except:
        font = ImageFont.load_default()
    draw.text((50, 400), "SUPER", fill="cyan", stroke_width=6, stroke_fill="magenta", font=font)

    bio = BytesIO()
    img.save(bio, "WEBP")
    bio.seek(0)
    await message.answer_sticker(InputFile(bio, filename="sticker.webp"))

# === Видео → заглушка ===
@dp.message(F.video | F.video_note)
async def video_handler(message: types.Message):
    await message.answer("Видео получено! Выбери эффект (в разработке):\nSHAKE • ZOOM • GLITCH • NEON • VHS")

# === Текст → неоновый стикер ===
@dp.message(F.text)
async def text_handler(message: types.Message):
    text = message.text.upper()[:30]
    img = Image.new("RGB", (512, 512), color=(random.randint(0,100), 0, random.randint(150,255)))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 100)
    except:
        font = ImageFont.load_default()
    tw = draw.textlength(text, font)
    pos = ((512 - tw) // 2, 200)
    for color in ["#00FFFF", "#FF00FF", "#FFFF00", "white"]:
        draw.text(pos, text, font=font, fill=color, stroke_width=10, stroke_fill="black")

    bio = BytesIO()
    img.save(bio, "WEBP")
    bio.seek(0)
    await message.answer_sticker(InputFile(bio, filename="text_sticker.webp"))

# === Webhook ===
async def on_startup(app):
    url = f"https://{os.getenv('VERCEL_URL')}/api/bot"
    await bot.set_webhook(url)
    print(f"Webhook установлен: {url}")

app = web.Application()
app.on_startup.append(on_startup)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/api/bot")

if __name__ == "__main__":
    web.run_app(app, port=8000)
