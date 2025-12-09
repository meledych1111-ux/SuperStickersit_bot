#!/usr/bin/env python3
# main.py - Video Sticker Bot - ФИНАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ
import os
import sys
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Tuple, Dict, Optional, List
import time
from datetime import datetime
import uuid
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
import atexit
import signal

print("=" * 60)
print("🎬 Video Sticker Bot - ФИНАЛЬНАЯ ВЕРСИЯ")
print("=" * 60)

# ===== НАСТРОЙКА ЛОГГИРОВАНИЯ =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ===== KEEP-ALIVE ДЛЯ REPLIT =====
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        response = f"🎬 Video Sticker Bot\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        self.wfile.write(response.encode('utf-8'))

    def log_message(self, format, *args):
        pass

def run_keep_alive():
    """Запуск keep-alive в отдельном потоке"""
    try:
        server = HTTPServer(('0.0.0.0', 3000), KeepAliveHandler)
        logger.info("🌐 Keep-alive сервер запущен на порту 3000")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Ошибка keep-alive: {e}")

def cleanup():
    """Очистка временных файлов"""
    logger.info("🧹 Очистка временных файлов...")
    temp_path = Path("./temp_files")
    if temp_path.exists():
        try:
            shutil.rmtree(temp_path, ignore_errors=True)
        except Exception as e:
            logger.error(f"Ошибка очистки: {e}")

atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda s, f: cleanup())

# Проверяем FFmpeg
FFMPEG = shutil.which("ffmpeg")
if not FFMPEG:
    logger.error("❌ ffmpeg не найден!")
    sys.exit(1)

logger.info(f"✅ FFmpeg: {FFMPEG}")

try:
    from aiogram import Bot, Dispatcher, F, Router
    from aiogram.filters import CommandStart, Command
    from aiogram.types import (
        Message, BufferedInputFile,
        ReplyKeyboardMarkup, KeyboardButton,
        InlineKeyboardMarkup, InlineKeyboardButton,
        CallbackQuery
    )
    from aiogram.enums import ParseMode, ChatAction
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.client.default import DefaultBotProperties
    logger.info("✅ Aiogram загружен")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

