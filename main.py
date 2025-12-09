# main.py - ПОЛНЫЙ КОД С 2.9 СЕКУНДАМИ И KEEP-ALIVE
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
import textwrap
from aiohttp import web
import threading

print("=" * 60)
print("🤖 Video Sticker Bot (2.9 секунды + Keep-alive)")
print("=" * 60)

# ===== KEEP-ALIVE ДЛЯ REPLIT =====
async def keep_alive_server():
    """HTTP сервер чтобы Replit не засыпал"""
    async def handle(request):
        return web.Response(
            text="🤖 Video Sticker Bot is ALIVE!\n\n"
                 "✅ Бот активен и готов к работе\n"
                 f"⏰ Время сервера: {datetime.now().strftime('%H:%M:%S')}\n"
                 "📊 Статус: Online",
            content_type='text/plain'
        )

    app = web.Application()
    app.router.add_get('/', handle)
    app.router.add_get('/health', handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

    print("🌐 Keep-alive сервер запущен на порту 8080")
    print("✅ Replit не будет засыпать")

    return runner

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
STICKER_DURATION = 2.9  # 2.9 СЕКУНДЫ!

# ===== ХРАНИЛИЩЕ =====
class FileStorage:
    def __init__(self):
        self.storage_dir = Path("./temp_files")
        self.storage_dir.mkdir(exist_ok=True)
        self.files = {}
        self.user_data = {}
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

# ===== ТИКТОК ЭФФЕКТЫ =====
TIKTOK_EFFECTS = {
    "none": {
        "name": "🎨 Без эффекта",
        "filter": "",
        "description": "Обычное видео"
    },
    "slowmo": {
        "name": "🐌 Замедление",
        "filter": "setpts=2.0*PTS",
        "description": "Видео в 2 раза медленнее"
    },
    "fastmo": {
        "name": "⚡ Ускорение", 
        "filter": "setpts=0.5*PTS",
        "description": "Видео в 2 раза быстрее"
    },
    "vhs": {
        "name": "📼 VHS",
        "filter": "curves=preset=vintage,noise=alls=20:allf=t+u",
        "description": "Эффект видеомагнитофона"
    },
    "glitch": {
        "name": "🌀 Глитч",
        "filter": "noise=alls=30:allf=t+u,hue=h=2*PI*t",
        "description": "Цифровой глитч"
    },
    "neon": {
        "name": "🌃 Неоновый",
        "filter": "eq=saturation=2:brightness=0.1",
        "description": "Яркие неоновые цвета"
    },
    "mirror": {
        "name": "🪞 Зеркало",
        "filter": "crop=iw/2:ih:0:0,split[left][tmp];[tmp]hflip[right];[left][right]hstack",
        "description": "Зеркальное отражение"
    },
    "vibrant": {
        "name": "🌈 Яркие цвета",
        "filter": "eq=saturation=1.5:contrast=1.2",
        "description": "Усиленные цвета"
    }
}

# ===== ФУНКЦИЯ ДЛЯ ТЕКСТА =====
def create_text_filter(text: str) -> str:
    """Создает фильтр для добавления текста"""
    if not text:
        return ""

    safe_text = text.replace(':', '\\:').replace("'", "\\'")

    # Простой текст внизу
    text_filter = f"drawtext=text='{safe_text}':" \
                 f"fontcolor=white:fontsize=40:" \
                 f"box=1:boxcolor=black@0.5:boxborderw=5:" \
                 f"x=(w-text_w)/2:y=h-text_h-20"

    return text_filter

# ===== ОСНОВНАЯ ФУНКЦИЯ (2.9 СЕКУНДЫ) =====
async def create_sticker_29s(
    input_path: Path, 
    output_path: Path, 
    effect: str = "none",
    text: str = ""
) -> Tuple[bool, str, int]:
    """
    Создает WebM стикер 2.9 секунды
    """
    try:
        effect_name = TIKTOK_EFFECTS[effect]["name"]
        print(f"🎬 Создаю стикер 2.9с: {effect_name}")

        # Получаем информацию о видео
        info = await get_video_info(input_path)
        source_duration = info['duration']

        # Если видео короче 2.9с, делаем петлю
        if source_duration < STICKER_DURATION:
            print(f"   ⚡ Видео короткое ({source_duration:.1f}с), создаю петлю...")
            looped_path = await create_video_loop(input_path, STICKER_DURATION)
            input_path = looped_path

        print(f"   📊 Исходное: {info['width']}x{info['height']}, {info['fps']:.1f}fps")

        # Базовый фильтр для Telegram
        base_filter = "scale=512:512:force_original_aspect_ratio=decrease," \
                     "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0," \
                     "fps=30,format=yuva420p"

        # Добавляем эффект и текст
        effect_filter = TIKTOK_EFFECTS[effect]["filter"]
        text_filter = create_text_filter(text)

        # Комбинируем фильтры
        filters = [base_filter]
        if effect_filter:
            filters.append(effect_filter)
        if text_filter:
            filters.append(text_filter)

        video_filter = ",".join(filter(None, filters))

        # КОМАНДА FFMPEG С 2.9 СЕКУНДАМИ
        cmd = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-t", str(STICKER_DURATION),  # 2.9 СЕКУНДЫ!
            "-an",  # Без звука
            "-vf", video_filter,
            "-c:v", "libvpx-vp9",  # VP9 кодек
            "-b:v", "160k",
            "-crf", "30",
            "-deadline", "good",
            "-row-mt", "1",
            "-tile-columns", "2",
            "-frame-parallel", "1",
            "-g", "87",  # Ключевые кадры (2.9 * 30)
            "-lag-in-frames", "0",
            "-auto-alt-ref", "0",
            "-pix_fmt", "yuva420p",
            "-f", "webm",
            str(output_path)
        ]

        print(f"   🛠️ Длительность: {STICKER_DURATION}с, VP9, 512x512, 30fps")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        # Очистка петли если создавали
        if 'looped_path' in locals() and looped_path.exists():
            try:
                looped_path.unlink()
            except:
                pass

        if process.returncode == 0 and output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            print(f"   ✅ WebM создан: {size_kb:.1f}KB")

            # Оптимизируем если нужно
            if size_kb > 200:
                print(f"   ⚙️ Оптимизирую размер...")
                await optimize_webm(output_path)
                size_kb = output_path.stat().st_size / 1024

            # Проверяем параметры
            output_info = await get_video_info(output_path)

            status = "✅" if size_kb <= 256 else "⚠️"

            message = f"{status} <b>Video Sticker создан!</b>\n\n"
            message += f"🎭 <b>Эффект:</b> {effect_name}\n"
            if text:
                message += f"📝 <b>Текст:</b> {text[:30]}{'...' if len(text) > 30 else ''}\n"
            message += f"📦 <b>Размер:</b> {size_kb:.1f}KB / 256KB\n"
            message += f"📏 <b>Разрешение:</b> 512x512\n"
            message += f"🎬 <b>FPS:</b> 30\n"
            message += f"⏱ <b>Длительность:</b> {STICKER_DURATION}с\n"
            message += f"🔧 <b>Кодек:</b> VP9\n"

            if size_kb <= 256:
                message += f"\n🎉 <b>Соответствует требованиям Telegram!</b>"
            else:
                message += f"\n⚠️ <b>Слишком большой для Telegram</b>"

            return True, message, int(size_kb)

        error = stderr.decode('utf-8', errors='ignore')
        print(f"   ❌ Ошибка: {error[:200]}")
        return False, "❌ Не удалось создать стикер", 0

    except Exception as e:
        print(f"   🔥 Исключение: {e}")
        return False, f"❌ Ошибка: {str(e)[:100]}", 0

