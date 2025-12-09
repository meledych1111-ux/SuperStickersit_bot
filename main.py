# main.py - С ЭФФЕКТАМИ СНЕГ, ЗВЕЗДЫ, ЗАМЕДЛЕНИЕ, УСКОРЕНИЕ
import os
import sys
import asyncio
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Dict
import time
from datetime import datetime
import uuid
import random

print("=" * 60)
print("🤖 Telegram Video Sticker Bot")
print("=" * 60)

FFMPEG = shutil.which("ffmpeg")
if not FFMPEG:
    print("❌ ffmpeg не найден!")
    sys.exit(1)

print(f"✅ FFmpeg: {FFMPEG}")

try:
    from aiogram import Bot, Dispatcher, F
    from aiogram.filters import CommandStart, Command
    from aiogram.types import (
        Message, BufferedInputFile,
        ReplyKeyboardMarkup, KeyboardButton,
        InlineKeyboardMarkup, InlineKeyboardButton,
        CallbackQuery
    )
    from aiogram.enums import ParseMode, ChatAction
    print("✅ Aiogram загружен")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

MAX_FILE_SIZE = 10 * 1024 * 1024
TARGET_SIZE = 256 * 1024

# ===== ХРАНИЛИЩЕ =====
class FileStorage:
    def __init__(self):
        self.storage_dir = Path("./temp_files")
        self.storage_dir.mkdir(exist_ok=True)
        self.files = {}
        print(f"📁 Хранилище: {self.storage_dir.absolute()}")

    def save(self, user_id: int, file_path: Path) -> str:
        file_id = str(uuid.uuid4())
        user_dir = self.storage_dir / str(user_id)
        user_dir.mkdir(exist_ok=True)

        saved_path = user_dir / file_id
        shutil.copy2(file_path, saved_path)

        self.files[file_id] = {
            'path': saved_path,
            'user_id': user_id,
            'time': time.time()
        }
        print(f"💾 Файл сохранен: {file_id}")
        return file_id

    def get(self, file_id: str) -> Path:
        return self.files[file_id]['path']

    def delete(self, file_id: str):
        if file_id in self.files:
            try:
                path = self.files[file_id]['path']
                if path.exists():
                    path.unlink()
            except:
                pass
            del self.files[file_id]

storage = FileStorage()

# ===== ЭФФЕКТЫ =====
EFFECTS = {
    "none": {
        "name": "🎨 Без эффекта",
        "filter": ""
    },
    "slowmo": {
        "name": "🐌 Замедление",
        "filter": "setpts=2.0*PTS"  # В 2 раза медленнее
    },
    "fastmo": {
        "name": "⚡ Ускорение", 
        "filter": "setpts=0.5*PTS"  # В 2 раза быстрее
    },
    "snow": {
        "name": "❄️ Снегопад",
        "filter": "color=c=white@0.1:s=512x512,geq=r='random(1)*255':g='random(1)*255':b='random(1)*255',format=rgba"
    },
    "stars": {
        "name": "✨ Звёзды",
        "filter": "color=c=black:s=512x512,noise=alls=20:allf=t+u,curves=preset=lighter"
    }
}