# Создаем сессию
session = AiohttpSession()
bot = Bot(
    token=BOT_TOKEN,
    session=session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

router = Router()
dp = Dispatcher()
dp.include_router(router)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
STICKER_DURATION = 2.9  # 2.9 секунды

# ===== ХРАНИЛИЩЕ =====
class FileStorage:
    def __init__(self):
        self.storage_dir = Path("./temp_files")
        self.storage_dir.mkdir(exist_ok=True)
        self.files = {}
        self.user_data = {}
        logger.info(f"📁 Хранилище создано")

    def save(self, user_id: int, file_path: Path) -> str:
        file_id = str(uuid.uuid4())
        user_dir = self.storage_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        saved_path = user_dir / f"{file_id}{file_path.suffix}"
        shutil.copy2(file_path, saved_path)

        self.files[file_id] = {
            'path': saved_path,
            'user_id': user_id,
            'time': time.time()
        }
        return file_id

    def get(self, file_id: str) -> Optional[Path]:
        if file_id in self.files:
            path = self.files[file_id]['path']
            if path.exists():
                return path
        return None

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

# ===== ЗАМЕТНЫЕ ЭФФЕКТЫ КОТОРЫЕ РАБОТАЮТ =====
VIDEO_EFFECTS = {
    "none": {
        "name": "🎬 Оригинал",
        "filter": "",
        "description": "Без изменений"
    },
    "slow": {
        "name": "🐌 Замедление",
        "filter": "setpts=2.0*PTS",
        "description": "Видео в 2 раза медленнее"
    },
    "fast": {
        "name": "⚡ Ускорение", 
        "filter": "setpts=0.5*PTS",
        "description": "Видео в 2 раза быстрее"
    },
    "vibrant": {
        "name": "🌈 Яркие цвета",
        "filter": "eq=saturation=1.8:brightness=0.1",
        "description": "Очень яркие и сочные цвета"
    },
    "vintage": {
        "name": "📻 Винтаж",
        "filter": "curves=preset=vintage",
        "description": "Желто-коричневые тона как старое фото"
    },
    "cinema": {
        "name": "🎥 Кинематограф",
        "filter": "eq=contrast=1.5:brightness=-0.1",
        "description": "Высокая контрастность как в кино"
    },
    "action": {
        "name": "💥 Экшен",
        "filter": "setpts=0.8*PTS, eq=saturation=1.5",
        "description": "Быстрое видео с яркими цветами"
    },
    "noir": {
        "name": "🕵️‍♂️ Фильм-нуар",
        "filter": "format=gray, eq=contrast=1.5",
        "description": "Черно-белое как старые детективы"
    },
    "fantasy": {
        "name": "🧚 Фэнтези",
        "filter": "eq=saturation=1.5, colorbalance=rs=0.3:gs=-0.1",
        "description": "Волшебные розово-зеленые тона"
    },
    "horror": {
        "name": "👻 Хоррор",
        "filter": "eq=brightness=-0.2:contrast=1.3, colorbalance=bm=-0.3",
        "description": "Темное видео с синими тонами"
    },
    "oldfilm": {
        "name": "🎞️ Старая пленка",
        "filter": "curves=preset=vintage, noise=c0s=8",
        "description": "Старое видео с шумом пленки"
    },
    "scifi": {
        "name": "👽 Sci-Fi",
        "filter": "colorbalance=rs=-0.2:bs=0.3, eq=contrast=1.4",
        "description": "Синие футуристические тона"
    }
}

# ===== ЦВЕТА ТЕКСТА =====
TEXT_COLORS = {
    "white": "⚪ Белый",
    "black": "⚫ Черный",
    "yellow": "💛 Желтый",
    "red": "🔴 Красный",
    "blue": "🔵 Синий",
    "green": "🟢 Зеленый",
    "pink": "🌸 Розовый",
    "orange": "🟠 Оранжевый"
}

# ===== РАЗМЕРЫ ТЕКСТА =====
TEXT_SIZES = {
    "small": "📏 Маленький",
    "medium": "📐 Средний",
    "large": "📊 Большой",
    "xlarge": "💥 Огромный"
}

# ===== РАМКИ =====
FRAMES = {
    "none": {
        "name": "🖼️ Без рамки",
        "filter": "",
        "description": "Без рамки"
    },
    "fire": {
        "name": "🔥 Огненная",
        "filter": "drawbox=x=0:y=0:w=512:h=15:c=red@0.8:t=fill,"
                  "drawbox=x=0:y=497:w=512:h=15:c=orange@0.7:t=fill,"
                  "drawbox=x=0:y=0:w=15:h=512:c=yellow@0.6:t=fill,"
                  "drawbox=x=497:y=0:w=15:h=512:c=red@0.8:t=fill",
        "description": "Огненная рамка"
    },
    "neon": {
        "name": "💡 Неоновая",
        "filter": "drawbox=x=0:y=0:w=512:h=8:c=cyan@0.7:t=fill,"
                  "drawbox=x=0:y=504:w=512:h=8:c=cyan@0.7:t=fill,"
                  "drawbox=x=0:y=0:w=8:h=512:c=cyan@0.7:t=fill,"
                  "drawbox=x=504:y=0:w=8:h=512:c=cyan@0.7:t=fill",
        "description": "Неоновая рамка"
    },
    "rainbow": {
        "name": "🌈 Радужная",
        "filter": "drawbox=x=0:y=0:w=512:h=10:c=red@0.6:t=fill,"
                  "drawbox=x=0:y=502:w=512:h=10:c=blue@0.6:t=fill,"
                  "drawbox=x=0:y=0:w=10:h=512:c=green@0.6:t=fill,"
                  "drawbox=x=502:y=0:w=10:h=512:c=yellow@0.6:t=fill",
        "description": "Радужная рамка"
    }
}

# ===== ФУНКЦИЯ ДЛЯ ТЕКСТА =====
def create_text_filter_advanced(text: str, color: str = "white", size: str = "medium") -> str:
    """Создает фильтр для текста с цветами и размерами"""
    if not text or len(text.strip()) == 0:
        return ""

    # Экранируем текст
    safe_text = text.replace("'", "\\'").replace(":", "\\:")
    if len(safe_text) > 25:
        safe_text = safe_text[:22] + "..."

    # Определяем размер
    if size == "small":
        font_size = 28
        y_offset = 30
    elif size == "large":
        font_size = 44
        y_offset = 50
    elif size == "xlarge":
        font_size = 52
        y_offset = 60
    else:  # medium
        font_size = 36
        y_offset = 40

    # Определяем цвет
    if color == "black":
        font_color = "black"
        outline_color = "white"
    elif color == "white":
        font_color = "white"
        outline_color = "black"
    elif color == "yellow":
        font_color = "yellow"
        outline_color = "black"
    elif color == "red":
        font_color = "red"
        outline_color = "white"
    elif color == "blue":
        font_color = "blue"
        outline_color = "white"
    elif color == "green":
        font_color = "green"
        outline_color = "black"
    elif color == "pink":
        font_color = "magenta"
        outline_color = "black"
    elif color == "orange":
        font_color = "orange"
        outline_color = "black"
    else:
        font_color = "white"
        outline_color = "black"

    # Создаем фильтр с контуром
    return (f"drawtext=text='{safe_text}':"
            f"fontcolor={font_color}:"
            f"fontsize={font_size}:"
            f"x=(w-text_w)/2:"
            f"y=h-text_h-{y_offset}:"
            f"box=1:"
            f"boxcolor={outline_color}@0.3:"
            f"boxborderw=3")

# ===== ФУНКЦИЯ СОЗДАНИЯ СТИКЕРА =====
async def create_sticker_simple(
    input_path: Path,
    output_path: Path,
    effect: str = "none",
    frame: str = "none",
    text: str = "",
    text_color: str = "white",
    text_size: str = "medium"
) -> Tuple[bool, str, int]:
    """Функция создания стикера"""
    try:
        logger.info(f"🎬 Создаю стикер: эффект={effect}, рамка={frame}")

        # Базовый фильтр
        filters = [
            "scale=512:512:force_original_aspect_ratio=decrease",
            "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0",
            "fps=30"
        ]

        # Добавляем эффект
        if effect in VIDEO_EFFECTS:
            effect_filter = VIDEO_EFFECTS[effect]["filter"]
            if effect_filter:
                filters.append(effect_filter)

        # Рамка
        if frame in FRAMES:
            frame_filter = FRAMES[frame]["filter"]
            if frame_filter:
                filters.append(frame_filter)

        # Текст
        if text:
            text_filter = create_text_filter_advanced(text, text_color, text_size)
            if text_filter:
                filters.append(text_filter)

        # Формируем фильтр
        video_filter = ",".join([f for f in filters if f])

        # Команда FFmpeg
        cmd = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-t", str(STICKER_DURATION),
            "-an",
            "-vf", video_filter,
            "-c:v", "libvpx-vp9",
            "-b:v", "150k",
            "-crf", "30",
            "-deadline", "good",
            "-pix_fmt", "yuva420p",
            "-f", "webm",
            str(output_path)
        ]

        # Запускаем
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and output_path.exists():
            size_kb = output_path.stat().st_size / 1024

            # Формируем результат
            result_msg = f"✅ <b>Стикер создан!</b>\n\n"

            # Эффект
            effect_name = VIDEO_EFFECTS.get(effect, {}).get("name", effect)
            effect_desc = VIDEO_EFFECTS.get(effect, {}).get("description", "")
            result_msg += f"🎬 <b>Эффект:</b> {effect_name}\n"
            result_msg += f"📝 <i>{effect_desc}</i>\n"

            # Рамка
            frame_name = FRAMES.get(frame, {}).get("name", frame)
            result_msg += f"🖼️ <b>Рамка:</b> {frame_name}\n"

            if text:
                result_msg += f"📝 <b>Текст:</b> {text[:20]}{'...' if len(text) > 20 else ''}\n"
                result_msg += f"🎨 <b>Цвет:</b> {TEXT_COLORS.get(text_color, 'Белый')}\n"
                result_msg += f"📏 <b>Размер:</b> {TEXT_SIZES.get(text_size, 'Средний')}\n"

            result_msg += f"📦 <b>Размер файла:</b> {size_kb:.1f}KB / 256KB\n"
            result_msg += f"📐 <b>Разрешение:</b> 512x512\n"
            result_msg += f"⏱ <b>Длительность:</b> {STICKER_DURATION}с\n"

            if size_kb <= 256:
                result_msg += f"\n🎉 <b>Соответствует требованиям Telegram!</b>"
            else:
                result_msg += f"\n⚠️ <b>Слишком большой, но можно попробовать отправить</b>"

            return True, result_msg, int(size_kb)
        else:
            error = stderr.decode('utf-8', errors='ignore')[:300]
            logger.error(f"FFmpeg ошибка: {error}")
            return False, f"❌ Ошибка FFmpeg", 0

    except Exception as e:
        logger.error(f"🔥 Ошибка в create_sticker_simple: {e}")
        return False, f"❌ Ошибка: {str(e)[:100]}", 0