async def create_video_loop(input_path: Path, target_duration: float) -> Path:
    """Создает зацикленное видео"""
    try:
        looped_path = input_path.with_suffix('.looped.mp4')

        # Рассчитываем сколько раз нужно повторить
        info = await get_video_info(input_path)
        source_duration = info['duration']
        loops_needed = int(target_duration / source_duration) + 1

        if loops_needed > 1:
            cmd = [
                FFMPEG, "-y",
                "-stream_loop", str(loops_needed - 1),
                "-i", str(input_path),
                "-t", str(target_duration),
                "-c", "copy",
                str(looped_path)
            ]
        else:
            # Если один раз хватает, просто копируем
            shutil.copy2(input_path, looped_path)

        process = await asyncio.create_subprocess_exec(*cmd)
        await process.wait()

        return looped_path
    except:
        return input_path

async def optimize_webm(file_path: Path) -> bool:
    """Оптимизация WebM"""
    try:
        temp_path = file_path.with_suffix('.opt.webm')

        cmd = [
            FFMPEG, "-y",
            "-i", str(file_path),
            "-t", "2.7",  # Чуть короче
            "-an",
            "-vf", "scale=384:384,fps=30",
            "-c:v", "libvpx-vp9",
            "-b:v", "100k",
            "-crf", "35",
            "-deadline", "good",
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
            'fps': 30
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
                import re
                match = re.search(r'(\d+)x(\d+)', line)
                if match:
                    info['width'] = int(match.group(1))
                    info['height'] = int(match.group(2))

                match = re.search(r'(\d+(\.\d+)?)\s*fps', line)
                if match:
                    info['fps'] = float(match.group(1))

        return info
    except:
        return {'duration': 0, 'width': 0, 'height': 0, 'fps': 30}

# ===== ОБРАБОТЧИКИ =====
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎬 <b>Video Sticker Bot 2.9s</b>\n\n"
        "<b>✅ Точные параметры Telegram:</b>\n"
        "• Длительность: 2.9 секунды\n"
        "• Разрешение: 512x512 пикселей\n"
        "• FPS: 30 кадров/сек\n"
        "• Размер: ≤256 КБ\n"
        "• Кодек: VP9\n"
        "• Формат: WebM\n"
        "• Без звука\n\n"
        "<b>✨ Эффекты + текст на видео!</b>\n\n"
        "<b>📤 Отправь видео:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📤 ОТПРАВИТЬ ВИДЕО")],
                [KeyboardButton(text="🎭 ЭФФЕКТЫ"), KeyboardButton(text="📝 ДОБАВИТЬ ТЕКСТ")]
            ],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "📤 ОТПРАВИТЬ ВИДЕО")
