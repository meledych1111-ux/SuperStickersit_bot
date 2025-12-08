# main.py
import os
import asyncio
import tempfile
import subprocess
import shutil
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, FSInputFile,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import CommandStart

# ---------- Configuration ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # поставь в Secrets на Replit
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------- Presets ----------
# Значения фильтров — чистые ffmpeg-части, комбинируются в одну цепочку.
PRESETS = {
    "vivid": "eq=contrast=1.25:saturation=1.4:brightness=0.02",
    "warm": "curves=r='0/0 0.4/0.5 1/1':g='0/0 0.5/0.6 1/1'",
    "cool": "curves=g='0/0 0.4/0.45 1/1':b='0/0 0.45/0.6 1/1'",
    "cinema": "eq=contrast=1.1:brightness=0.01:saturation=0.95,vignette=PI/4",
    "bw": "hue=s=0",
    "retro": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    "hdr": "eq=brightness=0.03:contrast=1.3:saturation=1.05",
    "soft": "boxblur=2:1",
    "sharp": "unsharp=5:5:1.0",
    "clean": "eq=contrast=1.05:saturation=1.08"
}

# per-user selected preset (in-memory)
user_preset = {}  # user_id -> preset_key

# chroma per-user (None or hex without #)
user_chroma = {}  # user_id -> "00FF00" etc.

# ---------- Keyboards ----------
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📤 Загрузить видео")],
        [KeyboardButton("🎛 Пресеты"), KeyboardButton("🧹 Удалить фон (хрома)")],
        [KeyboardButton("ℹ Помощь")]
    ],
    resize_keyboard=True
)

# preset keyboard (one-button-per-row)
preset_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(p)] for p in PRESETS.keys()],
    resize_keyboard=True
)

chroma_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("Зелёный (00FF00)")],
        [KeyboardButton("Синий (0000FF)")],
        [KeyboardButton("Фиолетовый (FF00FF)")],
        [KeyboardButton("Отключить хрома")]
    ],
    resize_keyboard=True
)

# ---------- Helpers ----------

def check_ffmpeg_exists():
    return shutil.which("ffmpeg") is not None

async def run_blocking(cmd, cwd=None):
    """Run blocking subprocess in thread to avoid blocking event loop."""
    def _run():
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd
        )
        return proc.returncode, proc.stdout, proc.stderr
    return await asyncio.to_thread(_run)

def build_filter_chain(preset_filter: str, chroma_hex: str | None):
    """
    Build ffmpeg vf filter with correct ordering:
    1) colorkey (if present) -> format=rgba (preserve alpha)
    2) preset effects (color correction, blur, etc.)
    3) scale -> pad to exact 512x512 (no borders visible)
    4) format=yuva420p
    """
    parts = []

    # 1) chroma key first (if requested)
    if chroma_hex:
        # Conservative similarity/blend settings; can be tuned
        parts.append(f"colorkey=0x{chroma_hex}:0.25:0.08")
        parts.append("format=rgba")

    # 2) preset filter (user-selected)
    if preset_filter:
        parts.append(preset_filter)

    # 3) scale & pad to exact 512x512 (cover/decrease may crop/fit, but we use decrease+pad)
    # Ensure we keep aspect ratio then pad with transparent background
    parts.append("scale=512:512:force_original_aspect_ratio=decrease")
    # pad transparent with black@0
    parts.append("pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0")

    # 4) ensure alpha-capable pixel format for VP9
    parts.append("format=yuva420p")

    return ",".join(parts)

async def compress_until_size(path: Path, max_bytes: int = 256 * 1024):
    """
    Try to reduce size by lowering bitrate/fps progressively.
    Returns final path (may mutate original).
    """
    # initial target bitrate (in bits) — string for ffmpeg like '220k'
    bitrates = ["240k", "180k", "140k", "110k", "90k"]
    framerates = ["30", "25", "20", "15"]

    for br in bitrates:
        for fr in framerates:
            if path.stat().st_size <= max_bytes:
                return path
            tmp = path.with_suffix(".tmp.webm")
            cmd = [
                "ffmpeg", "-y", "-i", str(path),
                "-c:v", "libvpx-vp9", "-b:v", br, "-r", fr,
                "-pix_fmt", "yuva420p",
                "-an",
                str(tmp)
            ]
            code, out, err = await run_blocking(cmd)
            if code == 0 and tmp.exists():
                tmp_size = tmp.stat().st_size
                if tmp_size < path.stat().st_size:
                    path.unlink()
                    tmp.rename(path)
                else:
                    tmp.unlink()
            # continue loop until satisfied
    return path

# ---------- Handlers ----------

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    user_preset[msg.from_user.id] = "clean"
    user_chroma.pop(msg.from_user.id, None)
    await msg.answer(
        "Привет! Я конвертирую видео в WebM-стикеры для Telegram (3s, 512×512, ≤256KB).\n\n"
        "Отправь видео прямо в чат или выбери действие.",
        reply_markup=main_menu
    )

@dp.message(F.text == "🎛 Пресеты")
async def on_presets(msg: Message):
    await msg.answer("Выбери пресет (настройка применяется к следующему видео):", reply_markup=preset_keyboard)

@dp.message(F.text.in_(list(PRESETS.keys())))
async def on_select_preset(msg: Message):
    key = msg.text
    user_preset[msg.from_user.id] = key
    await msg.answer(f"Пресет установлен: {key}", reply_markup=main_menu)

@dp.message(F.text == "🧹 Удалить фон (хрома)")
async def on_chroma_menu(msg: Message):
    await msg.answer("Выберите цвет хромакея (будет применён к следующему видео):", reply_markup=chroma_keyboard)