# ===== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ПАРСИНГА =====
def parse_simple_callback(data: str, prefix: str) -> Tuple[str, int]:
    """Простой парсер callback data"""
    try:
        # Убираем префикс
        rest = data[len(prefix):]

        # Разделяем на части
        parts = rest.split("_")

        # Если частей 2 или больше, значит есть значение и user_id
        if len(parts) >= 2:
            # Значение - все кроме последней части
            value = "_".join(parts[:-1])
            user_id = int(parts[-1])
            return value, user_id
        elif len(parts) == 1:
            # Только user_id
            return "", int(parts[0])
        else:
            return "", 0
    except Exception as e:
        logger.error(f"Ошибка парсинга {data}: {e}")
        return "", 0

# ===== ОБРАБОТЧИКИ =====
@router.message(CommandStart())
async def start_command(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "🎬 <b>Video Sticker Bot 2.9s</b>\n\n"
        "✅ <b>Создаю стикеры для Telegram:</b>\n"
        "• 512x512 пикселей\n"
        "• 2.9 секунды\n"
        "• WebM формат\n"
        "• До 256KB\n\n"
        "✨ <b>Функции:</b>\n"
        "• 8 цветов текста\n"
        "• 4 размера текста\n"
        "• 12 ЗАМЕТНЫХ эффектов\n"
        "• 4 стильные рамки\n\n"
        "📤 <b>Отправь видео для начала!</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📤 Отправить видео")],
                [KeyboardButton(text="✨ Эффекты"), KeyboardButton(text="🖼️ Рамки")]
            ],
            resize_keyboard=True
        )
    )

