# main.py - Исправленная версия с сохранением файлов
import os
import sys
import asyncio
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict
import uuid

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, FSInputFile,
    ReplyKeyboardMarkup, KeyboardButton,
    BufferedInputFile, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatAction

# ===== FFMPEG НАСТРОЙКА =====
def setup_ffmpeg():
    """Настройка ffmpeg-static"""
    import os
    import stat
    
    ffmpeg_static = "./ffmpeg-static"
    
    if not os.path.exists(ffmpeg_static):
        print("❌ ffmpeg-static не найден!")
        return False
    
    if not os.access(ffmpeg_static, os.X_OK):
        os.chmod(ffmpeg_static, stat.S_IRWXU)
    
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
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== ЭФФЕКТЫ =====
EFFECTS = {
    "none": "🎨 Без эффекта",
    "vibrant": "🌈 Яркие цвета",
    "vintage": "📻 Винтаж",
    "blackwhite": "⚫ Черно-белый", 
    "pixel": "👾 Пиксель-арт",
    "glitch": "🌀 Глитч",
    "slowmo": "🐌 Замедление",
    "fast": "⚡ Ускорение",
    "reverse": "↪️ Обратное",
    "mirror": "🪞 Зеркало",
    "shake": "📳 Дрожание",
    "zoom": "🔍 Увеличение",
    "rotate": "🔄 Вращение",
    "neon": "💡 Неоновый",
    "vhs": "📼 VHS эффект",
    "wavy": "🌊 Волны",
    "blur": "😶‍🌫️ Размытие",
    "sharpen": "🔪 Резкость"
}

# Глобальное хранилище для временных файлов (в памяти)
temp_storage = {}

# ===== ФУНКЦИИ ДЛЯ FFMPEG =====
async def run_ffmpeg(cmd: list) -> tuple[int, str, str]:
    """Асинхронный запуск ffmpeg"""
    def _run():
        if cmd[0] == "ffmpeg":
            cmd[0] = "./ffmpeg-static"
        
        print(f"🚀 Запускаю ffmpeg...")
        
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=120
        )
        return process.returncode, process.stdout, process.stderr
    
    return await asyncio.to_thread(_run)

def get_effect_filter(effect: str) -> str:
    """Получить фильтр для эффекта"""
    filters = []
    
    if effect == "vibrant":
        filters.append("eq=contrast=1.3:saturation=1.5:brightness=0.05")
    elif effect == "vintage":
        filters.append("curves=r='0/0.1 0.5/0.4 1/0.9':g='0/0 0.5/0.3 1/0.8'")
        filters.append("hue=s=0.8")
    elif effect == "blackwhite":
        filters.append("hue=s=0")
        filters.append("eq=contrast=1.2")
    elif effect == "pixel":
        filters.append("scale=128:128:flags=neighbor")
        filters.append("scale=512:512:flags=neighbor")
    elif effect == "glitch":
        filters.append("noise=alls=20:allf=t+u, hue=s=0.5")
    elif effect == "slowmo":
        filters.append("setpts=2.0*PTS")
    elif effect == "fast":
        filters.append("setpts=0.5*PTS")
    elif effect == "reverse":
        filters.append("reverse")
    elif effect == "mirror":
        filters.append("crop=iw/2:ih:0:0,split[left][tmp];[tmp]hflip[right];[left][right]hstack")
    elif effect == "shake":
        filters.append("crop=iw-10:ih-10:5:5,scale=512:512")
    elif effect == "zoom":
        filters.append("zoompan=z='min(zoom+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=512x512")
    elif effect == "rotate":
        filters.append("rotate=PI/6:ow=512:oh=512")
    elif effect == "neon":
        filters.append("edgedetect=low=0.1:high=0.4")
        filters.append("hue=s=2")
    elif effect == "vhs":
        filters.append("noise=alls=30:allf=t+u, curves=r='0/0 0.1/0.2 0.7/0.6 1/1':g='0/0 0.2/0.3 0.8/0.7 1/1':b='0/0 0.3/0.4 0.9/0.8 1/1'")
    elif effect == "wavy":
        filters.append("waveform=display=1")
    elif effect == "blur":
        filters.append("boxblur=5:1")
    elif effect == "sharpen":
        filters.append("unsharp=5:5:1.0")
    
    return ','.join(filters) if filters else "null"

