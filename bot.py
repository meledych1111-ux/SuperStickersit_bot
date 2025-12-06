import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import asyncio

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8062458019:AAFY6yl5Ijy-R1_hiyAc25j5dij9IjJMTWY"
WEBHOOK_URL = os.environ.get("RAILWAY_STATIC_URL", "")

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === ОБРАБОТЧИКИ ===
async def start(update: Update, context):
    await update.message.reply_text(
        "🎬 Video Sticker Bot работает на Railway!\n\n"
        "Отправьте мне видео, и я создам стикер!"
    )

async def handle_video(update: Update, context):
    video = update.message.video
    file_size_mb = video.file_size / (1024 * 1024)
    
    await update.message.reply_text(
        f"✅ Видео получено!\n"
        f"📹 Размер: {file_size_mb:.1f}MB\n"
        f"⏱️ Длительность: {video.duration} сек\n\n"
        "🎬 Обработка скоро будет..."
    )

# === WEBHOOK НАСТРОЙКА ===
async def set_webhook():
    """Установка вебхука"""
    if WEBHOOK_URL:
        import httpx
        
        webhook_url = f"{WEBHOOK_URL}/webhook"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                json={
                    "url": webhook_url,
                    "max_connections": 40,
                    "allowed_updates": ["message", "callback_query"]
                }
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Webhook установлен: {webhook_url}")
            else:
                logger.error(f"❌ Ошибка webhook: {response.text}")
    else:
        logger.warning("⚠️ RAILWAY_STATIC_URL не найден, вебхук не установлен")

# === FASTAPI ДЛЯ WEBHOOK ===
from fastapi import FastAPI, Request
import uvicorn

# Создаем FastAPI приложение
app = FastAPI()
telegram_app = None

@app.on_event("startup")
async def startup_event():
    """Запуск при старте"""
    global telegram_app
    
    # Создаем Telegram приложение
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    # Инициализируем
    await telegram_app.initialize()
    
    # Устанавливаем вебхук
    await set_webhook()
    
    logger.info("🚀 Бот запущен на Railway!")

@app.post("/webhook")
async def webhook(request: Request):
    """Обработка webhook от Telegram"""
    try:
        # Получаем обновление
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        
        # Обрабатываем
        await telegram_app.process_update(update)
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False, "error": str(e)}

@app.get("/")
async def root():
    """Главная страница"""
    return {
        "status": "online",
        "bot": "@ваш_бот",
        "mode": "webhook",
        "url": WEBHOOK_URL or "Not set"
    }

@app.get("/health")
async def health():
    """Health check для Railway"""
    return {"status": "healthy"}

# Запуск сервера
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
