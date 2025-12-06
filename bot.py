import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from fastapi import FastAPI, Request, Response
import uvicorn
import json

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8062458019:AAFY6yl5Ijy-R1_hiyAc25j5dij9IjJMTWY"

# Railway автоматически устанавливает PORT
PORT = int(os.environ.get("PORT", 8080))

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === ТЕЛЕГРАМ БОТ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("🎨 Выбрать эффект", callback_data="show_effects")],
        [InlineKeyboardButton("✨ Случайный эффект", callback_data="random_effect")]
    ]
    
    await update.message.reply_html(
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        f"🎬 <b>Video Sticker Bot (Railway)</b>\n\n"
        f"📹 <b>Как использовать:</b>\n"
        f"1. Выберите эффект\n"
        f"2. Отправьте видео\n"
        f"3. Получите стикер!\n\n"
        f"<i>Режим: 🌐 Webhook</i>",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "show_effects":
        keyboard = [
            [InlineKeyboardButton("⚫ Черно-белый", callback_data="effect_bw")],
            [InlineKeyboardButton("🔆 Контраст", callback_data="effect_contrast")],
            [InlineKeyboardButton("🟤 Винтаж", callback_data="effect_vintage")],
            [InlineKeyboardButton("✨ Яркий", callback_data="effect_bright")]
        ]
        
        await query.edit_message_text(
            "🎨 <b>Выберите эффект:</b>\n\n"
            "После выбора отправьте видео!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    
    elif query.data.startswith("effect_"):
        effect = query.data.replace("effect_", "")
        effect_names = {
            "bw": "Черно-белый",
            "contrast": "Контраст", 
            "vintage": "Винтаж",
            "bright": "Яркий"
        }
        
        await query.edit_message_text(
            f"✅ <b>Выбран эффект: {effect_names.get(effect, effect)}</b>\n\n"
            f"Теперь отправьте мне видео для обработки!",
            parse_mode="HTML"
        )
    
    elif query.data == "random_effect":
        import random
        effects = ["⚫ Черно-белый", "🔆 Контраст", "🟤 Винтаж", "✨ Яркий"]
        chosen = random.choice(effects)
        
        await query.edit_message_text(
            f"🎲 <b>Случайный эффект: {chosen}</b>\n\n"
            f"Отправьте видео для обработки!",
            parse_mode="HTML"
        )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка видео"""
    video = update.message.video
    size_mb = video.file_size / (1024 * 1024)
    
    await update.message.reply_text(
        f"✅ <b>Видео получено!</b>\n\n"
        f"📹 Размер: {size_mb:.1f}MB\n"
        f"⏱️ Длительность: {video.duration} сек\n\n"
        f"🎬 Режим: Railway Webhook\n"
        f"🔧 FFmpeg обработка скоро будет добавлена",
        parse_mode="HTML"
    )

# === СОЗДАНИЕ ПРИЛОЖЕНИЯ ===
def create_telegram_app():
    """Создаем Telegram приложение"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    # Текстовые сообщения
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        lambda update, ctx: update.message.reply_text("📹 Отправьте мне видео!")
    ))
    
    return application

# === FASTAPI WEBHOOK СЕРВЕР ===
app = FastAPI()
telegram_app = None

@app.on_event("startup")
async def startup():
    """Запуск при старте"""
    global telegram_app
    
    logger.info("🚀 Запускаю Telegram бота...")
    
    # Создаем Telegram приложение
    telegram_app = create_telegram_app()
    
    # Инициализируем (НО НЕ ЗАПУСКАЕМ polling!)
    await telegram_app.initialize()
    
    # Получаем Railway домен из переменных окружения
    railway_domain = os.environ.get("RAILWAY_STATIC_URL")
    
    if railway_domain:
        # Устанавливаем вебхук
        webhook_url = f"{railway_domain}/webhook"
        
        # Удаляем старый вебхук если есть
        await telegram_app.bot.delete_webhook()
        
        # Устанавливаем новый
        await telegram_app.bot.set_webhook(
            url=webhook_url,
            max_connections=40,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info(f"✅ Webhook установлен: {webhook_url}")
        
        # Получаем информацию о боте
        bot_info = await telegram_app.bot.get_me()
        logger.info(f"🤖 Бот: @{bot_info.username} ({bot_info.id})")
    else:
        logger.error("❌ RAILWAY_STATIC_URL не найден!")
        logger.info("ℹ️  Проверьте Railway Variables")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Endpoint для вебхука от Telegram"""
    try:
        # Получаем данные
        data = await request.json()
        
        # Создаем Update объект
        update = Update.de_json(data, telegram_app.bot)
        
        # Обрабатываем
        await telegram_app.process_update(update)
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False, "error": str(e)}, 500

@app.get("/")
async def root():
    """Главная страница"""
    railway_domain = os.environ.get("RAILWAY_STATIC_URL", "не найден")
    
    return {
        "status": "online",
        "service": "Telegram Video Sticker Bot",
        "mode": "webhook",
        "railway_domain": railway_domain,
        "bot_token": BOT_TOKEN[:10] + "..."
    }

@app.get("/health")
async def health():
    """Health check для Railway"""
    return {
        "status": "healthy",
        "timestamp": "now",
        "bot": "running"
    }

@app.get("/set-webhook")
async def set_webhook_manual():
    """Ручная установка вебхука (для теста)"""
    railway_domain = os.environ.get("RAILWAY_STATIC_URL")
    
    if not railway_domain:
        return {"error": "RAILWAY_STATIC_URL not found"}
    
    webhook_url = f"{railway_domain}/webhook"
    
    import requests
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={"url": webhook_url}
    )
    
    return {
        "webhook_url": webhook_url,
        "telegram_response": response.json()
    }

# === ЗАПУСК СЕРВЕРА ===
if __name__ == "__main__":
    # ВАЖНО: НЕ используем app.run_polling()!
    # Только uvicorn для webhook
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
