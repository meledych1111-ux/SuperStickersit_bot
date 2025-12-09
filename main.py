#!/usr/bin/env python3
# main.py - Video Sticker Bot с исправленными путями
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
import json
import subprocess

print("=" * 60)
print("🤖 Video Sticker Bot 2.9s - РАБОЧАЯ ВЕРСИЯ")
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
        response = f"🤖 Video Sticker Bot v2.9\n⏰ {datetime.now().strftime('%H:%M:%S')}\n✅ Active"
        self.wfile.write(response.encode('utf-8'))

    def log_message(self, format, *args):
        pass

def run_keep_alive():
    """Запуск keep-alive в отдельном потоке"""
    try:
        server = HTTPServer(('0.0.0.0', 3000), KeepAliveHandler)  # Изменен порт на 3000
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
        CallbackQuery, FSInputFile
    )
    from aiogram.enums import ParseMode, ChatAction
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.client.default import DefaultBotProperties

    logger.info("✅ Aiogram 3.22 загружен")
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
TARGET_SIZE = 256 * 1024  # 256KB
STICKER_DURATION = 2.9  # 2.9 секунды

# ===== ХРАНИЛИЩЕ С ИСПРАВЛЕННЫМИ ПУТЯМИ =====
class FileStorage:
    def __init__(self):
        self.storage_dir = Path("./temp_files")
        self.storage_dir.mkdir(exist_ok=True)
        self.files = {}
        self.user_data = {}
        logger.info(f"📁 Хранилище создано: {self.storage_dir.absolute()}")

    def save(self, user_id: int, file_path: Path) -> str:
        """Сохраняет файл и возвращает его ID"""
        file_id = str(uuid.uuid4())
        user_dir = self.storage_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)  # Важно: parents=True!

        saved_path = user_dir / f"{file_id}{file_path.suffix}"
        shutil.copy2(file_path, saved_path)

        self.files[file_id] = {
            'path': saved_path,
            'user_id': user_id,
            'time': time.time(),
            'size': saved_path.stat().st_size
        }
        logger.info(f"💾 Файл сохранен: {file_id} -> {saved_path}")
        return file_id

    def get(self, file_id: str) -> Optional[Path]:
        """Возвращает путь к файлу"""
        if file_id in self.files:
            path = self.files[file_id]['path']
            if path.exists():
                return path
            else:
                logger.error(f"Файл не существует: {path}")
        return None

    def delete(self, file_id: str):
        """Удаляет файл"""
        if file_id in self.files:
            try:
                path = self.files[file_id]['path']
                if path.exists():
                    path.unlink()
                    logger.info(f"🗑️ Удален: {path}")
            except Exception as e:
                logger.error(f"Ошибка удаления {file_id}: {e}")
            del self.files[file_id]

storage = FileStorage()

# ===== ПРОСТЫЕ ЭФФЕКТЫ =====
VIDEO_EFFECTS = {
    "none": {"name": "🎬 Оригинал", "filter": "", "description": "Без эффектов"},
    "slowmo": {"name": "🐌 Замедление", "filter": "setpts=1.5*PTS", "description": "Замедленное видео"},
    "fastmo": {"name": "⚡ Ускорение", "filter": "setpts=0.7*PTS", "description": "Ускоренное видео"},
    "vibrant": {"name": "🌈 Яркие цвета", "filter": "eq=saturation=1.3:contrast=1.1", "description": "Более яркие цвета"},
    "vintage": {"name": "📻 Винтаж", "filter": "curves=preset=vintage", "description": "Винтажный эффект"}
}