@router.message(F.text == "📤 Отправить видео")
async def send_video_handler(message: Message):
    """Обработчик кнопки отправки видео"""
    user_id = message.from_user.id
    storage.user_data[user_id] = {'step': 'waiting_video'}

    await message.answer(
        "📤 <b>Отправь видео, GIF или видео-файл</b>\n\n"
        "<i>• До 20MB\n"
        "• Будет обрезано до 2.9 секунд\n"
        "• Можно добавить текст</i>",
        parse_mode=ParseMode.HTML
    )

@router.message(F.text == "✨ Эффекты")
async def show_effects(message: Message):
    """Показывает доступные эффекты"""
    effects_text = "<b>🎬 Все видео эффекты:</b>\n\n"
    effects_text += "<i>Каждый эффект ЗАМЕТНО меняет видео:</i>\n\n"

    effects_list = [
        ("🎬 Оригинал", "Без изменений"),
        ("🐌 Замедление", "Видео в 2 раза медленнее"),
        ("⚡ Ускорение", "Видео в 2 раза быстрее"),
        ("🌈 Яркие цвета", "Очень яркие и сочные цвета"),
        ("📻 Винтаж", "Желто-коричневые тона как старое фото"),
        ("🎥 Кинематограф", "Высокая контрастность как в кино"),
        ("💥 Экшен", "Быстрое видео с яркими цветами"),
        ("🕵️‍♂️ Фильм-нуар", "Черно-белое как старые детективы"),
        ("🧚 Фэнтези", "Волшебные розово-зеленые тона"),
        ("👻 Хоррор", "Темное видео с синими тонами"),
        ("🎞️ Старая пленка", "Старое видео с шумом пленки"),
        ("👽 Sci-Fi", "Синие футуристические тона")
    ]

    for name, desc in effects_list:
        effects_text += f"<b>{name}</b>\n<i>{desc}</i>\n\n"

    await message.answer(
        f"{effects_text}",
        parse_mode=ParseMode.HTML
    )

