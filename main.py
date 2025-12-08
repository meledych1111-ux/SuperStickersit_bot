import os
import asyncio
import tempfile
import subprocess
import shutil
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
import aiohttp
from aiohttp import web

# ---------- Configuration ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------- Effects ----------
EFFECTS = {
    "✨ Яркий": "eq=contrast=1.25:saturation=1.4:brightness=0.02",
    "🔥 Тёплый": "curves=r='0/0 0.4/0.5 1/1':g='0/0 0.5/0.6 1/1'",
    "❄️ Холодный": "curves=g='0/0 0.4/0.45 1/1':b='0/0 0.45/0.6 1/1'",
    "🎬 Кино": "eq=contrast=1.1:brightness=0.01:saturation=0.95,vignette=PI/4",
    "⚫ Ч/б": "hue=s=0",
    "🕰 Ретро": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    "💡 HDR": "eq=brightness=0.03:contrast=1.3:saturation=1.05",
    "💤 Мягкий": "boxblur=2:1",
    "🔪 Резкий": "unsharp=5:5:1.0",
    "🧹 Чистый": "eq=contrast=1.05:saturation=1.08"
}

user_effect = {}   # user_id -> effect_key
user_chroma = {}   # user_id -> hex string without #

# ---------- Keyboards ----------
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📤 Загрузить видео")],
        [KeyboardButton(text="🎛 Эффекты"), KeyboardButton(text="🧹 Удалить фон (хрома)")],
        [KeyboardButton(text="ℹ Помощь")]
    ],
    resize_keyboard=True
)

effect_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=e)] for e in EFFECTS.keys()],
    resize_keyboard=True
)

chroma_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Зелёный (00FF00)")],
        [KeyboardButton(text="Синий (0000FF)")],
        [KeyboardButton(text="Фиолетовый (FF00FF)")],
        [KeyboardButton(text="Отключить хрома")]
    ],
    resize_keyboard=True
)

# ---------- Helpers ----------
def check_ffmpeg_exists():
    return shutil.which("ffmpeg") is not None

async def run_blocking(cmd, cwd=None):
    def _run():
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
        return proc.returncode, proc.stdout, proc.stderr
    return await asyncio.to_thread(_run)

# ---------- Handlers ----------
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    user_effect[msg.from_user.id] = "🧹 Чистый"
    user_chroma.pop(msg.from_user.id, None)
    await msg.answer(
        "Привет! Я конвертирую видео в WebM-стикеры для Telegram (до 5 секунд, 512×512, ≤256KB).\n\n"
        "Отправь видео прямо в чат или выбери действие.",
        reply_markup=main_menu
    )

@dp.message(F.text == "🎛 Эффекты")
async def on_effects(msg: Message):
    await msg.answer("Выберите эффект:", reply_markup=effect_keyboard)

@dp.message(F.text.in_(list(EFFECTS.keys())))
async def on_select_effect(msg: Message):
    key = msg.text
    user_effect[msg.from_user.id] = key
    await msg.answer(f"Эффект установлен: {key}", reply_markup=main_menu)

@dp.message(F.text == "🧹 Удалить фон (хрома)")
async def on_chroma_menu(msg: Message):
    await msg.answer("Выберите цвет хромакея:", reply_markup=chroma_keyboard)

@dp.message(F.text == "Зелёный (00FF00)")
async def on_chroma_green(msg: Message):
    user_chroma[msg.from_user.id] = "00FF00"
    await msg.answer("Хромакей: зелёный включён", reply_markup=main_menu)

@dp.message(F.text == "Синий (0000FF)")
async def on_chroma_blue(msg: Message):
    user_chroma[msg.from_user.id] = "0000FF"
    await msg.answer("Хромакей: синий включён", reply_markup=main_menu)

@dp.message(F.text == "Фиолетовый (FF00FF)")
async def on_chroma_purple(msg: Message):
    user_chroma[msg.from_user.id] = "FF00FF"
    await msg.answer("Хромакей: фиолетовый включён", reply_markup=main_menu)

@dp.message(F.text == "Отключить хрома")
async def on_chroma_off(msg: Message):
    user_chroma.pop(msg.from_user.id, None)
    await msg.answer("Хромакей отключён", reply_markup=main_menu)

