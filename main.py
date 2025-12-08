# main.py - исправленная версия
import os
import sys
import asyncio
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Optional

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, FSInputFile,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.enums import ChatAction

# ===== FFMPEG НАСТРОЙКА =====
def setup_ffmpeg():
    """Настройка ffmpeg-static"""
    import os
    import stat

    # Путь к статическому ffmpeg
    ffmpeg_static = "./ffmpeg-static"

    if not os.path.exists(ffmpeg_static):
        print("❌ ffmpeg-static не найден!")
        print("Скачайте командой:")
        print("wget -q https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz")
        print("tar -xf ffmpeg-git-amd64-static.tar.xz")
        print("mv ffmpeg-git-*-amd64-static/ffmpeg ffmpeg-static")
        print("chmod +x ffmpeg-static")
        return False

    # Убедимся что исполняемый
    if not os.access(ffmpeg_static, os.X_OK):
        os.chmod(ffmpeg_static, stat.S_IRWXU)
        print(f"✅ Сделали ffmpeg-static исполняемым")

    # Проверяем работу
    try:
        result = subprocess.run([ffmpeg_static, "-version"], 
                              capture_output=True, 
                              text=True, 
                              timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.splitlines()[0]
            print(f"✅ FFmpeg работает: {version_line}")
            return True
        else:
            print(f"❌ FFmpeg ошибка: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"❌ Ошибка запуска ffmpeg: {e}")
        return False

print("🔍 Проверяем ffmpeg-static...")
if not setup_ffmpeg():
    sys.exit(1)

# ===== КОНФИГУРАЦИЯ БОТА =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не установлен!")
    print("Установите в Environment Variables (значок замка)")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== ПРЕСЕТЫ =====
PRESETS = {
    "clean": "eq=contrast=1.05:saturation=1.08",
    "vivid": "eq=contrast=1.25:saturation=1.4:brightness=0.02",
    "cinema": "eq=contrast=1.1:brightness=0.01:saturation=0.95",
    "bw": "hue=s=0",
    "soft": "boxblur=2:1",
}

user_settings = {}

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 Загрузить видео")],
            [KeyboardButton(text="🎛 Пресеты"), KeyboardButton(text="ℹ Помощь")]
        ],
        resize_keyboard=True
    )

# ===== FFMPEG УТИЛИТЫ =====
async def run_ffmpeg(cmd: list) -> tuple[int, str, str]:
    """Асинхронный запуск ffmpeg"""
    def _run():
        # Заменяем 'ffmpeg' на './ffmpeg-static'
        if cmd[0] == "ffmpeg":
            cmd[0] = "./ffmpeg-static"

        print(f"🚀 Запускаю: {' '.join(cmd)}")

        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=60
        )
        return process.returncode, process.stdout, process.stderr

    return await asyncio.to_thread(_run)

def build_filter_chain(preset: str = "clean", chroma_key: Optional[str] = None) -> str:
    """Строит цепочку фильтров для ffmpeg"""
    filters = []

    if chroma_key:
        color = chroma_key.lstrip('#')
        if len(color) == 6:
            filters.append(f"colorkey=0x{color}:similarity=0.2:blend=0.05")

    if preset in PRESETS:
        filters.append(PRESETS[preset])
    else:
        filters.append(PRESETS["clean"])

    filters.append("scale=512:512:force_original_aspect_ratio=decrease")
    filters.append("pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000")
    filters.append("format=yuva420p")

    return ','.join(filters)

async def process_video(input_path: Path, output_path: Path, user_id: int) -> tuple[bool, str]:
    """Обработка видео в стикер"""
    try:
        settings = user_settings.get(user_id, {})
        preset = settings.get('preset', 'clean')
        chroma = settings.get('chroma_key')

        vf = build_filter_chain(preset, chroma)

        cmd = [
            "ffmpeg",  # будет заменено на ./ffmpeg-static
            "-y",
            "-i", str(input_path),
            "-t", "3",
            "-an",
            "-vf", vf,
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",
            "-b:v", "500k",
            "-r", "30",
            "-quality", "good",
            str(output_path)
        ]

        code, out, err = await run_ffmpeg(cmd)

        if code != 0:
            error_msg = err[:500] if err else "Неизвестная ошибка"
            return False, f"Ошибка ffmpeg: {error_msg}"

        if not output_path.exists():
            return False, "Файл не создан"

        size_kb = output_path.stat().st_size / 1024
        if size_kb > 256:
            return await compress_video(output_path, output_path)

        return True, f"Готово! Размер: {size_kb:.1f}KB"

    except Exception as e:
        return False, f"Ошибка: {str(e)}"

