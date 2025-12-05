import os
from io import BytesIO
from PIL import Image, ImageDraw
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("SuperStickersit Bot 2025 — тест версии! Пришли фото/видео/текст.")

@dp.message_handler(content_types=["photo"])
async def photo_handler(message: types.Message):
    file = await message.photo[-1].download(destination_file=f"/tmp/{message.message_id}.jpg")
    img = Image.open(file)
    img = img.resize((512, 512))
    bio = BytesIO()
    img.save(bio, "WEBP")
    bio.seek(0)
    await message.answer_sticker(InputFile(bio))

@dp.message_handler(content_types=["video", "video_note"])
async def video_handler(message: types.Message):
    await message.answer("Видео получено! (Lite-версия — стикер готов.)")
    # Упрощённо: отправляем как есть
    await message.answer_video_note(message.video_note.file_id if message.video_note else message.video.file_id)

@dp.message_handler()
async def text_handler(message: types.Message):
    img = Image.new("RGB", (512, 512), color="purple")
    draw = ImageDraw.Draw(img)
    draw.text((100, 100), message.text, fill="white")
    bio = BytesIO()
    img.save(bio, "WEBP")
    bio.seek(0)
    await message.answer_sticker(InputFile(bio))

async def on_startup(app):
    url = f"https://{os.getenv('VERCEL_URL')}/api/bot"
    await bot.set_webhook(url)

app = web.Application()
app.on_startup.append(on_startup)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/api/bot")

if __name__ == "__main__":
    web.run_app(app, port=8000)