# ===== ПРОСТЫЕ РАМКИ =====
FRAME_EFFECTS = {
    "none": {"name": "🖼️ Без рамки", "filter": "", "description": "Без рамки"},
    "fire": {"name": "🔥 Огненная", "filter": "drawbox=x=0:y=0:w=512:h=10:c=red:t=fill,drawbox=x=0:y=502:w=512:h=10:c=orange:t=fill,drawbox=x=0:y=0:w=10:h=512:c=yellow:t=fill,drawbox=x=502:y=0:w=10:h=512:c=red:t=fill", "description": "Огненная рамка"},
    "neon": {"name": "💡 Неоновая", "filter": "drawbox=x=0:y=0:w=512:h=5:c=cyan:t=fill,drawbox=x=0:y=507:w=512:h=5:c=cyan:t=fill,drawbox=x=0:y=0:w=5:h=512:c=cyan:t=fill,drawbox=x=507:y=0:w=5:h=512:c=cyan:t=fill", "description": "Неоновая рамка"},
    "rainbow": {"name": "🌈 Радужная", "filter": "drawbox=x=0:y=0:w=512:h=15:c=red:t=fill,drawbox=x=0:y=497:w=512:h=15:c=blue:t=fill,drawbox=x=0:y=0:w=15:h=512:c=green:t=fill,drawbox=x=497:y=0:w=15:h=512:c=yellow:t=fill", "description": "Радужная рамка"}
}

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
async def get_video_info(file_path: Path) -> Dict:
    """Получает информацию о видео"""
    try:
        cmd = [FFMPEG, "-i", str(file_path), "-hide_banner"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        output = stderr.decode('utf-8', errors='ignore')

        info = {'duration': 0, 'width': 0, 'height': 0, 'fps': 30}

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

        return info
    except Exception as e:
        logger.error(f"Ошибка получения информации: {e}")
        return {'duration': 0, 'width': 0, 'height': 0, 'fps': 30}

async def run_ffmpeg(cmd: List[str], timeout: int = 30) -> Tuple[bool, str]:
    """Запускает FFmpeg команду"""
    try:
        logger.info(f"🚀 Запускаю FFmpeg: {' '.join(cmd[:5])}...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return False, "Таймаут выполнения"

        if proc.returncode == 0:
            return True, "Успешно"
        else:
            error = stderr.decode('utf-8', errors='ignore')[:200]
            return False, f"Код ошибки: {proc.returncode}, Ошибка: {error}"
    except Exception as e:
        return False, f"Исключение: {str(e)}"

async def create_sticker_simple(
    input_path: Path,
    output_path: Path,
    effect: str = "none",
    frame: str = "none",
    text: str = ""
) -> Tuple[bool, str, int]:
    """Простая функция создания стикера"""
    try:
        logger.info(f"🎬 Создаю стикер из: {input_path}")

        # Получаем информацию о видео
        info = await get_video_info(input_path)
        if info['duration'] == 0:
            return False, "❌ Не удалось определить длительность видео", 0

        # Готовим фильтры
        base_filter = "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0,fps=30"

        # Добавляем эффект
        effect_filter = VIDEO_EFFECTS[effect]["filter"]
        if effect_filter:
            base_filter += f",{effect_filter}"

        # Добавляем рамку
        frame_filter = FRAME_EFFECTS[frame]["filter"]
        if frame_filter:
            base_filter += f",{frame_filter}"

        # Добавляем текст если есть
        if text and len(text) > 0:
            safe_text = text.replace("'", "\\'").replace(":", "\\:")
            if len(safe_text) > 30:
                safe_text = safe_text[:27] + "..."
            text_filter = f"drawtext=text='{safe_text}':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=h-text_h-30:box=1:boxcolor=black@0.5"
            base_filter += f",{text_filter}"

        # Команда FFmpeg
        cmd = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-t", str(min(STICKER_DURATION, info['duration'])),
            "-an",  # Без звука
            "-vf", base_filter,
            "-c:v", "libvpx-vp9",
            "-b:v", "150k",
            "-crf", "30",
            "-deadline", "good",
            "-pix_fmt", "yuva420p",
            "-f", "webm",
            str(output_path)
        ]

        # Запускаем кодирование
        success, message = await run_ffmpeg(cmd)

        if success and output_path.exists():
            size_kb = output_path.stat().st_size / 1024

            # Если слишком большой, оптимизируем
            if size_kb > 256:
                logger.info(f"⚙️ Оптимизирую {size_kb:.1f}KB -> 256KB")
                opt_cmd = [
                    FFMPEG, "-y",
                    "-i", str(output_path),
                    "-c:v", "libvpx-vp9",
                    "-b:v", "100k",
                    "-crf", "35",
                    "-deadline", "good",
                    "-f", "webm",
                    str(output_path.with_suffix('.opt.webm'))
                ]

                opt_success, _ = await run_ffmpeg(opt_cmd)
                if opt_success and output_path.with_suffix('.opt.webm').exists():
                    opt_size = output_path.with_suffix('.opt.webm').stat().st_size / 1024
                    if opt_size <= 256:
                        output_path.unlink()
                        output_path.with_suffix('.opt.webm').rename(output_path)
                        size_kb = opt_size

            result_msg = f"✅ <b>Стикер создан!</b>\n\n"
            result_msg += f"🎬 <b>Эффект:</b> {VIDEO_EFFECTS[effect]['name']}\n"
            result_msg += f"🖼️ <b>Рамка:</b> {FRAME_EFFECTS[frame]['name']}\n"
            if text:
                result_msg += f"📝 <b>Текст:</b> {text[:20]}{'...' if len(text) > 20 else ''}\n"
            result_msg += f"📦 <b>Размер:</b> {size_kb:.1f}KB / 256KB\n"
            result_msg += f"⏱ <b>Длительность:</b> {min(STICKER_DURATION, info['duration']):.1f}с\n"

            if size_kb <= 256:
                result_msg += f"\n🎉 <b>Соответствует требованиям Telegram!</b>"
            else:
                result_msg += f"\n⚠️ <b>Слишком большой, но можно попробовать отправить</b>"

            return True, result_msg, int(size_kb)
        else:
            return False, f"❌ Ошибка создания стикера: {message}", 0

    except Exception as e:
        logger.error(f"🔥 Ошибка в create_sticker_simple: {e}")
        return False, f"❌ Ошибка: {str(e)[:100]}", 0

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
        "📤 <b>Отправь видео для начала!</b>\n\n"
        "<i>Поддерживаются: видео, GIF, документы до 20MB</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📤 Отправить видео")]],
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
        "• Можно добавить текст и эффекты</i>",
        parse_mode=ParseMode.HTML
    )