# ===== ФУНКЦИИ ДЛЯ СОЗДАНИЯ СТИКЕРОВ =====
async def create_sticker_with_effect(input_path: Path, output_path: Path, effect: str = "none") -> Tuple[bool, str, int]:
    """
    Создает WebM стикер с эффектом
    """
    try:
        print(f"🎬 Создаю стикер с эффектом: {EFFECTS[effect]['name']}")

        # Получаем информацию о видео
        info = await get_video_info(input_path)
        duration = min(info['duration'], 2.8)
        fps = info['fps']

        print(f"   📊 Исходное: {info['width']}x{info['height']}, {duration:.1f}с, {fps:.1f}fps")

        # Базовый фильтр для Telegram
        base_filter = "scale=512:512:force_original_aspect_ratio=decrease," \
                     "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0," \
                     f"fps=30,format=yuva420p"

        # Добавляем эффект
        effect_filter = EFFECTS[effect]['filter']
        if effect_filter:
            # Для снега и звёзд создаем отдельный слой и накладываем
            if effect in ["snow", "stars"]:
                # Создаем видео с эффектом
                effect_video = input_path.with_suffix(f'.{effect}.mp4')
                await create_effect_video(effect, effect_video, duration)

                # Комбинируем с основным видео
                filter_complex = f"[0:v]{base_filter}[main];" \
                               f"[1:v]scale=512:512,format=yuva420p[effect];" \
                               f"[main][effect]overlay=format=auto"

                cmd = [
                    FFMPEG, "-y",
                    "-i", str(input_path),
                    "-i", str(effect_video),
                    "-t", str(duration),
                    "-an",
                    "-filter_complex", filter_complex,
                    "-c:v", "libvpx",
                    "-b:v", "150k",
                    "-crf", "32",
                    "-deadline", "good",
                    "-auto-alt-ref", "0",
                    "-f", "webm",
                    str(output_path)
                ]

                # Удаляем временный файл эффекта
                try:
                    effect_video.unlink()
                except:
                    pass

            else:
                # Для других эффектов просто добавляем фильтр
                video_filter = f"{base_filter},{effect_filter}"
                cmd = [
                    FFMPEG, "-y",
                    "-i", str(input_path),
                    "-t", str(duration),
                    "-an",
                    "-vf", video_filter,
                    "-c:v", "libvpx",
                    "-b:v", "150k",
                    "-crf", "32",
                    "-deadline", "good",
                    "-auto-alt-ref", "0",
                    "-f", "webm",
                    str(output_path)
                ]
        else:
            # Без эффекта
            cmd = [
                FFMPEG, "-y",
                "-i", str(input_path),
                "-t", str(duration),
                "-an",
                "-vf", base_filter,
                "-c:v", "libvpx",
                "-b:v", "150k",
                "-crf", "32",
                "-deadline", "good", 
                "-auto-alt-ref", "0",
                "-f", "webm",
                str(output_path)
            ]

        print(f"   🛠️ Запускаю конвертацию...")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0 and output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            print(f"   ✅ Стикер создан: {size_kb:.1f}KB")

            # Оптимизируем если нужно
            if size_kb > 200:
                print(f"   ⚙️ Оптимизирую размер...")
                await optimize_webm(output_path)
                size_kb = output_path.stat().st_size / 1024

            # Проверяем параметры
            output_info = await get_video_info(output_path)
            checks = {
                "Размер ≤256KB": size_kb <= 256,
                "FPS=30": abs(output_info['fps'] - 30) < 1,
                "Разрешение 512x512": output_info['width'] == 512 and output_info['height'] == 512
            }

            status = "✅" if all(checks.values()) and size_kb <= 256 else "⚠️"

            message = f"{status} <b>Стикер создан!</b>\n\n"
            message += f"🎭 <b>Эффект:</b> {EFFECTS[effect]['name']}\n"
            message += f"📦 <b>Размер:</b> {size_kb:.1f}KB / 256KB\n"
            message += f"📏 <b>Разрешение:</b> {output_info['width']}x{output_info['height']}\n"
            message += f"🎬 <b>FPS:</b> {output_info['fps']:.1f}\n"
            message += f"⏱ <b>Длительность:</b> {output_info['duration']:.1f}с\n"

            if all(checks.values()) and size_kb <= 256:
                message += "\n🎉 <b>Готов к добавлению в Telegram!</b>"
            else:
                message += "\n⚠️ <b>Возможны проблемы с размером или параметрами</b>"

            return True, message, int(size_kb)

        error = stderr.decode('utf-8', errors='ignore')
        print(f"   ❌ Ошибка: {error[:200]}")
        return False, "❌ Не удалось создать стикер", 0

    except Exception as e:
        print(f"   🔥 Исключение: {e}")
        return False, f"❌ Ошибка: {str(e)[:100]}", 0