async def create_animated_sticker(input_path: Path, output_path: Path, effect: str = "none") -> tuple[bool, str]:
    """Создает анимированный стикер (WebP) для Telegram"""
    try:
        # Создаем временную папку для промежуточных файлов
        temp_dir = output_path.parent / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        # Базовые фильтры
        base_filters = [
            "scale=512:512:force_original_aspect_ratio=decrease",
            "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=white@0.0",
            "fps=15"  # Оптимальный FPS для анимации
        ]
        
        # Добавляем эффект
        if effect != "none":
            effect_filter = get_effect_filter(effect)
            if effect_filter and effect_filter != "null":
                base_filters.insert(0, effect_filter)
        
        filters = ','.join(base_filters)
        
        # Для обратного эффекта нужна особая обработка
        if effect == "reverse":
            filters += ",reverse"
        
        # Простая команда для создания WebP (не используем сложную палитру)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-t", "3",  # Макс 3 секунды
            "-vf", filters,
            "-loop", "0",
            "-lossless", "0",
            "-q:v", "75",
            "-compression_level", "6",
            "-preset", "default",
            "-an",
            str(output_path)
        ]
        
        code, out, err = await run_ffmpeg(cmd)
        
        if code != 0:
            print(f"FFmpeg ошибка: {err[:500]}")
            return False, f"Ошибка создания стикера: {err[:100]}"
        
        if not output_path.exists():
            return False, "Файл не создан"
        
        # Проверяем и сжимаем если нужно
        size_kb = output_path.stat().st_size / 1024
        if size_kb > 256:
            compressed = await compress_sticker(output_path, output_path)
            if compressed[0]:
                size_kb = output_path.stat().st_size / 1024
            else:
                return compressed
        
        # Очищаем временные файлы
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        
        return True, f"✅ Стикер готов!\nРазмер: {size_kb:.1f}KB\nЭффект: {EFFECTS[effect]}"
        
    except Exception as e:
        print(f"Ошибка в create_animated_sticker: {e}")
        return False, f"Ошибка: {str(e)[:100]}"

async def compress_sticker(input_path: Path, output_path: Path) -> tuple[bool, str]:
    """Сжимает стикер до <256KB"""
    try:
        temp_path = output_path.with_suffix('.compressed.webp')
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-loop", "0",
            "-lossless", "0",
            "-q:v", "90",  # Более высокое качество
            "-compression_level", "6",
            str(temp_path)
        ]
        
        code, _, err = await run_ffmpeg(cmd)
        
        if code == 0 and temp_path.exists():
            size_kb = temp_path.stat().st_size / 1024
            if size_kb <= 256:
                if input_path.exists():
                    input_path.unlink()
                temp_path.rename(output_path)
                return True, f"✅ Стикер сжат до {size_kb:.1f}KB"
            else:
                temp_path.unlink()
                return False, f"❌ Не удалось сжать до 256KB (осталось {size_kb:.1f}KB)"
        
        return False, "Не удалось сжать стикер"
    except Exception as e:
        return False, f"Ошибка сжатия: {str(e)}"