@router.message(F.text == "🖼️ Рамки")
async def show_frames(message: Message):
    """Показывает доступные рамки"""
    frames_text = "<b>🖼️ Доступные рамки:</b>\n\n"
    for key, frame in FRAMES.items():
        frames_text += f"<b>{frame['name']}</b>\n<i>{frame['description']}</i>\n\n"

    await message.answer(
        frames_text,
        parse_mode=ParseMode.HTML
    )

@router.message(Command("effects"))
async def effects_command(message: Message):
    """Команда для просмотра эффектов"""
    await show_effects(message)

@router.message(F.video | F.animation | F.document)
async def handle_video(message: Message):
    """Обработка входящего видео"""
    try:
        user_id = message.from_user.id

        if user_id not in storage.user_data or storage.user_data[user_id].get('step') != 'waiting_video':
            await message.answer("ℹ️ Нажми '📤 Отправить видео' для начала")
            return

        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

        # Определяем тип файла
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
            await message.answer(f"❌ <b>Файл слишком большой!</b>\nМаксимум: {MAX_FILE_SIZE/1024/1024:.0f}MB")
            return

        status_msg = await message.answer("📥 <i>Скачиваю файл...</i>", parse_mode=ParseMode.HTML)

        # Скачиваем файл
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            input_path = Path(tmp.name)
            try:
                file = await bot.get_file(file_id)
                await bot.download_file(file.file_path, str(input_path))
                logger.info(f"✅ Файл скачан: {input_path.stat().st_size/1024:.1f}KB")
            except Exception as e:
                await status_msg.edit_text(f"❌ <b>Ошибка скачивания:</b> {e}")
                return

        if not input_path.exists() or input_path.stat().st_size == 0:
            await status_msg.edit_text("❌ <b>Файл пустой или поврежден</b>")
            try:
                input_path.unlink()
            except:
                pass
            return

        # Сохраняем в хранилище
        saved_id = storage.save(user_id, input_path)

        # Сохраняем данные пользователя
        storage.user_data[user_id] = {
            'file_id': saved_id,
            'step': 'waiting_text',
            'text': '',
            'effect': 'none',
            'frame': 'none',
            'text_color': 'white',
            'text_size': 'medium'
        }

        await status_msg.edit_text(
            "✅ <b>Видео получено!</b>\n\n"
            "📝 <b>Хочешь добавить текст на видео?</b>\n\n"
            "Отправь текст (до 25 символов) или нажми /skip",
            parse_mode=ParseMode.HTML
        )

        try:
            input_path.unlink()
        except:
            pass

    except Exception as e:
        logger.error(f"❌ Ошибка в handle_video: {e}")
        await message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    """Обработка текста для видео"""
    try:
        user_id = message.from_user.id

        if user_id not in storage.user_data:
            await message.answer("❌ Сначала отправь видео!")
            return

        if storage.user_data[user_id].get('step') != 'waiting_text':
            return

        text = message.text.strip()
        if len(text) == 0:
            await message.answer("❌ Текст не может быть пустым!")
            return

        if len(text) > 25:
            await message.answer("❌ Слишком длинный текст! Максимум 25 символов.")
            return

        storage.user_data[user_id]['text'] = text
        storage.user_data[user_id]['step'] = 'waiting_color'

        # Клавиатура с цветами текста
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        row = []
        for color_key, color_name in TEXT_COLORS.items():
            row.append(InlineKeyboardButton(
                text=color_name,
                callback_data=f"color_{color_key}_{user_id}"
            ))
            if len(row) == 2:
                keyboard.inline_keyboard.append(row)
                row = []
        if row:
            keyboard.inline_keyboard.append(row)

        await message.answer(
            f"✅ <b>Текст сохранен:</b> {text}\n\n"
            f"🎨 <b>Теперь выбери цвет текста:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в handle_text: {e}")
        await message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

