// Telegram Bot - полная версия
const BOT_TOKEN = process.env.BOT_TOKEN;

export default async function handler(req, res) {
  // Включаем CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  // OPTIONS запрос
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }
  
  // GET запрос - health check
  if (req.method === 'GET') {
    res.status(200).json({
      status: 'online',
      service: 'Telegram Video Sticker Bot',
      webhook_configured: true,
      timestamp: new Date().toISOString()
    });
    return;
  }
  
  // POST запрос - Telegram webhook (ВАЖНО!)
  if (req.method === 'POST') {
    try {
      // Читаем тело запроса
      let body = '';
      for await (const chunk of req) {
        body += chunk.toString();
      }
      
      console.log('📨 Raw webhook body:', body.substring(0, 200));
      
      const data = JSON.parse(body);
      console.log('📨 Telegram update ID:', data.update_id);
      
      // Обработка сообщения
      if (data.message) {
        const chatId = data.message.chat.id;
        
        // Команда /start
        if (data.message.text === '/start') {
          console.log(`👋 Sending welcome to chat ${chatId}`);
          await sendToTelegram('sendMessage', {
            chat_id: chatId,
            text: '🎬 *Video Sticker Bot*\n\nЯ готов к работе! Отправьте мне видео.',
            parse_mode: 'Markdown'
          });
        }
        
        // Если видео
        if (data.message.video) {
          console.log(`🎥 Video received in chat ${chatId}`);
          await sendToTelegram('sendMessage', {
            chat_id: chatId,
            text: '✅ Видео получено! Обрабатываю...',
            parse_mode: 'Markdown'
          });
        }
      }
      
      // ВАЖНО: Telegram требует ответ {ok: true}
      res.status(200).json({ ok: true });
      
    } catch (error) {
      console.error('❌ Webhook error:', error);
      res.status(200).json({ ok: true }); // Всегда возвращаем успех Telegram
    }
    return;
  }
  
  // Любой другой метод
  res.status(404).json({ error: 'Not found' });
}

// Функция для отправки в Telegram
async function sendToTelegram(method, data) {
  if (!BOT_TOKEN) {
    console.log('⚠️ BOT_TOKEN not set, skipping:', method, data);
    return { ok: false, error: 'BOT_TOKEN not configured' };
  }
  
  const url = `https://api.telegram.org/bot${BOT_TOKEN}/${method}`;
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    
    const result = await response.json();
    console.log(`📤 Telegram ${method} response:`, result.ok ? '✅' : '❌');
    return result;
  } catch (error) {
    console.error(`❌ Telegram ${method} error:`, error);
    return { ok: false, error: error.message };
  }
}