@dp.message(F.text == "📤 Загрузить видео")
async def on_upload_prompt(msg: Message):
    await msg.answer("Пришлите видео (MP4, MOV) или GIF/Animation.", reply_markup=main_menu)

@dp.message(F.text == "ℹ Помощь")
async def on_help(msg: Message):
    await msg.answer(
        "Правила Telegram для видео-стикеров:\n"
        "• Длительность: до 5 секунд (если размер ≤256 KB)\n"
        "• Разрешение: 512×512 px\n"
        "• Формат: WebM (VP9) с альфой\n"
        "• Максимум: 256 KB (512 KB для Premium)\n\n"
        "Выбери эффект, включи хромакей и отправь видео."
    )

# ----- Обработка видео/анимации -----
@dp.message(F.video | F.animation | (F.document & F.document.mime_type.startswith("video")) | F.document.mime_type == "image/gif")
async def handle_media(msg: Message):
    await msg.answer("Начинаю обработку… ⏳", reply_markup=main_menu)

    if not check_ffmpeg_exists():
        await msg.answer("Ошибка: ffmpeg не найден.")
        return

    with tempfile.TemporaryDirectory() as tmpdir_name:
        tmpdir = Path(tmpdir_name)
        in_path = tmpdir / "input"
        out_path = tmpdir / "sticker.webm"

        try:
            file_id = msg.video.file_id if msg.video else msg.animation.file_id if msg.animation else msg.document.file_id
            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, in_path)
        except Exception as e:
            await msg.answer("Сбой при загрузке файла.")
            print("download error:", e)
            return

        effect_key = user_effect.get(msg.from_user.id, "🧹 Чистый")
        preset_filter = EFFECTS[effect_key]
        chroma = user_chroma.get(msg.from_user.id)

        vf_parts = []
        if chroma:
            vf_parts.append(f"colorkey=0x{chroma}:0.25:0.08")
            vf_parts.append("format=rgba")
        vf_parts.append(preset_filter)
        vf_parts.append("scale=512:512:force_original_aspect_ratio=decrease")
        vf_parts.append("pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000")
        vf_parts.append("format=yuva420p")
        vf = ",".join(vf_parts)

        duration_sec = 5
        cmd = [
            "ffmpeg", "-y", "-i", str(in_path),
            "-t", str(duration_sec), "-an", "-vf", vf,
            "-c:v", "libvpx-vp9", "-b:v", "180k",
            "-auto-alt-ref", "0", "-r", "20",
            str(out_path)
        ]
        code, _, _ = await run_blocking(cmd)
        if code != 0:
            await msg.answer("Ошибка при конвертации видео.")
            return

        max_bytes = 256 * 1024
        if out_path.stat().st_size > max_bytes:
            duration_sec = 3
            cmd2 = [
                "ffmpeg", "-y", "-i", str(in_path),
                "-t", str(duration_sec), "-an", "-vf", vf,
                "-c:v", "libvpx-vp9", "-b:v", "180k",
                "-auto-alt-ref", "0", "-r", "20",
                str(out_path)
            ]
            await run_blocking(cmd2)

        size_kb = out_path.stat().st_size // 1024
        try:
            await msg.answer_document(FSInputFile(out_path, filename="sticker.webm"))
            await msg.answer(f"Готово — размер {size_kb} KB, длительность {duration_sec} сек.", reply_markup=main_menu)
        except Exception as e:
            await msg.answer("Ошибка отправки файла в Telegram.")
            print("send error:", e)

# ---------- Webserver + Self-ping ----------
async def handle_root(request):
    return web.Response(text="OK")

async def start_webserver():
    port = int(os.getenv("PORT", 3000))
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Webserver started on port {port}")

async def self_ping_loop():
    url = os.getenv("REPLIT_URL")
    if not url:
        print("Self-ping disabled")
        return
    while True:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=10) as r:
                    print("Self-ping", url, r.status)
        except Exception as e:
            print("Self-ping failed:", e)
        await asyncio.sleep(60*4)

# ---------- Main ----------
async def main():
    await start_webserver()
    asyncio.create_task(self_ping_loop())
    print("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        try:
            asyncio.run(bot.session.close())
        except Exception:
            pass