@router.message(Command("skip"))
async def skip_text(message: Message):
    """Пропуск добавления текста"""
    try:
        user_id = message.from_user.id

        if user_id not in storage.user_data:
            await message.answer("❌ Сначала отправь видео!")
            return

        storage.user_data[user_id]['text'] = ''
        storage.user_data[user_id]['step'] = 'waiting_color'

        # Клавиатура с цветами текста
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        row = []
        for color_key, color_name in TEXT_COLORS.items():
            row.append(InlineKeyboardButton(
                text=color_name,
                callback_data=f"color_{color_key}_{user_id}"
            ))
            if len(row) == 2:
                keyboard.inline_keyboard.append(row)
                row = []
        if row:
            keyboard.inline_keyboard.append(row)

        await message.answer(
            "⏭️ <b>Пропускаем текст</b>\n\n"
            "🎨 <b>Выбери цвет текста:</b>\n"
            "<i>Текст не будет добавлен, но выбери цвет для продолжения</i>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в skip_text: {e}")
        await message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("color_"))
async def handle_color(callback: CallbackQuery):
    """Обработка выбора цвета текста"""
    try:
        await callback.answer()

        color, user_id = parse_simple_callback(callback.data, "color_")

        if color not in TEXT_COLORS:
            return

        if user_id not in storage.user_data:
            return

        # Сохраняем цвет
        storage.user_data[user_id]['text_color'] = color
        storage.user_data[user_id]['step'] = 'waiting_size'

        # Показываем выбор размера
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        row = []
        for size_key, size_name in TEXT_SIZES.items():
            row.append(InlineKeyboardButton(
                text=size_name,
                callback_data=f"size_{size_key}_{user_id}"
            ))
            if len(row) == 2:
                keyboard.inline_keyboard.append(row)
                row = []
        if row:
            keyboard.inline_keyboard.append(row)

        await callback.message.edit_text(
            f"✅ <b>Цвет выбран:</b> {TEXT_COLORS[color]}\n\n"
            f"📏 <b>Теперь выбери размер текста:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в handle_color: {e}")

@router.callback_query(F.data.startswith("size_"))
async def handle_size(callback: CallbackQuery):
    """Обработка выбора размера текста"""
    try:
        await callback.answer()

        size, user_id = parse_simple_callback(callback.data, "size_")

        if size not in TEXT_SIZES:
            return

        if user_id not in storage.user_data:
            return

        # Сохраняем размер
        storage.user_data[user_id]['text_size'] = size
        storage.user_data[user_id]['step'] = 'waiting_effect'

        # Показываем все эффекты сразу
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        row = []

        # Все эффекты
        all_effects = list(VIDEO_EFFECTS.items())
        for i, (effect_key, effect_data) in enumerate(all_effects):
            row.append(InlineKeyboardButton(
                text=effect_data['name'],
                callback_data=f"effect_{effect_key}_{user_id}"
            ))
            if len(row) == 2:
                keyboard.inline_keyboard.append(row)
                row = []
        if row:
            keyboard.inline_keyboard.append(row)

        await callback.message.edit_text(
            f"✅ <b>Размер выбран:</b> {TEXT_SIZES[size]}\n\n"
            f"🎬 <b>Теперь выбери видео эффект:</b>\n\n"
            f"<i>Каждый эффект ЗАМЕТНО меняет видео!</i>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в handle_size: {e}")