async def create_effect_video(effect: str, output_path: Path, duration: float):
    """Создает видео с эффектом (снег, звёзды)"""
    try:
        if effect == "snow":
            # Создаем снегопад
            cmd = [
                FFMPEG, "-y",
                "-f", "lavfi",
                "-i", f"color=c=white@0:s=512x512:d={duration},geq=r='random(1)*255':g='random(1)*255':b='random(1)*255',format=rgba",
                "-t", str(duration),
                "-c:v", "libx264",
                "-pix_fmt", "yuva420p",
                str(output_path)
            ]
        elif effect == "stars":
            # Создаем звёзды
            cmd = [
                FFMPEG, "-y",
                "-f", "lavfi",
                "-i", f"color=c=black:s=512x512:d={duration},noise=alls=20:allf=t+u,curves=preset=lighter",
                "-t", str(duration),
                "-c:v", "libx264",
                "-pix_fmt", "yuva420p",
                str(output_path)
            ]
        else:
            return False

        process = await asyncio.create_subprocess_exec(*cmd)
        await process.wait()
        return process.returncode == 0

    except:
        return False

async def optimize_webm(file_path: Path) -> bool:
    """Оптимизация размера WebM"""
    try:
        temp_path = file_path.with_suffix('.opt.webm')

        cmd = [
            FFMPEG, "-y",
            "-i", str(file_path),
            "-t", "2.5",
            "-an",
            "-vf", "scale=384:384,fps=30",
            "-c:v", "libvpx",
            "-b:v", "80k",
            "-crf", "38",
            "-deadline", "good",
            "-auto-alt-ref", "0",
            "-f", "webm",
            str(temp_path)
        ]

        process = await asyncio.create_subprocess_exec(*cmd)
        await process.wait()

        if temp_path.exists():
            new_size = temp_path.stat().st_size / 1024
            if new_size <= 256:
                file_path.unlink()
                temp_path.rename(file_path)
                return True
            else:
                temp_path.unlink()
        return False
    except:
        return False

async def get_video_info(file_path: Path) -> Dict:
    """Получает информацию о видео"""
    try:
        cmd = [FFMPEG, "-i", str(file_path), "-hide_banner"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        output = stderr.decode('utf-8', errors='ignore')

        info = {
            'duration': 0,
            'width': 0,
            'height': 0,
            'fps': 0,
            'codec': 'unknown',
            'pix_fmt': 'unknown'
        }

        for line in output.split('\n'):
            if 'Duration:' in line:
                try:
                    dur_str = line.split('Duration:')[1].split(',')[0].strip()
                    h, m, s = dur_str.split(':')
                    info['duration'] = int(h)*3600 + int(m)*60 + float(s)
                except:
                    pass
            elif 'Video:' in line:
                parts = line.split('Video:')[1].split(',')
                info['codec'] = parts[0].strip()

                # Ищем разрешение
                for part in parts:
                    if 'x' in part and '[' not in part:
                        try:
                            w, h = part.strip().split('x')
                            info['width'] = int(w)
                            info['height'] = int(h)
                        except:
                            pass

                # Ищем FPS
                for part in parts:
                    if 'fps' in part:
                        try:
                            fps_str = part.split('fps')[0].strip()
                            info['fps'] = float(fps_str)
                        except:
                            pass

                # Ищем формат пикселей
                for fmt in ['yuva420p', 'yuv420p', 'rgba']:
                    if fmt in line.lower():
                        info['pix_fmt'] = fmt
                        break

        return info
    except:
        return {'duration': 0, 'width': 0, 'height': 0, 'fps': 0, 'codec': 'unknown', 'pix_fmt': 'unknown'}

# ===== ОБРАБОТЧИКИ =====
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎬 <b>Video Sticker Bot с эффектами!</b>\n\n"
        "<b>✨ Доступные эффекты:</b>\n"
        "• 🐌 Замедление\n"
        "• ⚡ Ускорение\n"
        "• ❄️ Снегопад\n"
        "• ✨ Звёзды\n"
        "• 🎨 Без эффекта\n\n"
        "<b>✅ Соответствует Telegram:</b>\n"
        "• WebM с VP8 кодеком\n"
        "• 30 кадров/сек\n"
        "• 512x512 пикселей\n"
        "• До 256 КБ\n"
        "• Без звука\n\n"
        "<b>📤 Отправь видео или GIF:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📤 ОТПРАВИТЬ ВИДЕО")],
                [KeyboardButton(text="✨ ЭФФЕКТЫ"), KeyboardButton(text="🆘 ПОМОЩЬ")]
            ],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "📤 ОТПРАВИТЬ ВИДЕО")
