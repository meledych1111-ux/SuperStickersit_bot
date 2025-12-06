import os
import asyncio
import logging
import subprocess
import tempfile
from io import BytesIO
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode
import aiohttp
from PIL import Image

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение токена из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

# Очередь обработки
processing_users = set()

# Эффекты для стикеров
EFFECTS = {
    "emoji": "🎭",
    "list": [
        {"id": "original", "name": "Оригинал", "emoji": "⚪"},
        {"id": "bw", "name": "Черно-белый", "emoji": "⚫"},
        {"id": "contrast", "name": "Контраст", "emoji": "🔆"},
        {"id": "bright", "name": "Яркий", "emoji": "✨"},
        {"id": "vintage", "name": "Винтаж", "emoji": "🟤"},
        {"id": "sepia", "name": "Сепия", "emoji": "🟫"},
    ]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = """
🎬 <b>Video Sticker Bot</b>

🤖 Я создаю крутые стикеры из ваших видео!

<b>Как использовать:</b>
1. Отправьте мне видео (до 20MB)
2. Выберите эффект
3. Получите стикер за 10-30 секунд!

<b>Доступные эффекты:</b>
"""
    
    for effect in EFFECTS["list"]:
        welcome_text += f"{effect['emoji']} {effect['name']}\n"
    
    welcome_text += "\n<i>Нажмите /effects для выбора эффекта</i>"
    
    await update.message.reply_html(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
❓ <b>Помощь</b>

<b>Ограничения:</b>
• Видео до 20MB
• Длительность до 30 секунд
• Форматы: MP4, MOV, AVI

<b>Что я умею:</b>
• Создавать квадратные стикеры
• Применять фильтры к видео
• Обрезать до 3 секунд
• Оптимизировать для Telegram

<b>Команды:</b>
/start - Начало работы
/effects - Выбрать эффект
/help - Эта справка
/status - Статус бота
"""
    
    await update.message.reply_html(help_text)

async def effects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать эффекты"""
    keyboard = []
    
    # Создаем кнопки эффектов
    for effect in EFFECTS["list"]:
        keyboard.append([
            InlineKeyboardButton(
                f"{effect['emoji']} {effect['name']}",
                callback_data=f"effect:{effect['id']}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎨 <b>Выберите эффект для стикера:</b>\n\n"
        "После выбора отправьте мне видео!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def effect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора эффекта"""
    query = update.callback_query
    await query.answer()
    
    effect_id = query.data.split(":")[1]
    effect = next((e for e in EFFECTS["list"] if e["id"] == effect_id), EFFECTS["list"][0])
    
    # Сохраняем выбор пользователя
    context.user_data["effect"] = effect_id
    
    await query.edit_message_text(
        f"✅ Выбран эффект: <b>{effect['name']}</b>\n\n"
        f"Теперь отправьте мне видео!",
        parse_mode=ParseMode.HTML
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    queue_count = len(processing_users)
    
    status_text = f"""
📊 <b>Статус бота</b>

🔄 Обрабатывается: {queue_count}
⚡ Онлайн: ✅
🎬 Режим: Sticker Creator

<i>Используйте /effects для выбора эффекта</i>
"""
    
    await update.message.reply_html(status_text)

async def download_video(file_url: str, max_size_mb: int = 20) -> bytes:
    """Скачать видео с ограничением по размеру"""
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as response:
            if response.status != 200:
                raise Exception(f"Ошибка загрузки: {response.status}")
            
            # Читаем с ограничением размера
            max_bytes = max_size_mb * 1024 * 1024
            video_data = bytearray()
            
            async for chunk in response.content.iter_chunked(8192):
                video_data.extend(chunk)
                if len(video_data) > max_bytes:
                    raise Exception(f"Видео превышает {max_size_mb}MB")
            
            return bytes(video_data)

async def convert_to_sticker(video_data: bytes, effect: str) -> bytes:
    """Конвертировать видео в стикер"""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f_in, \
         tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f_out:
        
        input_path = f_in.name
        output_path = f_out.name
        
        try:
            # Сохраняем видео
            f_in.write(video_data)
            f_in.flush()
            
            # Определяем фильтр по эффекту
            filter_complex = get_filter_by_effect(effect)
            
            # Команда FFmpeg для конвертации в стикер
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-t', '3',                    # Макс 3 секунды для стикера
                '-vf', filter_complex,
                '-c:v', 'libvpx-vp9',        # Кодек для WebM
                '-b:v', '500k',              # Битрейт
                '-crf', '30',                # Качество
                '-an',                       # Без звука
                '-deadline', 'realtime',     # Максимальная скорость
                '-cpu-used', '8',            # Агрессивная оптимизация
                '-y',                        # Перезаписать
                output_path
            ]
            
            logger.info(f"Запуск FFmpeg: {' '.join(cmd)}")
            
            # Выполняем команду
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg ошибка: {stderr.decode()}")
                raise Exception("Ошибка обработки видео")
            
            # Читаем результат
            with open(output_path, 'rb') as f:
                return f.read()
                
        finally:
            # Удаляем временные файлы
            try:
                os.unlink(input_path)
                os.unlink(output_path)
            except:
                pass

def get_filter_by_effect(effect_id: str) -> str:
    """Получить фильтр FFmpeg по эффекту"""
    filters = {
        "original": "scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
        "bw": "hue=s=0,scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
        "contrast": "eq=contrast=1.3:brightness=0.1,scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
        "bright": "eq=contrast=1.1:brightness=0.2:saturation=1.2,scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
        "vintage": "curves=all='0/0 0.5/0.9 1/1',colorbalance=rs=-0.1:gs=-0.1,scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
        "sepia": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131,scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
    }
    
    return filters.get(effect_id, filters["original"])

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящего видео"""
    user_id = update.effective_user.id
    
    # Проверяем, не обрабатывается ли уже видео
    if user_id in processing_users:
        await update.message.reply_text(
            "⏳ Ваше видео уже обрабатывается. Пожалуйста, подождите..."
        )
        return
    
    try:
        processing_users.add(user_id)
        
        # Получаем информацию о видео
        video = update.message.video
        file_size_mb = video.file_size / (1024 * 1024)
        
        # Проверяем размер
        if file_size_mb > 20:
            await update.message.reply_text(
                "❌ Видео слишком большое (>20MB). Отправьте видео поменьше."
            )
            return
        
        # Получаем выбранный эффект
        effect_id = context.user_data.get("effect", "original")
        effect = next((e for e in EFFECTS["list"] if e["id"] == effect_id), EFFECTS["list"][0])
        
        # Отправляем сообщение о начале обработки
        status_msg = await update.message.reply_text(
            f"🔄 <b>Начинаю обработку...</b>\n\n"
            f"📹 Размер: {file_size_mb:.1f}MB\n"
            f"🎨 Эффект: {effect['name']}\n"
            f"⏱️ Время: 10-30 секунд",
            parse_mode=ParseMode.HTML
        )
        
        # Получаем файл
        file = await video.get_file()
        file_url = file.file_path
        
        # Скачиваем видео
        await status_msg.edit_text("⏬ Скачиваю видео...")
        video_data = await download_video(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_url}")
        
        # Конвертируем в стикер
        await status_msg.edit_text("🎬 Обрабатываю видео...")
        sticker_data = await convert_to_sticker(video_data, effect_id)
        
        # Проверяем размер стикера (Telegram ограничение 256KB для VideoNote)
        if len(sticker_data) > 256 * 1024:
            logger.warning(f"Стикер слишком большой: {len(sticker_data)} bytes")
            # Пробуем сжать
            await status_msg.edit_text("📦 Сжимаю стикер...")
            sticker_data = await compress_sticker(sticker_data)
        
        # Отправляем стикер
        await status_msg.edit_text("📤 Отправляю стикер...")
        
        # Отправляем как VideoNote (круглый стикер)
        try:
            await update.message.reply_video_note(
                video_note=BytesIO(sticker_data),
                length=256,  # Размер для Telegram
                duration=3   # Длительность
            )
            await status_msg.delete()
        except Exception as e:
            logger.error(f"Ошибка отправки VideoNote: {e}")
            
            # Fallback: отправляем как обычное видео
            await update.message.reply_video(
                video=BytesIO(sticker_data),
                caption=f"🎭 Стикер готов! Эффект: {effect['name']}"
            )
            await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Ошибка обработки: {e}")
        
        error_msg = "❌ Произошла ошибка при обработке видео.\n\n"
        error_msg += "Возможные причины:\n"
        error_msg += "• Видео слишком длинное\n"
        error_msg += "• Неподдерживаемый формат\n"
        error_msg += "• Проблемы с обработкой\n\n"
        error_msg += "Попробуйте другое видео!"
        
        await update.message.reply_text(error_msg)
        
    finally:
        processing_users.discard(user_id)

async def compress_sticker(sticker_data: bytes) -> bytes:
    """Сжать стикер если он слишком большой"""
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f_in, \
         tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f_out:
        
        input_path = f_in.name
        output_path = f_out.name
        
        try:
            # Сохраняем оригинал
            f_in.write(sticker_data)
            f_in.flush()
            
            # Команда для сжатия
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-b:v', '300k',      # Меньший битрейт
                '-crf', '35',        # Больше сжатие
                '-an',
                '-y',
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            # Читаем сжатый файл
            with open(output_path, 'rb') as f:
                return f.read()
                
        finally:
            try:
                os.unlink(input_path)
                os.unlink(output_path)
            except:
                pass

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка видео как документа"""
    document = update.message.document
    
    # Проверяем, является ли документ видео
    if document.mime_type and document.mime_type.startswith('video/'):
        # Преобразуем в сообщение с видео
        update.message.video = document
        await handle_video(update, context)

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("effects", effects_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(effect_callback, pattern="^effect:"))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.Document.VIDEO, handle_document))
    
    # Запускаем бота
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