@router.callback_query(F.data.startswith("effect_"))
async def handle_effect(callback: CallbackQuery):
    """Обработка выбора эффекта"""
    try:
        await callback.answer()

        effect, user_id = parse_simple_callback(callback.data, "effect_")

        # Проверяем существует ли эффект
        if effect not in VIDEO_EFFECTS:
            logger.error(f"❌ Неизвестный эффект: {effect}")
            await callback.answer(f"❌ Неизвестный эффект", show_alert=True)
            return

        if user_id not in storage.user_data:
            logger.error(f"❌ User {user_id} не найден")
            return

        # Получаем данные эффекта
        effect_data = VIDEO_EFFECTS[effect]

        # Сохраняем эффект
        storage.user_data[user_id]['effect'] = effect
        storage.user_data[user_id]['step'] = 'waiting_frame'

        # Показываем выбор рамки с пояснением об эффекте
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        row = []
        for frame_key, frame in FRAMES.items():
            row.append(InlineKeyboardButton(
                text=frame["name"],
                callback_data=f"frame_{frame_key}_{user_id}"
            ))
            if len(row) == 2:
                keyboard.inline_keyboard.append(row)
                row = []
        if row:
            keyboard.inline_keyboard.append(row)

        await callback.message.edit_text(
            f"✅ <b>Эффект выбран:</b> {effect_data['name']}\n\n"
            f"📝 <i>{effect_data['description']}</i>\n\n"
            f"🖼️ <b>Теперь выбери рамку:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в handle_effect: {e}")

@router.callback_query(F.data.startswith("frame_"))
async def handle_frame(callback: CallbackQuery):
    """Обработка выбора рамки и создание стикера"""
    try:
        await callback.answer()

        frame, user_id = parse_simple_callback(callback.data, "frame_")

        if frame not in FRAMES:
            return

        if user_id not in storage.user_data:
            return

        # Получаем все данные
        file_id = storage.user_data[user_id]['file_id']
        effect = storage.user_data[user_id]['effect']
        text = storage.user_data[user_id].get('text', '')
        text_color = storage.user_data[user_id].get('text_color', 'white')
        text_size = storage.user_data[user_id].get('text_size', 'medium')

        # Получаем файл
        input_path = storage.get(file_id)
        if input_path is None or not input_path.exists():
            await callback.message.answer("❌ Файл не найден. Отправь видео заново.")
            return

        # Получаем имена
        effect_data = VIDEO_EFFECTS.get(effect, {})
        effect_name = effect_data.get('name', effect)
        effect_desc = effect_data.get('description', '')

        frame_name = FRAMES[frame]["name"]

        await bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VIDEO)

        processing_msg = await callback.message.answer(
            f"🎬 <b>Создаю стикер...</b>\n\n"
            f"✨ <i>Эффект:</i> {effect_name}\n"
            f"📝 <i>{effect_desc}</i>\n"
            f"🖼️ <i>Рамка:</i> {frame_name}\n"
            f"📝 <i>Текст:</i> {text[:15] if text else 'нет'}\n"
            f"🎨 <i>Цвет:</i> {TEXT_COLORS.get(text_color, 'Белый')}\n"
            f"📏 <i>Размер:</i> {TEXT_SIZES.get(text_size, 'Средний')}\n\n"
            f"⏳ <i>Обработка...</i>",
            parse_mode=ParseMode.HTML
        )

        # Создаем временный файл для результата
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            output_path = Path(tmp.name)

        # Создаем стикер
        success, result_text, size_kb = await create_sticker_simple(
            input_path, output_path, effect, frame, text, text_color, text_size
        )

        if success:
            await processing_msg.edit_text("📤 <i>Отправляю файл...</i>", parse_mode=ParseMode.HTML)

            try:
                # Читаем файл
                with open(output_path, 'rb') as f:
                    webm_data = f.read()

                # Генерируем имя файла
                timestamp = int(time.time())
                filename = f"sticker_{timestamp}.webm"

                # Отправляем файл
                await bot.send_document(
                    callback.message.chat.id,
                    document=BufferedInputFile(webm_data, filename=filename),
                    caption=result_text,
                    parse_mode=ParseMode.HTML
                )

                # Инструкция
                if size_kb <= 256:
                    await callback.message.answer(
                        "💡 <b>Как добавить стикер:</b>\n\n"
                        "1. Сохрани файл\n"
                        "2. Напиши @Stickers\n"
                        "3. /newpack → название → эмодзи\n"
                        "4. Загрузи файл\n\n"
                        "<i>✅ Готово! Стикер добавлен</i>",
                        parse_mode=ParseMode.HTML
                    )

            except Exception as e:
                await processing_msg.edit_text(f"❌ <b>Ошибка отправки:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)
        else:
            await processing_msg.edit_text(result_text, parse_mode=ParseMode.HTML)

        # Очистка
        try:
            if output_path.exists():
                output_path.unlink()
            storage.delete(file_id)
            if user_id in storage.user_data:
                del storage.user_data[user_id]
        except Exception as e:
            logger.error(f"Ошибка очистки: {e}")

        # Кнопка для нового видео
        await callback.message.answer(
            "🔄 <b>Хочешь создать еще один стикер?</b>\n\n"
            "Нажми /start или кнопку ниже",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📤 Новое видео")],
                    [KeyboardButton(text="/start")]
                ],
                resize_keyboard=True
            )
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в handle_frame: {e}")
        await callback.message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

