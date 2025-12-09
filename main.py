# main.py - БОТ С ТЕКСТОМ И TIKTOK ЭФФЕКТАМИ
import os
import sys
import asyncio
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Dict, Optional
import time
from datetime import datetime
import uuid
import textwrap

print("=" * 60)
print("🤖 Video Sticker Bot с текстом и эффектами")
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
        self.user_data = {}  # user_id -> {text: str, effect: str, file_id: str}
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
        "description": "Обычное видео без эффектов"
    },
    "slowmo": {
        "name": "🐌 Супер-замедление",
        "filter": "setpts=2.5*PTS",
        "description": "Видео в 2.5 раза медленнее"
    },
    "fastmo": {
        "name": "⚡ Супер-ускорение", 
        "filter": "setpts=0.4*PTS",
        "description": "Видео в 2.5 раза быстрее"
    },
    "vhs": {
        "name": "📼 VHS Эффект",
        "filter": "noise=alls=30:allf=t+u,curves=preset=vintage,eq=saturation=0.8",
        "description": "Старый видеомагнитофон"
    },
    "glitch": {
        "name": "🌀 Глитч-эффект",
        "filter": "noise=alls=50:allf=t+u,colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131,hue=H=2*PI*t",
        "description": "Цифровой глитч с цветами"
    },
    "neon": {
        "name": "🌃 Неоновый",
        "filter": "curves=preset=color_negative,eq=brightness=0.1:saturation=2,convolution='0 -1 0 -1 5 -1 0 -1 0:0 -1 0 -1 5 -1 0 -1 0:0 -1 0 -1 5 -1 0 -1 0:0 -1 0 -1 5 -1 0 -1 0'",
        "description": "Неоновые цвета и свечение"
    },
    "pixel": {
        "name": "🎮 Пиксель-арт",
        "filter": "scale=128:128:flags=neighbor,scale=512:512:flags=neighbor",
        "description": "Ретро пиксельная графика"
    },
    "mirror": {
        "name": "🪞 Зеркальный",
        "filter": "crop=iw/2:ih:0:0,split[left][tmp];[tmp]hflip[right];[left][right]hstack",
        "description": "Симметричное отражение"
    },
    "vibrant": {
        "name": "🌈 Яркие цвета",
        "filter": "eq=saturation=1.8:brightness=0.1:contrast=1.3",
        "description": "Усиленные насыщенные цвета"
    },
    "shake": {
        "name": "📳 Дрожание",
        "filter": "crop=iw-10:ih-10:5+5*sin(2*PI*t):5+5*cos(2*PI*t)",
        "description": "Эффект дрожащей камеры"
    },
    "zoom": {
        "name": "🔍 Зум-эффект",
        "filter": "zoompan=z='min(zoom+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps=30",
        "description": "Плавное увеличение"
    },
    "wave": {
        "name": "🌊 Волновой",
        "filter": "waveform=m=0:desc=0",
        "description": "Волнообразные искажения"
    }
}

# ===== ФУНКЦИЯ ДЛЯ ДОБАВЛЕНИЯ ТЕКСТА =====
def create_text_filter(text: str, effect: str) -> str:
    """Создает фильтр для добавления текста с эффектами"""
    if not text:
        return ""

    # Очищаем текст от спецсимволов
    safe_text = text.replace(':', '\\:').replace("'", "\\'").replace('"', '\\"')

    # Разбиваем длинный текст на строки
    lines = textwrap.wrap(safe_text, width=20)

    # Базовые стили текста
    fontfile = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    # Разные стили для разных эффектов
    if effect == "neon":
        # Неоновый текст с тенью
        text_filter = f"drawtext=fontfile={fontfile}:text='{safe_text}':" \
                     f"fontcolor=cyan@0.9:fontsize=48:" \
                     f"box=1:boxcolor=black@0.4:boxborderw=10:" \
                     f"x=(w-text_w)/2:y=h-text_h-50:" \
                     f"shadowcolor=magenta@0.7:shadowx=4:shadowy=4"
    elif effect == "vhs":
        # Текст в стиле VHS
        text_filter = f"drawtext=fontfile={fontfile}:text='{safe_text}':" \
                     f"fontcolor=white:fontsize=44:" \
                     f"x=(w-text_w)/2:y=h-text_h-40:" \
                     f"enable='between(t,0,3)':" \
                     f"alpha='if(lt(t,2.5),1,if(lt(t,2.8),0.5,0))'"
    elif effect == "glitch":
        # Глитч-текст
        text_filter = f"drawtext=fontfile={fontfile}:text='{safe_text}':" \
                     f"fontcolor=0xFF00FF@0.9:fontsize=50:" \
                     f"x='(w-text_w)/2+5*sin(10*PI*t)':" \
                     f"y='h-text_h-30+3*cos(15*PI*t)':" \
                     f"alpha='0.8+0.2*sin(20*PI*t)'"
    else:
        # Стандартный текст
        text_filter = f"drawtext=fontfile={fontfile}:text='{safe_text}':" \
                     f"fontcolor=white:fontsize=50:" \
                     f"borderw=3:bordercolor=black@0.7:" \
                     f"x=(w-text_w)/2:y=h-text_h-30"

    return text_filter

