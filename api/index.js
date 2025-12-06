// Простейший Telegram бот для Vercel
const TelegramBot = require('node-telegram-bot-api');

// Проверяем наличие токена
if (!process.env.BOT_TOKEN) {
  console.error('❌ ERROR: BOT_TOKEN is not set!');
  console.error('Add it in Vercel Dashboard → Settings → Environment Variables');
}

// Создаем бота
const bot = new TelegramBot(process.env.BOT_TOKEN, {
  polling: false,
  webHook: false
});

// Главный обработчик для Vercel Functions
module.exports = async (req, res) => {
  // Устанавливаем CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  // OPTIONS запрос (CORS)
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }
  
  // Health check
  if (req.method === 'GET') {
    res.status(200).json({
      status: 'online',
      service: 'Telegram Video Sticker Bot',
      fluid_compute: true,
      message: 'Send POST request with Telegram webhook data'
    });
    return;
  }
  
  // Обработка Telegram webhook
  if (req.method === 'POST') {
    try {
      // Читаем тело запроса
      let body = '';
      req.on('data', chunk => {
        body += chunk.toString();
      });
      
      req.on('end', async () => {
        try {
          const data = JSON.parse(body);
          console.log('📨 Telegram update:', data.update_id);
          
          const chatId = data.message?.chat?.id;
          
          // Команда /start
          if (data.message?.text === '/start') {
            await bot.sendMessage(
              chatId,
              '🎬 *Video Sticker Bot*\n\n' +
              'Отправьте мне видео, и я сделаю стикер!\n\n' +
              '✅ До 50MB\n' +
              '✅ До 60 секунд\n' +
              '⚡ Fluid Compute включен',
              { parse_mode: 'Markdown' }
            );
          }
          
          // Если отправили видео
          if (data.message?.video) {
            await bot.sendMessage(
              chatId,
              '🔄 Видео получено! В будущем здесь будет конвертация в стикер.'
            );
          }
          
          res.status(200).json({ ok: true });
          
        } catch (error) {
          console.error('Error parsing webhook:', error);
          res.status(500).json({ error: error.message });
        }
      });
      
    } catch (error) {
      console.error('Handler error:', error);
      res.status(500).json({ error: error.message });
    }
    return;
  }
  
  // Любой другой метод
  res.status(404).json({ error: 'Not found' });
};