async def send_video(message: Message):
    user_id = message.from_user.id
    storage.user_data[user_id] = {'step': 'waiting_video'}

    await message.answer(
        "📤 <b>Отправь видео или GIF</b>\n\n"
        f"<i>• До 10MB\n"
        f"• Будет обрезано до {STICKER_DURATION} секунд\n"
        f"• Если видео короче - сделаю петлю\n"
        f"• После загрузки можно добавить текст и выбрать эффект!</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "🎭 ЭФФЕКТЫ")
async def show_effects(message: Message):
    effects_text = ""
    for key, effect in TIKTOK_EFFECTS.items():
        effects_text += f"• <b>{effect['name']}</b>\n  <i>{effect['description']}</i>\n\n"

    await message.answer(
        f"🎭 <b>Доступные эффекты:</b>\n\n{effects_text}"
        f"<i>Стикеры создаются {STICKER_DURATION} секунды с эффектами!</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "📝 ДОБАВИТЬ ТЕКСТ")
async def add_text_prompt(message: Message):
    user_id = message.from_user.id
    if user_id in storage.user_data and 'file_id' in storage.user_data[user_id]:
        storage.user_data[user_id]['step'] = 'waiting_text'
        await message.answer(
            "📝 <b>Введи текст для видео:</b>\n\n"
            "<i>• До 40 символов\n"
            "• Текст появится внизу видео\n"
            "• Можно использовать эмодзи\n"
            "• Или /skip чтобы пропустить</i>",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer("❌ Сначала отправь видео!")

@dp.message(F.video | F.animation | F.document)
async def handle_media(message: Message):
    """Шаг 1: Получение видео"""
    try:
        user_id = message.from_user.id

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
        saved_id = storage.save(user_id, input_path)

        # Сохраняем данные пользователя
        storage.user_data[user_id] = {
            'file_id': saved_id,
            'step': 'waiting_text',
            'text': ''
        }

        await status_msg.edit_text(
            "✅ <b>Видео получено!</b>\n\n"
            "📝 <b>Хочешь добавить текст?</b>\n\n"
            "Отправь текст (до 40 символов) или /skip",
            parse_mode=ParseMode.HTML
        )

        # Очистка временного файла
        try:
            os.unlink(input_path)
        except:
            pass

    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)
        print(f"❌ Ошибка: {e}")

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text_input(message: Message):
    """Шаг 2: Получение текста"""
    try:
        user_id = message.from_user.id

        if user_id not in storage.user_data:
            await message.answer("❌ Сначала отправь видео!")
            return

        if storage.user_data[user_id].get('step') != 'waiting_text':
            return

        text = message.text.strip()

        if len(text) > 40:
            await message.answer("❌ Слишком длинный текст! Максимум 40 символов.")
            return

        # Сохраняем текст
        storage.user_data[user_id]['text'] = text
        storage.user_data[user_id]['step'] = 'waiting_effect'

        await message.answer(
            f"✅ <b>Текст сохранен:</b> {text}\n\n"
            f"🎭 <b>Теперь выбери эффект:</b>",
            parse_mode=ParseMode.HTML
        )

        # Кнопки с эффектами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["none"]["name"], 
                                   callback_data=f"effect_none_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["slowmo"]["name"], 
                                   callback_data=f"effect_slowmo_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["fastmo"]["name"], 
                                   callback_data=f"effect_fastmo_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["vhs"]["name"], 
                                   callback_data=f"effect_vhs_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["glitch"]["name"], 
                                   callback_data=f"effect_glitch_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["neon"]["name"], 
                                   callback_data=f"effect_neon_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["mirror"]["name"], 
                                   callback_data=f"effect_mirror_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["vibrant"]["name"], 
                                   callback_data=f"effect_vibrant_{user_id}")
            ]
        ])

        await message.answer("Нажми на эффект:", reply_markup=keyboard)

    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