@router.message(F.text == "📤 Новое видео")
async def new_video_handler(message: Message):
    """Начать с чистого листа"""
    user_id = message.from_user.id

    # Очищаем старые данные
    if user_id in storage.user_data:
        file_id = storage.user_data[user_id].get('file_id')
        if file_id:
            storage.delete(file_id)
        del storage.user_data[user_id]

    storage.user_data[user_id] = {'step': 'waiting_video'}

    await message.answer(
        "🔄 <b>Начинаем заново!</b>\n\n"
        "📤 <b>Отправь видео, GIF или видео-файл</b>\n\n"
        "<i>• До 20MB\n"
        "• Будет обрезано до 2.9 секунд</i>",
        parse_mode=ParseMode.HTML
    )

# ===== ЗАПУСК БОТА =====
async def main():
    """Основная функция запуска"""
    print("\n" + "=" * 60)
    print("🚀 ЗАПУСК VIDEO STICKER BOT - ФИНАЛЬНАЯ ВЕРСИЯ")
    print("=" * 60)
    print("✅ 8 цветов текста")
    print("✅ 4 размера текста")
    print("✅ 12 ЗАМЕТНЫХ эффектов")
    print("✅ 4 стильные рамки")
    print("✅ Все ошибки исправлены")
    print("=" * 60)

    # Очищаем старые файлы
    cleanup()

    # Запускаем keep-alive
    try:
        keep_alive_thread = threading.Thread(target=run_keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("✅ Keep-alive запущен на порту 3000")
    except Exception as e:
        logger.error(f"⚠️ Ошибка keep-alive: {e}")

    # Получаем информацию о боте
    me = await bot.get_me()
    logger.info(f"🤖 Бот: @{me.username}")
    logger.info("✅ Бот запущен!")

    # Запускаем бота
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")

if __name__ == "__main__":
    # Очищаем при запуске
    cleanup()

    # Создаем папку temp_files
    temp_dir = Path("./temp_files")
    temp_dir.mkdir(exist_ok=True)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
        cleanup()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        cleanup()
        sys.exit(1)