@dp.message(F.text == "Зелёный (00FF00)")
async def on_chroma_green(msg: Message):
    user_chroma[msg.from_user.id] = "00FF00"
    await msg.answer("Хромакей: зелёный (00FF00) включён", reply_markup=main_menu)

@dp.message(F.text == "Синий (0000FF)")
async def on_chroma_blue(msg: Message):
    user_chroma[msg.from_user.id] = "0000FF"
    await msg.answer("Хромакей: синий (0000FF) включён", reply_markup=main_menu)

@dp.message(F.text == "Фиолетовый (FF00FF)")
async def on_chroma_purple(msg: Message):
    user_chroma[msg.from_user.id] = "FF00FF"
    await msg.answer("Хромакей: фиолетовый (FF00FF) включён", reply_markup=main_menu)

@dp.message(F.text == "Отключить хрома")
async def on_chroma_off(msg: Message):
    user_chroma.pop(msg.from_user.id, None)
    await msg.answer("Хромакей отключён", reply_markup=main_menu)

@dp.message(F.text == "📤 Загрузить видео")
async def on_upload_prompt(msg: Message):
    await msg.answer("Пришли, пожалуйста, видео (MP4, MOV) или GIF/Animation прямо в чат.", reply_markup=main_menu)

@dp.message(F.text == "ℹ Помощь")
async def on_help(msg: Message):
    await msg.answer(
        "Правила Telegram для видео-стикеров:\n"
        "• Длительность: ровно 3 секунды\n"
        "• Точное разрешение: 512×512 px (без полей)\n"
        "• Формат: WebM (VP9) с альфой\n"
        "• Максимум: 256 KB (512 KB для Premium)\n\n"
        "Выбери пресет, включи хромакей при необходимости и отправь видео."
    )

@dp.message(F.video | F.animation | (F.document & F.document.mime_type.startswith("video")))
async def handle_media(msg: Message):
    await msg.answer("Получил. Начинаю обработку… ⏳", reply_markup=main_menu)

    # sanity checks
    if not check_ffmpeg_exists():
        await msg.answer("Ошибка: ffmpeg не найден в системе. В Replit: открой Shell и выполни: `apt update && apt install -y ffmpeg`")
        return

    # prepare temp files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        in_path = tmpdir / "input"
        out_path = tmpdir / "out.webm"

        # download file: handle video / animation / document
        try:
            if msg.video:
                await msg.video.download(destination=in_path)
            elif msg.animation:
                await msg.animation.download(destination=in_path)
            elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("video"):
                await msg.document.download(destination=in_path)
            else:
                await msg.answer("Не удалось распознать формат файла.")
                return
        except Exception as e:
            await msg.answer("Сбой при загрузке файла.")
            print("download error:", e)
            return

        # build ffmpeg filter chain: preset + chroma + scaling/pad/final format
        preset_key = user_preset.get(msg.from_user.id, "clean")
        preset_filter = PRESETS.get(preset_key, PRESETS["clean"])
        chroma = user_chroma.get(msg.from_user.id)

        vf = build_filter_chain(preset_filter, chroma)
        # ensure exact 3s; first convert using initial bitrate
        cmd = [
            "ffmpeg", "-y",
            "-i", str(in_path),
            "-t", "3",
            "-an",
            "-vf", vf,
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",
            "-b:v", "220k",
            str(out_path)
        ]

        code, out, err = await run_blocking(cmd)
        if code != 0:
            await msg.answer("FFmpeg: ошибка при первичной конвертации.")
            print(err.decode(errors="ignore"))
            return

        # compress to <=256KB if needed
        try:
            final = await compress_until_size(out_path, max_bytes=256 * 1024)
        except Exception as e:
            await msg.answer("Ошибка при сжатии файла.")
            print("compress error:", e)
            return

        size_kb = final.stat().st_size // 1024
        # send back as document (safer) — пользователь сможет сохранить; можно заменить на send_sticker при желании
        try:
            await msg.answer_document(FSInputFile(final, filename="sticker.webm"))
            await msg.answer(f"Готово — размер {size_kb} KB. Если нужно, могу отправить в виде стикера/пакета.", reply_markup=main_menu)
        except Exception as e:
            await msg.answer("Ошибка отправки файла в Telegram.")
            print("send error:", e)

# ---------- Keep-alive minimal webserver + self-ping ----------
# This helps Replit keep instance awake when you use external pinger or Replit's own web exposure.
from aiohttp import web

async def handle_root(request):
    return web.Response(text="OK")

async def start_webserver(app_host="0.0.0.0", app_port=None):
    port = int(os.getenv("PORT", os.getenv("REPLIT_PORT", 3000)))
    runner = web.AppRunner(web.Application())
    await runner.setup()
    site = web.TCPSite(runner, host=app_host, port=port)
    # add a simple root route
    runner.app.router.add_get("/", handle_root)
    await site.start()
    print(f"Webserver started on port {port}")

async def self_ping_loop():
    # If REPLIT_URL present, periodically ping it to help keep alive.
    repl_url = os.getenv("REPLIT_URL") or os.getenv("REPLIT_RUN_URL")
    if not repl_url:
        return
    # normalize
    if repl_url.startswith("http"):
        url = repl_url
    else:
        url = f"https://{repl_url}"
    await asyncio.sleep(10)
    while True:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=10) as r:
                    print("Self-ping", url, r.status)
        except Exception as e:
            print("Self-ping failed:", e)
        await asyncio.sleep(60 * 4)

# ---------- Main ----------
async def main():
    # start webserver and self-pinger in background
    asyncio.create_task(start_webserver())
    asyncio.create_task(self_ping_loop())
    print("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        # graceful shutdown
        try:
            asyncio.run(bot.session.close())
        except Exception:
            pass
