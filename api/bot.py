import os
from bot import bot, dp
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

async def on_startup(app):
    url = f"https://{os.getenv('VERCEL_URL')}/api/bot"
    await bot.set_webhook(url)

app = web.Application()
app.on_startup.append(on_startup)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/api/bot")

if __name__ == "__main__":
    web.run_app(app, port=8000)