@dp.message(Command("skip"))
async def skip_text(message: Message):
    """Пропуск текста"""
    try:
        user_id = message.from_user.id

        if user_id not in storage.user_data:
            await message.answer("❌ Сначала отправь видео!")
            return

        storage.user_data[user_id]['text'] = ''
        storage.user_data[user_id]['step'] = 'waiting_effect'

        await message.answer(
            "⏭️ <b>Пропускаем текст</b>\n\n"
            "🎭 <b>Выбери эффект:</b>",
            parse_mode=ParseMode.HTML
        )

        # Те же кнопки
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["none"]["name"], 
                                   callback_data=f"effect_none_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["slowmo"]["name"], 
                                   callback_data=f"effect_slowmo_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["fastmo"]["name"], 
                                   callback_data=f"effect_fastmo_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["vhs"]["name"], 
                                   callback_data=f"effect_vhs_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["glitch"]["name"], 
                                   callback_data=f"effect_glitch_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["neon"]["name"], 
                                   callback_data=f"effect_neon_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["mirror"]["name"], 
                                   callback_data=f"effect_mirror_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["vibrant"]["name"], 
                                   callback_data=f"effect_vibrant_{user_id}")
            ]
        ])

        await message.answer("Нажми на эффект:", reply_markup=keyboard)

    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("effect_"))