def get_effects_keyboard():
    """Клавиатура для выбора эффектов"""
    effects = list(EFFECTS.items())
    keyboard = []
    
    # Группируем по 2 в ряд для лучшего отображения
    for i in range(0, len(effects), 2):
        row = effects[i:i+2]
        keyboard.append([
            InlineKeyboardButton(text=name, callback_data=f"effect_{key}")
            for key, name in row
        ])
    
    # Добавляем кнопку "Без эффекта" отдельно
    keyboard.append([
        InlineKeyboardButton(text="🎨 Без эффекта", callback_data="effect_none"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def save_user_file(user_id: int, file_path: Path) -> str:
    """Сохраняет файл пользователя и возвращает уникальный ID"""
    file_id = str(uuid.uuid4())
    
    # Создаем папку для пользователя если нет
    user_dir = Path(f"./temp_files/{user_id}")
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем файл
    saved_path = user_dir / f"{file_id}{file_path.suffix}"
    shutil.copy2(file_path, saved_path)
    
    # Сохраняем в глобальное хранилище
    temp_storage[user_id] = {
        'file_id': file_id,
        'path': str(saved_path),
        'timestamp': asyncio.get_event_loop().time()
    }
    
    return file_id

async def get_user_file(user_id: int) -> Optional[Path]:
    """Получает сохраненный файл пользователя"""
    if user_id not in temp_storage:
        return None
    
    data = temp_storage[user_id]
    file_path = Path(data['path'])
    
    if file_path.exists():
        # Проверяем не устарел ли файл (10 минут)
        current_time = asyncio.get_event_loop().time()
        if current_time - data['timestamp'] < 600:  # 10 минут
            return file_path
        else:
            # Удаляем устаревший файл
            try:
                file_path.unlink()
            except:
                pass
            del temp_storage[user_id]
    
    return None

async def cleanup_user_file(user_id: int):
    """Очищает файлы пользователя"""
    if user_id in temp_storage:
        data = temp_storage[user_id]
        file_path = Path(data['path'])
        try:
            if file_path.exists():
                file_path.unlink()
        except:
            pass
        
        # Удаляем папку пользователя если пуста
        user_dir = file_path.parent
        try:
            if user_dir.exists() and not any(user_dir.iterdir()):
                user_dir.rmdir()
        except:
            pass
        
        del temp_storage[user_id]

# ===== ОБРАБОТЧИКИ =====
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🎬 *Animated Sticker Bot*\n\n"
        "Я создаю анимированные стикеры из видео и GIF!\n\n"
        "Как использовать:\n"
        "1. 📤 Отправь мне видео/GIF\n"
        "2. ✨ Выбери эффект\n"
        "3. 📥 Получи WebP стикер\n"
        "4. 📚 Добавь в стикерпак\n\n"
        "Готов создать крутой стикер? Отправь видео! 🚀",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📤 Отправить видео")],
                [KeyboardButton(text="✨ Список эффектов"), KeyboardButton(text="ℹ️ Помощь")]
            ],
            resize_keyboard=True
        )
    )

@dp.message(Command("effects"))
@dp.message(F.text == "✨ Список эффектов")
async def show_all_effects(message: Message):
    effects_text = "✨ *Доступные эффекты:*\n\n"
    for key, name in EFFECTS.items():
        effects_text += f"{name}\n"
    
    effects_text += "\nОтправь видео и выбери эффект!"
    await message.answer(effects_text, parse_mode="Markdown")

@dp.message(F.text == "ℹ️ Помощь")
async def show_help(message: Message):
    await message.answer(
        "📋 *Как использовать бота:*\n\n"
        "1. *Отправь видео/GIF* (до 50MB)\n"
        "2. *Выбери эффект* из списка\n"
        "3. *Получи WebP файл* анимированного стикера\n"
        "4. *Сохрани файл* и добавь в стикерпак\n\n"
        "📌 *Требования Telegram:*\n"
        "• Формат: WebP (анимированный)\n"
        "• Размер: 512×512 пикселей\n"
        "• Вес: до 256KB\n"
        "• Длительность: до 3 секунд\n\n"
        "🎯 *Как добавить в стикерпак:*\n"
        "1. Сохрани полученный файл\n"
        "2. Напиши @Stickers\n"
        "3. Создай новый стикерпак\n"
        "4. Загрузи как анимированный стикер\n\n"
        "Готов творить? Отправь видео! 🎥",
        parse_mode="Markdown"
    )

@dp.message(F.text == "📤 Отправить видео")
async def prompt_upload(message: Message):
    await message.answer("📹 Отправь мне видео (MP4, MOV, AVI) или GIF")

