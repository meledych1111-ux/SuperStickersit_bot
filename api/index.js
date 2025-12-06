// Минимальный Telegram бот для Vercel
module.exports = async (req, res) => {
  // Включаем CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  // OPTIONS запрос
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  // GET запрос - health check
  if (req.method === 'GET') {
    return res.status(200).json({
      status: 'online',
      service: 'Telegram Video Sticker Bot',
      timestamp: new Date().toISOString(),
      message: 'Send POST request for Telegram webhook'
    });
  }
  
  // POST запрос - Telegram webhook
  if (req.method === 'POST') {
    try {
      // Читаем тело запроса
      let body = '';
      for await (const chunk of req) {
        body += chunk;
      }
      
      const data = JSON.parse(body);
      console.log('📨 Telegram update received:', data.update_id);
      
      // Всегда возвращаем успех Telegram
      return res.status(200).json({ ok: true });
      
    } catch (error) {
      console.error('Error:', error);
      return res.status(500).json({ error: error.message });
    }
  }
  
  // Любой другой метод
  return res.status(404).json({ error: 'Not found' });
};