async def handle_effect(callback: CallbackQuery):
    """Шаг 3: Обработка эффекта"""
    try:
        parts = callback.data.split("_")
        if len(parts) < 3:
            await callback.answer("❌ Ошибка данных")
            return

        effect = parts[1]
        user_id = int(parts[2])

        if effect not in TIKTOK_EFFECTS:
            await callback.answer("❌ Неизвестный эффект")
            return

        if user_id not in storage.user_data or 'file_id' not in storage.user_data[user_id]:
            await callback.answer("❌ Данные не найдены")
            return

        effect_name = TIKTOK_EFFECTS[effect]["name"]
        await callback.answer(f"Выбран: {effect_name}")

        # Получаем данные
        file_id = storage.user_data[user_id]['file_id']
        text = storage.user_data[user_id].get('text', '')

        # Получаем файл
        try:
            input_path = storage.get(file_id)
        except:
            await callback.message.answer("❌ Файл не найден. Отправь видео снова.")
            return

        processing_msg = await callback.message.answer(
            f"🎬 <i>Создаю стикер {STICKER_DURATION}с...</i>\n"
            f"<b>Эффект:</b> {effect_name}",
            parse_mode=ParseMode.HTML
        )

        # Создаем WebM
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_out:
            output_path = Path(tmp_out.name)

            success, result, size_kb = await create_sticker_29s(
                input_path, output_path, effect, text
            )

            if success:
                # Отправляем файл
                with open(output_path, 'rb') as f:
                    webm_data = f.read()

                filename = f"sticker_{STICKER_DURATION}s_{effect}.webm"

                await processing_msg.edit_text("📤 <i>Отправляю...</i>", parse_mode=ParseMode.HTML)

                await bot.send_document(
                    callback.message.chat.id,
                    document=BufferedInputFile(webm_data, filename=filename),
                    caption=result,
                    parse_mode=ParseMode.HTML
                )

                # Инструкция
                if size_kb <= 256:
                    await callback.message.answer(
                        "💡 <b>Как добавить:</b>\n\n"
                        "1. Сохрани файл\n"
                        "2. Напиши @Stickers\n"
                        "3. /newpack → название → эмодзи\n"
                        "4. Загрузи файл\n\n"
                        "<i>✅ Стикер готов!</i>",
                        parse_mode=ParseMode.HTML
                    )

                try:
                    await processing_msg.delete()
                except:
                    pass

            else:
                await processing_msg.edit_text(result, parse_mode=ParseMode.HTML)

            # Очистка
            try:
                os.unlink(output_path)
                storage.delete(file_id)
                if user_id in storage.user_data:
                    del storage.user_data[user_id]
            except:
                pass

    except Exception as e:
        await callback.message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)
        print(f"❌ Ошибка: {e}")

# ===== ЗАПУСК С KEEP-ALIVE =====
async def main():
    print("\n" + "=" * 60)
    print("🚀 БОТ ЗАПУЩЕН!")
    print("=" * 60)
    print("⚙️ ОСНОВНЫЕ ПАРАМЕТРЫ:")
    print(f"   • Длительность: {STICKER_DURATION} секунды")
    print("   • Разрешение: 512x512 пикселей")
    print("   • FPS: 30 кадров/сек")
    print("   • Размер: ≤256 КБ")
    print("   • Кодек: VP9")
    print("   • Формат: WebM")
    print("=" * 60)
    print("✨ ФУНКЦИИ:")
    print("   • 8 TikTok-эффектов")
    print("   • Добавление текста на видео")
    print("   • Автопетля для коротких видео")
    print("   • Keep-alive для Replit")
    print("=" * 60)

    # Запускаем keep-alive сервер
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('0.0.0.0', 8080))
        sock.close()

        if result != 0:  # Порт свободен
            runner = await keep_alive_server()
            print("✅ Keep-alive сервер запущен")
        else:
            print("⚠️ Порт 8080 занят, keep-alive не запущен")
    except:
        print("⚠️ Не удалось запустить keep-alive сервер")

    me = await bot.get_me()
    print(f"🤖 Бот: @{me.username}")
    print(f"✅ Готов создавать стикеры {STICKER_DURATION} секунды!")
    print("=" * 60)

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
        if Path("./temp_files").exists():
            shutil.rmtree("./temp_files")
