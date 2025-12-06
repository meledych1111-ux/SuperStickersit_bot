import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from fastapi import FastAPI, Request, Response
import uvicorn
import json
import time

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8062458019:AAFY6yl5Ijy-R1_hiyAc25j5dij9IjJMTWY"
PORT = int(os.environ.get("PORT", 8080))

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === ТЕЛЕГРАМ БОТ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [[InlineKeyboardButton("🎨 Выбрать эффект", callback_data="show_effects")]]
    
    await update.message.reply_html(
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        f"🎬 <b>Video Sticker Bot</b>\n\n"
        f"Выберите эффект и отправьте видео!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "show_effects":
        keyboard = [
            [InlineKeyboardButton("⚫ Черно-белый", callback_data="effect_bw")],
            [InlineKeyboardButton("🔆 Контраст", callback_data="effect_contrast")]
        ]
        await query.edit_message_text(
            "🎨 Выберите эффект:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data.startswith("effect_"):
        await query.edit_message_text("✅ Эффект выбран! Отправьте видео.")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    await update.message.reply_text(f"✅ Видео получено! Размер: {video.file_size / 1024 / 1024:.1f}MB")

# === СОЗДАНИЕ ПРИЛОЖЕНИЯ ===
def create_telegram_app():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    return application

# === FASTAPI СЕРВЕР ===
app = FastAPI(title="Telegram Video Bot")
start_time = time.time()
telegram_app = None

@app.on_event("startup")
async def startup():
    """Запуск при старте"""
    global telegram_app
    logger.info("🚀 Starting Telegram Bot...")
    
    # Создаем приложение
    telegram_app = create_telegram_app()
    await telegram_app.initialize()
    
    # Пробуем установить вебхук если есть Railway домен
    railway_domain = os.environ.get("RAILWAY_STATIC_URL")
    if railway_domain:
        webhook_url = f"{railway_domain}/webhook"
        try:
            await telegram_app.bot.set_webhook(webhook_url)
            logger.info(f"✅ Webhook set: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}")
    
    logger.info("✅ Bot started successfully")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Обработка вебхука от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(content=json.dumps({"ok": False}), status_code=500)

@app.get("/")
async def root():
    """Главная страница - ВАЖНО для healthcheck!"""
    return {
        "status": "online",
        "service": "Telegram Video Sticker Bot",
        "uptime": time.time() - start_time,
        "timestamp": time.time()
    }

@app.get("/health")
@app.get("/healthz")
@app.get("/healthcheck")
@app.get("/api/health")
async def health_check():
    """Health check endpoint - Railway проверяет именно его!"""
    return Response(
        content=json.dumps({
            "status": "healthy",
            "timestamp": time.time(),
            "service": "telegram-bot",
            "version": "1.0"
        }),
        status_code=200,
        media_type="application/json"
    )

@app.get("/info")
async def info():
    """Информация о Railway окружении"""
    return {
        "railway_static_url": os.environ.get("RAILWAY_STATIC_URL"),
        "railway_environment": os.environ.get("RAILWAY_ENVIRONMENT"),
        "port": PORT,
        "all_env_keys": list(os.environ.keys())
    }

# Запуск сервера
if __name__ == "__main__":
    uvicorn.run(
        "bot:app",  # Важно: передаем app как строку
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=True  # Включаем логи доступа для отладки
    )
