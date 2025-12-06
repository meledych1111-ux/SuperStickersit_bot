import os
import logging
import asyncio
import time
import tempfile
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    CallbackQueryHandler,
    ContextTypes
)
from fastapi import FastAPI, Request
import uvicorn
import threading
import requests
from io import BytesIO

# Импорт нашего обработчика видео
from ffmpeg_processor import VideoProcessor

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8062458019:AAFY6yl5Ijy-R1_hiyAc25j5dij9IjJMTWY")
PORT = int(os.getenv("PORT", 10000))
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === ИНИЦИАЛИЗАЦИЯ ===
video_processor = VideoProcessor()
user_data = {}
bot_start_time = time.time()

# === ЭФФЕКТЫ ДЛЯ ВИДЕО ===
VIDEO_EFFECTS = [
    {
        "id": "original",
        "name": "⚪ Оригинал",
        "emoji": "⚪",
        "ffmpeg_filter": "scale=512:512:force_original_aspect_ratio=increase,crop=512:512"
    },
    {
        "id": "bw",
        "name": "⚫ Черно-белый",
        "emoji": "⚫",
        "ffmpeg_filter": "hue=s=0,scale=512:512:force_original_aspect_ratio=increase,crop=512:512"
    },
    {
        "id": "contrast",
        "name": "🔆 Контраст+",
        "emoji": "🔆",
        "ffmpeg_filter": "eq=contrast=1.5:brightness=0.1,saturation=1.3,scale=512:512:force_original_aspect_ratio=increase,crop=512:512"
    },
    {
        "id": "vintage",
        "name": "🟤 Винтаж",
        "emoji": "🟤",
        "ffmpeg_filter": "curves=all='0/0 0.4/0.6 1/1',colorbalance=rs=-0.1:gs=-0.1,scale=512:512:force_original_aspect_ratio=increase,crop=512:512"
    },
    {
        "id": "sepia",
        "name": "🟫 Сепия",
        "emoji": "🟫",
        "ffmpeg_filter": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131,scale=512:512:force_original_aspect_ratio=increase,crop=512:512"
    },
    {
        "id": "cool",
        "name": "❄️ Холодный",
        "emoji": "❄️",
        "ffmpeg_filter": "colorbalance=rs=-0.1:bs=0.1,scale=512:512:force_original_aspect_ratio=increase,crop=512:512"
    },
    {
        "id": "warm",
        "name": "🔥 Теплый",
        "emoji": "🔥",
        "ffmpeg_filter": "colorbalance=rs=0.1:gs=0.1,scale=512:512:force_original_aspect_ratio=increase,crop=512:512"
    },
    {
        "id": "sharp",
        "name": "💎 Резкость",
        "emoji": "💎",
        "ffmpeg_filter": "unsharp=5:5:1.0:5:5:0.0,scale=512:512:force_original_aspect_ratio=increase,crop=512:512"
    }
]