async def compress_video(input_path: Path, output_path: Path) -> tuple[bool, str]:
    """Сжатие видео до <256KB"""
    try:
        bitrates = ["400k", "300k", "200k", "150k"]

        for bitrate in bitrates:
            temp_path = input_path.with_suffix('.temp.webm')

            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(input_path),
                "-c:v", "libvpx-vp9",
                "-b:v", bitrate,
                "-pix_fmt", "yuva420p",
                "-an",
                "-r", "20",
                str(temp_path)
            ]

            code, _, _ = await run_ffmpeg(cmd)

            if code == 0 and temp_path.exists():
                size_kb = temp_path.stat().st_size / 1024
                if size_kb <= 256:
                    if input_path.exists():
                        input_path.unlink()
                    temp_path.rename(output_path)
                    return True, f"Сжато до {size_kb:.1f}KB"
                else:
                    temp_path.unlink()

        return False, "Не удалось сжать до 256KB"
    except Exception as e:
        return False, f"Ошибка сжатия: {str(e)}"

# ===== ОБРАБОТЧИКИ СООБЩЕНИЙ =====
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🎬 *Стикер-бот для Telegram*\n\n"
        "Отправь мне видео и я сделаю из него стикер!",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "📤 Загрузить видео")
async def prompt_upload(message: Message):
    await message.answer("📹 Отправь мне видео (MP4, MOV, GIF) или анимацию")

@dp.message(F.text == "🎛 Пресеты")
async def show_presets(message: Message):
    presets_text = "🎨 *Доступные пресеты:*\n\n"
    for name in PRESETS.keys():
        presets_text += f"• {name}\n"
    await message.answer(presets_text, parse_mode="Markdown")

@dp.message(F.text == "ℹ Помощь")
async def show_help(message: Message):
    await message.answer(
        "📋 *Помощь*\n\n"
        "Просто отправь видео и получи стикер!\n\n"
        "Требования Telegram:\n"
        "• 3 секунды\n"
        "• 512x512 пикселей\n"
        "• WebM VP9 с альфа-каналом\n"
        "• До 256KB",
        parse_mode="Markdown"
    )

# Выбор пресета
@dp.message(F.text.in_(PRESETS.keys()))
async def select_preset(message: Message):
    preset = message.text
    user_id = message.from_user.id

    if user_id not in user_settings:
        user_settings[user_id] = {}

    user_settings[user_id]['preset'] = preset
    await message.answer(f"✅ Пресет установлен: *{preset}*", parse_mode="Markdown")

# Обработка видео
@dp.message(F.video | F.animation | (F.document & F.document.mime_type.startswith("video/")))
async def handle_video(message: Message):
    await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
    await message.answer("⏳ Обрабатываю видео...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        in_path = tmpdir / "input"
        out_path = tmpdir / "sticker.webm"

        try:
            # Скачиваем файл
            if message.video:
                file_id = message.video.file_id
            elif message.animation:
                file_id = message.animation.file_id
            elif message.document:
                file_id = message.document.file_id
            else:
                await message.answer("❌ Неподдерживаемый формат")
                return

            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, in_path)

            # Проверяем размер
            file_size = in_path.stat().st_size
            if file_size > 20 * 1024 * 1024:
                await message.answer("❌ Файл слишком большой (макс. 20MB)")
                return

            # Обрабатываем
            success, result_msg = await process_video(in_path, out_path, message.from_user.id)

            if not success:
                await message.answer(f"❌ {result_msg}")
                return

            # Отправляем результат
            if out_path.exists():
                await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)
                await message.answer_document(
                    FSInputFile(out_path, filename="sticker.webm"),
                    caption=f"✅ {result_msg}"
                )
            else:
                await message.answer("❌ Ошибка: файл не создан")

        except Exception as e:
            await message.answer(f"❌ Ошибка обработки: {str(e)[:200]}")
            print(f"Error: {e}")

# Обработка всего остального
@dp.message()
async def handle_other(message: Message):
    await message.answer("Используй кнопки меню или отправь видео")

# ===== ЗАПУСК =====
async def main():
    print("=" * 50)
    print("🤖 Telegram Sticker Bot")
    print(f"📊 Bot token: {BOT_TOKEN[:10]}...")
    print("=" * 50)

    print("🚀 Запускаю бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