async def send_video(message: Message):
    await message.answer(
        "📤 <b>Отправь мне видео или GIF</b>\n\n"
        "<i>• До 10MB\n"
        "• До 5 секунд\n"
        "• Любой формат\n\n"
        "После загрузки выбери эффект!</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "✨ ЭФФЕКТЫ")
async def show_effects(message: Message):
    effects_list = "\n".join([f"• {effect['name']}" for effect in EFFECTS.values()])
    await message.answer(
        f"✨ <b>Доступные эффекты:</b>\n\n{effects_list}\n\n"
        f"<i>Отправь видео, затем выбери эффект</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "🆘 ПОМОЩЬ")
async def show_help(message: Message):
    await message.answer(
        "🆘 <b>Как использовать:</b>\n\n"
        "1. <b>Отправь видео/GIF</b>\n"
        "2. <b>Выбери эффект</b>\n"
        "3. <b>Получи WebM файл</b>\n"
        "4. <b>Сохрани файл</b>\n"
        "5. <b>Напиши @Stickers</b>\n"
        "6. <b>/newpack → название → эмодзи</b>\n"
        "7. <b>Загрузи файл</b>\n\n"
        "<i>✅ Файлы соответствуют требованиям Telegram</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.video | F.animation | F.document)
async def handle_media(message: Message):
    """Шаг 1: Получение видео"""
    try:
        await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
        status_msg = await message.answer("📥 <i>Скачиваю файл...</i>", parse_mode=ParseMode.HTML)

        # Определяем файл
        if message.video:
            file_id = message.video.file_id
            file_size = message.video.file_size or 0
            ext = ".mp4"
        elif message.animation:
            file_id = message.animation.file_id
            file_size = message.animation.file_size or 0
            ext = ".gif"
        else:
            file_id = message.document.file_id
            file_size = message.document.file_size or 0
            ext = ".mp4"

        # Проверка размера
        if file_size > MAX_FILE_SIZE:
            await status_msg.edit_text(
                f"❌ <b>Файл слишком большой!</b>\n"
                f"Максимум: {MAX_FILE_SIZE/1024/1024:.0f}MB\n"
                f"Ваш файл: {file_size/1024/1024:.1f}MB",
                parse_mode=ParseMode.HTML
            )
            return

        # Скачиваем
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            input_path = Path(tmp.name)
            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, str(input_path))

        print(f"📥 Файл скачан: {file_size/1024:.1f}KB")

        # ✅ СОХРАНЯЕМ ФАЙЛ
        saved_id = storage.save(message.from_user.id, input_path)

        await status_msg.edit_text(
            "✅ <b>Файл получен!</b>\n\n"
            "✨ <b>Выбери эффект:</b>",
            parse_mode=ParseMode.HTML
        )

        # Создаем кнопки с эффектами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=EFFECTS["none"]["name"], 
                                   callback_data=f"effect_none_{saved_id}"),
                InlineKeyboardButton(text=EFFECTS["slowmo"]["name"], 
                                   callback_data=f"effect_slowmo_{saved_id}")
            ],
            [
                InlineKeyboardButton(text=EFFECTS["fastmo"]["name"], 
                                   callback_data=f"effect_fastmo_{saved_id}"),
                InlineKeyboardButton(text=EFFECTS["snow"]["name"], 
                                   callback_data=f"effect_snow_{saved_id}")
            ],
            [
                InlineKeyboardButton(text=EFFECTS["stars"]["name"], 
                                   callback_data=f"effect_stars_{saved_id}")
            ]
        ])

        await message.answer("Нажми на эффект для применения:", reply_markup=keyboard)
        await status_msg.delete()

        # Удаляем временный файл скачивания
        try:
            os.unlink(input_path)
        except:
            pass

    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)
        print(f"❌ Ошибка: {e}")