@router.message(F.video | F.animation | F.document)
async def handle_video(message: Message):
    """Обработка входящего видео"""
    try:
        user_id = message.from_user.id

        # Проверяем что пользователь ожидает видео
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

        # Проверяем что файл не пустой
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
            'frame': 'none'
        }

        await status_msg.edit_text(
            "✅ <b>Видео получено!</b>\n\n"
            "📝 <b>Хочешь добавить текст на видео?</b>\n\n"
            "Отправь текст (до 30 символов) или нажми /skip",
            parse_mode=ParseMode.HTML
        )

        # Удаляем временный файл
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
        if len(text) > 30:
            await message.answer("❌ Слишком длинный текст! Максимум 30 символов.")
            return

        storage.user_data[user_id]['text'] = text
        storage.user_data[user_id]['step'] = 'waiting_effect'

        # Создаем клавиатуру с эффектами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=VIDEO_EFFECTS["none"]["name"], 
                                   callback_data=f"effect_none_{user_id}"),
                InlineKeyboardButton(text=VIDEO_EFFECTS["slowmo"]["name"], 
                                   callback_data=f"effect_slowmo_{user_id}")
            ],
            [
                InlineKeyboardButton(text=VIDEO_EFFECTS["fastmo"]["name"], 
                                   callback_data=f"effect_fastmo_{user_id}"),
                InlineKeyboardButton(text=VIDEO_EFFECTS["vibrant"]["name"], 
                                   callback_data=f"effect_vibrant_{user_id}")
            ],
            [
                InlineKeyboardButton(text=VIDEO_EFFECTS["vintage"]["name"], 
                                   callback_data=f"effect_vintage_{user_id}")
            ]
        ])

        await message.answer(
            f"✅ <b>Текст сохранен:</b> {text}\n\n"
            f"🎬 <b>Теперь выбери видео эффект:</b>",
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
        storage.user_data[user_id]['step'] = 'waiting_effect'

        # Создаем клавиатуру с эффектами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=VIDEO_EFFECTS["none"]["name"], 
                                   callback_data=f"effect_none_{user_id}"),
                InlineKeyboardButton(text=VIDEO_EFFECTS["slowmo"]["name"], 
                                   callback_data=f"effect_slowmo_{user_id}")
            ],
            [
                InlineKeyboardButton(text=VIDEO_EFFECTS["fastmo"]["name"], 
                                   callback_data=f"effect_fastmo_{user_id}"),
                InlineKeyboardButton(text=VIDEO_EFFECTS["vibrant"]["name"], 
                                   callback_data=f"effect_vibrant_{user_id}")
            ],
            [
                InlineKeyboardButton(text=VIDEO_EFFECTS["vintage"]["name"], 
                                   callback_data=f"effect_vintage_{user_id}")
            ]
        ])

        await message.answer(
            "⏭️ <b>Пропускаем текст</b>\n\n"
            "🎬 <b>Выбери видео эффект:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в skip_text: {e}")
        await message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("effect_"))