# ===== ОСНОВНАЯ ФУНКЦИЯ =====
async def create_sticker_with_text_and_effect(
    input_path: Path, 
    output_path: Path, 
    effect: str = "none",
    text: str = ""
) -> Tuple[bool, str, int]:
    """
    Создает WebM стикер с текстом и эффектом
    """
    try:
        effect_name = TIKTOK_EFFECTS[effect]["name"]
        print(f"🎬 Создаю стикер: {effect_name}")
        if text:
            print(f"   📝 Текст: {text[:30]}...")

        # Получаем информацию о видео
        info = await get_video_info(input_path)
        duration = min(info['duration'], 2.8)

        print(f"   📊 Исходное: {info['width']}x{info['height']}, {duration:.1f}с, {info['fps']:.1f}fps")

        # Базовый фильтр для Telegram
        base_filter = "scale=512:512:force_original_aspect_ratio=decrease," \
                     "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0," \
                     "fps=30,format=yuva420p"

        # Добавляем TikTok эффект
        effect_filter = TIKTOK_EFFECTS[effect]["filter"]

        # Добавляем текст
        text_filter = create_text_filter(text, effect)

        # Комбинируем все фильтры
        filters = [base_filter]
        if effect_filter:
            filters.append(effect_filter)
        if text_filter:
            filters.append(text_filter)

        video_filter = ",".join(filter(None, filters))

        # КОМАНДА FFMPEG С VP9
        cmd = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-t", str(duration),
            "-an",  # Без звука
            "-vf", video_filter,
            "-c:v", "libvpx-vp9",  # VP9 кодек
            "-b:v", "180k",
            "-crf", "30",
            "-deadline", "good",
            "-row-mt", "1",
            "-tile-columns", "2",
            "-frame-parallel", "1",
            "-g", str(int(duration * 30)),
            "-lag-in-frames", "0",
            "-auto-alt-ref", "0",
            "-pix_fmt", "yuva420p",
            "-f", "webm",
            str(output_path)
        ]

        print(f"   🛠️ Запускаю конвертацию с эффектом...")

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

            status = "✅" if size_kb <= 256 else "⚠️"

            message = f"{status} <b>Video Sticker создан!</b>\n\n"
            message += f"🎭 <b>Эффект:</b> {effect_name}\n"
            if text:
                message += f"📝 <b>Текст:</b> {text[:50]}{'...' if len(text) > 50 else ''}\n"
            message += f"📦 <b>Размер:</b> {size_kb:.1f}KB / 256KB\n"
            message += f"📏 <b>Разрешение:</b> {output_info['width']}x{output_info['height']}\n"
            message += f"🎬 <b>FPS:</b> {output_info['fps']:.1f}\n"
            message += f"⏱ <b>Длительность:</b> {output_info['duration']:.1f}с\n"
            message += f"🔧 <b>Кодек:</b> VP9\n"

            if size_kb <= 256:
                message += "\n🎉 <b>Готов к добавлению в Telegram!</b>"
                message += f"\n<i>{TIKTOK_EFFECTS[effect]['description']}</i>"
            else:
                message += "\n⚠️ <b>Слишком большой для Telegram</b>"

            return True, message, int(size_kb)

        error = stderr.decode('utf-8', errors='ignore')
        print(f"   ❌ Ошибка: {error[:200]}")

        # Пробуем упрощенный метод
        return await create_simple_sticker(input_path, output_path, effect, text)

    except Exception as e:
        print(f"   🔥 Исключение: {e}")
        return False, f"❌ Ошибка: {str(e)[:100]}", 0