@dp.callback_query(F.data.startswith("effect_"))
async def handle_effect(callback: CallbackQuery):
    """Шаг 2: Обработка выбранного эффекта"""
    try:
        # Парсим callback data
        parts = callback.data.split("_")
        if len(parts) < 3:
            await callback.answer("❌ Ошибка данных")
            return

        effect = parts[1]
        file_id = "_".join(parts[2:])

        if effect not in EFFECTS:
            await callback.answer("❌ Неизвестный эффект")
            return

        effect_name = EFFECTS[effect]["name"]
        await callback.answer(f"Выбран: {effect_name}")

        # Получаем сохраненный файл
        try:
            input_path = storage.get(file_id)
        except:
            await callback.message.answer("❌ Файл не найден. Отправь видео снова.")
            return

        processing_msg = await callback.message.answer(
            f"🎬 <i>Создаю стикер с эффектом...</i>\n"
            f"<b>Эффект:</b> {effect_name}",
            parse_mode=ParseMode.HTML
        )

        # Создаем WebM с эффектом
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_out:
            output_path = Path(tmp_out.name)

            success, result, size_kb = await create_sticker_with_effect(input_path, output_path, effect)

            if success:
                # Отправляем файл
                with open(output_path, 'rb') as f:
                    webm_data = f.read()

                filename = f"sticker_{effect}_{int(time.time())}.webm"

                await processing_msg.delete()

                await bot.send_document(
                    callback.message.chat.id,
                    document=BufferedInputFile(webm_data, filename=filename),
                    caption=result,
                    parse_mode=ParseMode.HTML
                )

                # Инструкция по добавлению
                if size_kb <= 256:
                    await callback.message.answer(
                        "💡 <b>Как добавить в Telegram:</b>\n\n"
                        "1. Сохрани этот файл\n"
                        "2. Напиши @Stickers\n"
                        "3. /newpack → название → эмодзи\n"
                        "4. Загрузи файл\n\n"
                        "<i>✅ Файл готов к использованию!</i>",
                        parse_mode=ParseMode.HTML
                    )
            else:
                await callback.message.answer(result, parse_mode=ParseMode.HTML)

            await processing_msg.delete()

            # Очистка
            try:
                os.unlink(output_path)
                storage.delete(file_id)  # Удаляем сохраненный файл
            except:
                pass

    except Exception as e:
        await callback.message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)
        print(f"❌ Ошибка эффекта: {e}")

# ===== ЗАПУСК =====
async def main():
    print("\n" + "=" * 60)
    print("🚀 Бот запущен с эффектами!")
    print("=" * 60)
    print("✨ Доступные эффекты:")
    print("   • 🐌 Замедление (2x медленнее)")
    print("   • ⚡ Ускорение (2x быстрее)")
    print("   • ❄️ Снегопад (анимированный)")
    print("   • ✨ Звёзды (анимированные)")
    print("   • 🎨 Без эффекта")
    print("=" * 60)
    print("🎯 Параметры Telegram:")
    print("   • VP8 кодек (libvpx)")
    print("   • 30 FPS (обязательно)")
    print("   • 512x512 пикселей")
    print("   • ≤256KB размер")
    print("=" * 60)

    me = await bot.get_me()
    print(f"🤖 Бот: @{me.username}")
    print("✅ Готов к работе! Отправь видео и выбери эффект")
    print("=" * 60)

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
        # Очистка временных файлов
        if Path("./temp_files").exists():
            shutil.rmtree("./temp_files")
            print("🧹 Временные файлы удалены")