# === ОБРАБОТЧИКИ TELEGRAM ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("🎨 Выбрать эффект", callback_data="show_effects")],
        [InlineKeyboardButton("✨ Случайный эффект", callback_data="random_effect")]
    ]
    
    await update.message.reply_html(
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        f"🎬 <b>Video Sticker Bot</b> 🎬\n\n"
        f"📹 <b>Реальная обработка видео через FFmpeg!</b>\n\n"
        f"🌐 <b>Сервер:</b> Render.com\n"
        f"⚡ <b>FFmpeg:</b> Установлен\n"
        f"⏱ <b>Аптайм:</b> {get_uptime()}\n\n"
        f"<b>Как использовать:</b>\n"
        f"1. Выберите эффект\n"
        f"2. Отправьте видео (до 20MB)\n"
        f"3. Получите готовый стикер!\n\n"
        f"<i>Нажмите кнопку ниже чтобы начать:</i>",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_effects_keyboard():
    """Создание клавиатуры с эффектами"""
    keyboard = []
    
    # Создаем кнопки по 2 в ряд
    for i in range(0, len(VIDEO_EFFECTS), 2):
        row = []
        for effect in VIDEO_EFFECTS[i:i+2]:
            row.append(InlineKeyboardButton(
                f"{effect['emoji']} {effect['name'].split()[1]}",
                callback_data=f"effect_{effect['id']}"
            ))
        keyboard.append(row)
    
    # Дополнительные кнопки
    keyboard.append([
        InlineKeyboardButton("🎲 Случайный", callback_data="random_effect"),
        InlineKeyboardButton("📊 Статус", callback_data="status")
    ])
    
    return InlineKeyboardMarkup(keyboard)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline кнопок"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    data = query.data
    
    if data == "show_effects":
        reply_markup = await show_effects_keyboard()
        await query.edit_message_text(
            "🎨 <b>Выберите эффект для обработки видео:</b>\n\n"
            "<i>Все эффекты применяются в реальном времени через FFmpeg</i>",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    
    elif data.startswith("effect_"):
        effect_id = data.replace("effect_", "")
        effect = next((e for e in VIDEO_EFFECTS if e["id"] == effect_id), VIDEO_EFFECTS[0])
        
        # Сохраняем выбор пользователя
        user_data[user_id] = {
            'effect': effect_id,
            'effect_name': effect['name'],
            'ffmpeg_filter': effect['ffmpeg_filter']
        }
        
        await query.edit_message_text(
            f"✅ <b>Выбран эффект: {effect['emoji']} {effect['name']}</b>\n\n"
            f"Теперь отправьте мне видео для обработки!\n\n"
            f"<b>Ограничения:</b>\n"
            f"• Максимальный размер: 20MB\n"
            f"• Длительность: до 30 секунд\n"
            f"• Форматы: MP4, MOV, AVI\n\n"
            f"<i>Обработка займет 5-15 секунд</i>",
            parse_mode="HTML"
        )
    
    elif data == "random_effect":
        import random
        effect = random.choice(VIDEO_EFFECTS)
        
        user_data[user_id] = {
            'effect': effect['id'],
            'effect_name': effect['name'],
            'ffmpeg_filter': effect['ffmpeg_filter']
        }
        
        await query.edit_message_text(
            f"🎲 <b>Случайный эффект: {effect['emoji']} {effect['name']}</b>\n\n"
            f"Теперь отправьте мне видео!\n\n"
            f"<i>FFmpeg фильтр: {effect['ffmpeg_filter'][:50]}...</i>",
            parse_mode="HTML"
        )
    
    elif data == "status":
        await status_info(query)

async def status_info(query):
    """Показать статус"""
    uptime = get_uptime()
    processed_count = video_processor.get_stats()
    
    status_text = (
        f"📊 <b>Статус бота</b>\n\n"
        f"🌐 <b>Сервер:</b> Render.com\n"
        f"⏱ <b>Аптайм:</b> {uptime}\n"
        f"🎬 <b>Обработано видео:</b> {processed_count}\n"
        f"🎨 <b>Эффектов:</b> {len(VIDEO_EFFECTS)}\n"
        f"⚡ <b>FFmpeg:</b> Работает\n\n"
        f"<i>Бот обрабатывает видео в реальном времени</i>"
    )
    
    await query.edit_message_text(
        status_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎨 Выбрать эффект", callback_data="show_effects")
        ]])
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящего видео"""
    user_id = update.effective_user.id
    video = update.message.video
    
    # Проверка размера
    file_size_mb = video.file_size / (1024 * 1024)
    if file_size_mb > 20:
        await update.message.reply_text(
            "❌ <b>Видео слишком большое!</b>\n\n"
            f"Размер: {file_size_mb:.1f}MB\n"
            "Максимум: 20MB\n\n"
            "Пожалуйста, отправьте видео поменьше.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, выбран ли эффект
    if user_id not in user_data:
        keyboard = [[InlineKeyboardButton("🎨 Выбрать эффект сейчас", callback_data="show_effects")]]
        
        await update.message.reply_html(
            "⚠️ <b>Сначала выберите эффект!</b>\n\n"
            "Пожалуйста, выберите эффект для обработки видео:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Получаем выбранный эффект
    effect_info = user_data[user_id]
    effect_name = effect_info['effect_name']
    ffmpeg_filter = effect_info['ffmpeg_filter']
    
    # Сообщение о начале обработки
    processing_msg = await update.message.reply_html(
        f"🔄 <b>Начинаю обработку видео...</b>\n\n"
        f"📹 <b>Информация:</b>\n"
        f"• Размер: {file_size_mb:.1f}MB\n"
        f"• Длительность: {video.duration} сек\n"
        f"• Эффект: {effect_name}\n\n"
        f"⚡ <b>Использую FFmpeg для обработки...</b>"
    )
    
    try:
        # Получаем файл видео
        file = await video.get_file()
        file_url = file.file_path
        
        # Скачиваем видео
        await processing_msg.edit_text(
            f"⏬ <b>Скачиваю видео с Telegram...</b>\n\n"
            f"📥 Размер: {file_size_mb:.1f}MB",
            parse_mode="HTML"
        )
        
        # Скачиваем видео
        video_data = await download_video_from_telegram(file_url)
        
        # Обрабатываем видео
        await processing_msg.edit_text(
            f"🎬 <b>Обрабатываю видео через FFmpeg...</b>\n\n"
            f"🔧 Фильтр: {ffmpeg_filter[:60]}...",
            parse_mode="HTML"
        )
        
        # Обработка через FFmpeg
        start_time = time.time()
        processed_video = await video_processor.process_video(
            video_data=video_data,
            ffmpeg_filter=ffmpeg_filter,
            max_duration=min(video.duration, 10)  # Макс 10 секунд для стикера
        )
        processing_time = time.time() - start_time
        
        # Проверяем размер результата
        if len(processed_video) > 50 * 1024 * 1024:  # 50MB
            raise ValueError("Результат слишком большой")
        
        # Отправляем результат
        await processing_msg.edit_text(
            f"📤 <b>Отправляю результат...</b>\n\n"
            f"✅ Обработка заняла: {processing_time:.1f} сек",
            parse_mode="HTML"
        )
        
        # Отправляем как видео
        await update.message.reply_video(
            video=BytesIO(processed_video),
            caption=f"🎬 Готово! Эффект: {effect_name}\n⏱ Время: {processing_time:.1f}с",
            filename="sticker.mp4"
        )
        
        # Удаляем сообщение о процессе
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Ошибка обработки видео: {e}")
        
        error_msg = (
            f"❌ <b>Ошибка при обработке видео</b>\n\n"
            f"<b>Причина:</b> {str(e)[:100]}\n\n"
            f"<b>Что можно сделать:</b>\n"
            f"1. Попробуйте другое видео\n"
            f"2. Выберите другой эффект\n"
            f"3. Убедитесь что видео не повреждено\n\n"
            f"<i>Если проблема повторяется, свяжитесь с поддержкой</i>"
        )
        
        try:
            await processing_msg.edit_text(error_msg, parse_mode="HTML")
        except:
            await update.message.reply_html(error_msg)

async def download_video_from_telegram(file_path: str) -> bytes:
    """Скачать видео из Telegram"""
    import aiohttp
    
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as response:
            if response.status == 200:
                return await response.read()
            else:
                raise Exception(f"Ошибка загрузки: {response.status}")

def get_uptime():
    """Получить время работы"""
    uptime = time.time() - bot_start_time
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    return f"{hours}ч {minutes}м"

# === ФУНКЦИИ ДЛЯ ПОДДЕРЖАНИЯ АКТИВНОСТИ ===
def keep_alive_worker():
    """Фоновая задача для поддержания активности"""
    if not RENDER_URL:
        return
    
    while True:
        try:
            response = requests.get(f"{RENDER_URL}/ping", timeout=10)
            logger.debug(f"Keep-alive ping: {response.status_code}")
        except Exception as e:
            logger.warning(f"Keep-alive error: {e}")
        
        # Ждем 8 минут (Render засыпает через 15)
        time.sleep(480)

# === СОЗДАНИЕ ПРИЛОЖЕНИЯ ===
def create_telegram_app():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", lambda u, c: status_info(u)))
    application.add_handler(CommandHandler("effects", 
        lambda u, c: u.message.reply_text("🎨 Выберите эффект:", 
            reply_markup=show_effects_keyboard())))
    
    # Callback кнопки
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Видео сообщения
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    return application

# === FASTAPI СЕРВЕР ===
app = FastAPI(title="Video Sticker Bot")
telegram_app = None

@app.on_event("startup")
async def startup():
    """Запуск при старте"""
    global telegram_app
    
    logger.info("🚀 Запуск Video Sticker Bot с FFmpeg...")
    
    # Проверяем FFmpeg
    if video_processor.check_ffmpeg():
        logger.info("✅ FFmpeg доступен")
    else:
        logger.error("❌ FFmpeg не найден!")
    
    # Создаем Telegram приложение
    telegram_app = create_telegram_app()
    await telegram_app.initialize()
    
    # Устанавливаем вебхук
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook"
        await telegram_app.bot.set_webhook(webhook_url)
        logger.info(f"✅ Webhook установлен: {webhook_url}")
    
    # Запускаем keep-alive
    if RENDER_URL:
        threading.Thread(target=keep_alive_worker, daemon=True).start()
        logger.info("✅ Keep-alive запущен")
    
    logger.info("✅ Бот готов к работе!")

@app.post("/webhook")
async def webhook(request: Request):
    """Обработка вебхука"""
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False, "error": str(e)}, 500

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Video Sticker Bot",
        "ffmpeg": video_processor.check_ffmpeg(),
        "effects": len(VIDEO_EFFECTS),
        "uptime": get_uptime()
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/ping")
async def ping():
    return {"pong": True, "timestamp": time.time()}

@app.get("/test/ffmpeg")
async def test_ffmpeg():
    """Тест FFmpeg"""
    test_result = video_processor.test_ffmpeg()
    return test_result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