async def handle_effect(callback: CallbackQuery):
    """Обработка выбора эффекта"""
    try:
        await callback.answer()

        parts = callback.data.split("_")
        if len(parts) < 3:
            return

        effect = parts[1]
        user_id = int(parts[2])

        if effect not in VIDEO_EFFECTS:
            return

        if user_id not in storage.user_data:
            return

        # Сохраняем эффект
        storage.user_data[user_id]['effect'] = effect
        storage.user_data[user_id]['step'] = 'waiting_frame'

        effect_name = VIDEO_EFFECTS[effect]["name"]

        # Создаем клавиатуру с рамками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=FRAME_EFFECTS["none"]["name"], 
                                   callback_data=f"frame_none_{user_id}"),
                InlineKeyboardButton(text=FRAME_EFFECTS["fire"]["name"], 
                                   callback_data=f"frame_fire_{user_id}")
            ],
            [
                InlineKeyboardButton(text=FRAME_EFFECTS["neon"]["name"], 
                                   callback_data=f"frame_neon_{user_id}"),
                InlineKeyboardButton(text=FRAME_EFFECTS["rainbow"]["name"], 
                                   callback_data=f"frame_rainbow_{user_id}")
            ]
        ])

        await callback.message.edit_text(
            f"✅ <b>Эффект выбран:</b> {effect_name}\n\n"
            f"🖼️ <b>Теперь выбери рамку:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в handle_effect: {e}")
        await callback.message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("frame_"))
async def handle_frame(callback: CallbackQuery):
    """Обработка выбора рамки и создание стикера"""
    try:
        await callback.answer()

        parts = callback.data.split("_")
        if len(parts) < 3:
            return

        frame = parts[1]
        user_id = int(parts[2])

        if frame not in FRAME_EFFECTS:
            return

        if user_id not in storage.user_data:
            return

        # Получаем данные
        file_id = storage.user_data[user_id]['file_id']
        effect = storage.user_data[user_id]['effect']
        text = storage.user_data[user_id].get('text', '')

        # Получаем файл
        input_path = storage.get(file_id)
        if input_path is None or not input_path.exists():
            await callback.message.answer("❌ Файл не найден. Отправь видео заново.")
            return

        effect_name = VIDEO_EFFECTS[effect]["name"]
        frame_name = FRAME_EFFECTS[frame]["name"]

        await bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VIDEO)

        processing_msg = await callback.message.answer(
            f"🎬 <b>Создаю стикер...</b>\n\n"
            f"⚙️ <i>Обработка может занять до 30 секунд</i>",
            parse_mode=ParseMode.HTML
        )

        # Создаем временный файл для результата
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            output_path = Path(tmp.name)

        # Создаем стикер
        success, result_text, size_kb = await create_sticker_simple(
            input_path, output_path, effect, frame, text
        )

        if success:
            await processing_msg.edit_text("📤 <i>Отправляю файл...</i>", parse_mode=ParseMode.HTML)

            # Читаем файл
            try:
                with open(output_path, 'rb') as f:
                    webm_data = f.read()

                filename = f"sticker_{STICKER_DURATION}s.webm"

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

    except Exception as e:
        logger.error(f"❌ Ошибка в handle_frame: {e}")
        await callback.message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

# ===== ЗАПУСК БОТА =====
async def main():
    """Основная функция запуска"""
    print("\n" + "=" * 60)
    print("🚀 ЗАПУСК VIDEO STICKER BOT")
    print("=" * 60)
    print("⚙️ ОСНОВНЫЕ ПАРАМЕТРЫ:")
    print(f"   • Длительность: {STICKER_DURATION} секунды")
    print("   • Разрешение: 512x512 пикселей")
    print("   • Формат: WebM с VP9")
    print("   • Размер: ≤256 КБ")
    print("=" * 60)

    # Очищаем старые файлы
    cleanup()

    # Запускаем keep-alive в отдельном потоке
    try:
        keep_alive_thread = threading.Thread(target=run_keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("✅ Keep-alive запущен")
    except Exception as e:
        logger.error(f"⚠️ Ошибка keep-alive: {e}")

    # Получаем информацию о боте
    me = await bot.get_me()
    logger.info(f"🤖 Бот: @{me.username}")
    logger.info("✅ Готов к работе!")

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