@dp.message(F.video | F.animation | (F.document & F.document.mime_type.startswith("video/")))
async def handle_video(message: Message):
    await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
    status_msg = await message.answer("⏳ Скачиваю файл...")
    
    try:
        # Скачиваем файл во временную папку
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            if message.video:
                file_id = message.video.file_id
                input_path = tmpdir / "video.mp4"
            elif message.animation:
                file_id = message.animation.file_id
                input_path = tmpdir / "animation.gif"
            elif message.document:
                file_id = message.document.file_id
                # Определяем расширение
                mime = message.document.mime_type
                if "gif" in mime:
                    ext = ".gif"
                elif "webm" in mime:
                    ext = ".webm"
                else:
                    ext = ".mp4"
                input_path = tmpdir / f"video{ext}"
            else:
                await message.answer("❌ Неподдерживаемый формат файла")
                return
            
            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, input_path)
            
            # Проверяем размер
            file_size = input_path.stat().st_size
            if file_size > 50 * 1024 * 1024:
                await message.answer("❌ Файл слишком большой (максимум 50MB)")
                return
            
            if file_size < 1024:
                await message.answer("❌ Файл слишком маленький")
                return
            
            # Сохраняем файл
            await save_user_file(message.from_user.id, input_path)
            
            await status_msg.delete()
            
            # Показываем клавиатуру с эффектами
            keyboard = get_effects_keyboard()
            await message.answer(
                "✨ *Отлично! Теперь выбери эффект:*\n\n"
                "Или нажми '🎨 Без эффекта' для чистого стикера",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при загрузке файла: {str(e)[:200]}")
        print(f"Error in handle_video: {e}")

@dp.callback_query(F.data.startswith("effect_"))
async def handle_effect_selection(callback: CallbackQuery):
    effect_key = callback.data.replace("effect_", "")
    
    if effect_key == "cancel":
        await callback.answer("❌ Отменено")
        await callback.message.delete()
        await cleanup_user_file(callback.from_user.id)
        return
    
    if effect_key not in EFFECTS:
        await callback.answer("❌ Неизвестный эффект")
        return
    
    effect_name = EFFECTS[effect_key]
    await callback.answer(f"Выбран: {effect_name}")
    
    # Получаем сохраненный файл
    input_path = await get_user_file(callback.from_user.id)
    
    if not input_path or not input_path.exists():
        await callback.message.answer("❌ Файл не найден или устарел. Отправь видео снова.")
        return
    
    # Создаем стикер
    processing_msg = await callback.message.answer(f"🎨 Создаю стикер с эффектом: {effect_name}...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_path = tmpdir / f"sticker_{effect_key}.webp"
        
        try:
            success, result_msg = await create_animated_sticker(
                input_path, 
                output_path, 
                effect_key
            )
            
            if success and output_path.exists():
                # Читаем и отправляем файл
                with open(output_path, 'rb') as f:
                    sticker_data = f.read()
                
                input_file = BufferedInputFile(sticker_data, filename=f"sticker_{effect_key}.webp")
                
                await bot.send_document(
                    chat_id=callback.message.chat.id,
                    document=input_file,
                    caption=result_msg
                )
                
                # Инструкция
                instructions = (
                    "\n\n📌 *Как добавить в стикерпак:*\n"
                    "1. Сохрани этот файл\n"
                    "2. Напиши @Stickers\n"
                    "3. Выбери 'Новый стикерпак'\n"
                    "4. Загрузи этот файл\n"
                    "5. Выбери эмодзи для стикера\n\n"
                    "Готово! 🎉"
                )
                await callback.message.answer(instructions, parse_mode="Markdown")
                
            else:
                await callback.message.answer(f"❌ {result_msg}")
            
            await processing_msg.delete()
            
        except Exception as e:
            await callback.message.answer(f"❌ Ошибка при создании стикера: {str(e)[:200]}")
            print(f"Error in handle_effect_selection: {e}")
    
    # Очищаем файлы пользователя
    await cleanup_user_file(callback.from_user.id)

@dp.message()
async def handle_other(message: Message):
    await message.answer(
        "Отправь мне видео или GIF чтобы создать анимированный стикер!\n\n"
        "Используй кнопки меню:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📤 Отправить видео")],
                [KeyboardButton(text="✨ Список эффектов"), KeyboardButton(text="ℹ️ Помощь")]
            ],
            resize_keyboard=True
        )
    )

# ===== ОЧИСТКА ВРЕМЕННЫХ ФАЙЛОВ ПРИ СТАРТЕ =====
def cleanup_old_files():
    """Очистка старых временных файлов при запуске"""
    temp_dir = Path("./temp_files")
    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
            print("🧹 Очищены старые временные файлы")
        except:
            pass

# ===== ЗАПУСК =====
async def main():
    print("=" * 50)
    print("🤖 Telegram Animated Sticker Bot")
    print("=" * 50)
    
    # Очищаем старые файлы
    cleanup_old_files()
    
    try:
        me = await bot.get_me()
        print(f"✅ Бот: @{me.username}")
        print(f"✅ Имя: {me.full_name}")
        print(f"✨ Эффектов: {len(EFFECTS)}")
        print(f"👤 ID: {me.id}")
    except Exception as e:
        print(f"⚠️ Не удалось получить информацию о боте: {e}")
    
    print("🚀 Запускаю бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
        # Очищаем временные файлы при выходе
        temp_dir = Path("./temp_files")
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