async def create_simple_sticker(input_path: Path, output_path: Path, effect: str, text: str) -> Tuple[bool, str, int]:
    """Упрощенный метод создания стикера"""
    try:
        duration = 2.5

        # Только базовые фильтры
        base_filter = "scale=512:512,fps=30,format=yuva420p"
        text_filter = create_text_filter(text, "none") if text else ""

        video_filter = base_filter
        if text_filter:
            video_filter = f"{base_filter},{text_filter}"

        cmd = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-t", str(duration),
            "-an",
            "-vf", video_filter,
            "-c:v", "libvpx-vp9",
            "-b:v", "150k",
            "-crf", "32",
            "-deadline", "good",
            "-f", "webm",
            str(output_path)
        ]

        process = await asyncio.create_subprocess_exec(*cmd)
        await process.wait()

        if output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            return True, f"✅ Стикер создан (упрощенный)\nРазмер: {size_kb:.1f}KB", int(size_kb)

        return False, "❌ Не удалось создать стикер", 0
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}", 0

async def optimize_webm(file_path: Path) -> bool:
    """Оптимизация WebM"""
    try:
        temp_path = file_path.with_suffix('.opt.webm')

        cmd = [
            FFMPEG, "-y",
            "-i", str(file_path),
            "-t", "2.5",
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
        "🎬 <b>Video Sticker Bot с TikTok-эффектами!</b>\n\n"
        "<b>✨ НОВИНКА:</b> Добавление текста на видео!\n\n"
        "<b>🎭 12 крутых эффектов:</b>\n"
        "• 🐌 Супер-замедление\n"
        "• ⚡ Супер-ускорение\n"
        "• 📼 VHS стиль\n"
        "• 🌀 Глитч-эффект\n"
        "• 🌃 Неоновый\n"
        "• 🎮 Пиксель-арт\n"
        "• 🪞 Зеркальный\n"
        "• 🌈 Яркие цвета\n"
        "• 📳 Дрожание\n"
        "• 🔍 Зум-эффект\n"
        "• 🌊 Волновой\n"
        "• 🎨 Без эффекта\n\n"
        "<b>📝 Можно добавить текст на видео!</b>\n\n"
        "<b>📤 Отправь видео и выбери эффект:</b>",
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
        "📤 <b>Отправь мне видео или GIF</b>\n\n"
        "<i>• До 10MB\n"
        "• До 5 секунд\n"
        "• Любой формат\n\n"
        "После загрузки сможешь добавить текст и выбрать эффект!</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "🎭 ЭФФЕКТЫ")
async def show_effects(message: Message):
    effects_text = ""
    for i, (key, effect) in enumerate(TIKTOK_EFFECTS.items(), 1):
        effects_text += f"{i}. <b>{effect['name']}</b>\n   <i>{effect['description']}</i>\n\n"

    await message.answer(
        f"🎭 <b>Доступные TikTok-эффекты:</b>\n\n{effects_text}"
        f"<i>Отправь видео → Выбери эффект → Получи крутой стикер!</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "📝 ДОБАВИТЬ ТЕКСТ")
async def add_text_prompt(message: Message):
    user_id = message.from_user.id
    if user_id in storage.user_data and 'file_id' in storage.user_data[user_id]:
        storage.user_data[user_id]['step'] = 'waiting_text'
        await message.answer(
            "📝 <b>Введи текст для видео:</b>\n\n"
            "<i>• До 50 символов\n"
            "• Текст появится в нижней части видео\n"
            "• Можно использовать эмодзи 😊\n\n"
            "Или отправь /skip чтобы пропустить</i>",
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
            "📝 <b>Хочешь добавить текст на видео?</b>\n\n"
            "Отправь текст (до 50 символов) или /skip чтобы пропустить",
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

        if len(text) > 50:
            await message.answer("❌ Слишком длинный текст! Максимум 50 символов.")
            return

        # Сохраняем текст
        storage.user_data[user_id]['text'] = text
        storage.user_data[user_id]['step'] = 'waiting_effect'

        await message.answer(
            f"✅ <b>Текст сохранен:</b> {text}\n\n"
            f"🎭 <b>Теперь выбери эффект:</b>",
            parse_mode=ParseMode.HTML
        )

        # Показываем кнопки с эффектами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["slowmo"]["name"], 
                                   callback_data=f"effect_slowmo_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["fastmo"]["name"], 
                                   callback_data=f"effect_fastmo_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["vhs"]["name"], 
                                   callback_data=f"effect_vhs_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["glitch"]["name"], 
                                   callback_data=f"effect_glitch_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["neon"]["name"], 
                                   callback_data=f"effect_neon_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["pixel"]["name"], 
                                   callback_data=f"effect_pixel_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["mirror"]["name"], 
                                   callback_data=f"effect_mirror_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["vibrant"]["name"], 
                                   callback_data=f"effect_vibrant_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["shake"]["name"], 
                                   callback_data=f"effect_shake_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["zoom"]["name"], 
                                   callback_data=f"effect_zoom_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["wave"]["name"], 
                                   callback_data=f"effect_wave_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["none"]["name"], 
                                   callback_data=f"effect_none_{user_id}")
            ]
        ])

        await message.answer("Нажми на эффект для применения:", reply_markup=keyboard)

    except Exception as e:
        await message.answer(f"❌ <b>Ошибка:</b> {str(e)[:200]}", parse_mode=ParseMode.HTML)

@dp.message(Command("skip"))
async def skip_text(message: Message):
    """Пропуск добавления текста"""
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

        # Показываем те же кнопки с эффектами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["slowmo"]["name"], 
                                   callback_data=f"effect_slowmo_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["fastmo"]["name"], 
                                   callback_data=f"effect_fastmo_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["vhs"]["name"], 
                                   callback_data=f"effect_vhs_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["glitch"]["name"], 
                                   callback_data=f"effect_glitch_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["neon"]["name"], 
                                   callback_data=f"effect_neon_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["pixel"]["name"], 
                                   callback_data=f"effect_pixel_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["mirror"]["name"], 
                                   callback_data=f"effect_mirror_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["vibrant"]["name"], 
                                   callback_data=f"effect_vibrant_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["shake"]["name"], 
                                   callback_data=f"effect_shake_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["zoom"]["name"], 
                                   callback_data=f"effect_zoom_{user_id}")
            ],
            [
                InlineKeyboardButton(text=TIKTOK_EFFECTS["wave"]["name"], 
                                   callback_data=f"effect_wave_{user_id}"),
                InlineKeyboardButton(text=TIKTOK_EFFECTS["none"]["name"], 
                                   callback_data=f"effect_none_{user_id}")
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

        # Получаем данные пользователя
        file_id = storage.user_data[user_id]['file_id']
        text = storage.user_data[user_id].get('text', '')

        # Получаем сохраненный файл
        try:
            input_path = storage.get(file_id)
        except:
            await callback.message.answer("❌ Файл не найден. Отправь видео снова.")
            return

        processing_msg = await callback.message.answer(
            f"🎬 <i>Создаю стикер с эффектом...</i>\n"
            f"<b>Эффект:</b> {effect_name}\n"
            f"{f'<b>Текст:</b> {text}' if text else ''}",
            parse_mode=ParseMode.HTML
        )

        # Создаем WebM
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_out:
            output_path = Path(tmp_out.name)

            success, result, size_kb = await create_sticker_with_text_and_effect(
                input_path, output_path, effect, text
            )

            if success:
                # Отправляем файл
                with open(output_path, 'rb') as f:
                    webm_data = f.read()

                filename = f"sticker_{effect}_{int(time.time())}.webm"

                await processing_msg.edit_text("📤 <i>Отправляю результат...</i>", parse_mode=ParseMode.HTML)

                await bot.send_document(
                    callback.message.chat.id,
                    document=BufferedInputFile(webm_data, filename=filename),
                    caption=result,
                    parse_mode=ParseMode.HTML
                )

                # Инструкция
                if size_kb <= 256:
                    await callback.message.answer(
                        "💡 <b>Как добавить в Telegram:</b>\n\n"
                        "1. Сохрани этот файл\n"
                        "2. Напиши @Stickers\n"
                        "3. /newpack → название → эмодзи\n"
                        "4. Загрузи файл\n\n"
                        "<i>✅ Стикер готов к использованию!</i>",
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
        print(f"❌ Ошибка эффекта: {e}")

# ===== ЗАПУСК =====
async def main():
    print("\n" + "=" * 60)
    print("🚀 БОТ ЗАПУЩЕН С TIKTOK-ЭФФЕКТАМИ И ТЕКСТОМ!")
    print("=" * 60)
    print("✨ 12 КРУТЫХ ЭФФЕКТОВ:")
    for key, effect in TIKTOK_EFFECTS.items():
        print(f"   • {effect['name']} - {effect['description']}")
    print("=" * 60)
    print("📝 НОВАЯ ФУНКЦИЯ:")
    print("   • Добавление текста на видео")
    print("   • Автоматическое форматирование")
    print("   • Стили под каждый эффект")
    print("=" * 60)
    print("🎯 ПАРАМЕТРЫ TELEGRAM:")
    print("   • WebM с VP9 кодеком")
    print("   • 30 кадров/сек")
    print("   • 512x512 пикселей")
    print("   • ≤256 КБ")
    print("   • ≤3 секунды")
    print("=" * 60)

    me = await bot.get_me()
    print(f"🤖 Бот: @{me.username}")
    print("✅ Готов к работе! Отправь видео и создай крутой стикер!")
    print("=" * 60)

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
        if Path("./temp_files").exists():
            shutil.rmtree("./temp_files")
