import express from 'express';
import fetch from 'node-fetch';
import { exec } from 'child_process';
import { promisify } from 'util';
import { createWriteStream, readFileSync, unlinkSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import cron from 'node-cron';

const execAsync = promisify(exec);
const app = express();
const PORT = process.env.PORT || 3000;

// ==================== КОНФИГУРАЦИЯ ====================
const BOT_TOKEN = process.env.BOT_TOKEN || 'ВАШ_ТОКЕН_БОТА';
const REPLIT_URL = process.env.REPLIT_URL || `https://${process.env.REPL_SLUG}.${process.env.REPL_OWNER}.repl.co`;
const PING_INTERVAL = 5; // минут
const ADMIN_CHAT_ID = process.env.ADMIN_CHAT_ID || '';

// Статистика
let serverStats = {
  startTime: new Date(),
  totalRequests: 0,
  lastPing: null,
  uptime: 0
};

// ==================== ФУНКЦИЯ "БУДИТЬ СЕРВЕР" ====================

// Пинг каждые 5 минут чтобы сервер не засыпал
cron.schedule(`*/${PING_INTERVAL} * * * *`, async () => {
  console.log(`🔄 [${new Date().toLocaleTimeString()}] Будим сервер...`);
  await keepServerAwake();
});

// Пинг самого себя
async function keepServerAwake() {
  try {
    const response = await fetch(`${REPLIT_URL}/ping`);
    const data = await response.json();
    serverStats.lastPing = new Date();
    serverStats.uptime = Date.now() - serverStats.startTime;
    console.log(`✅ Сервер активен. Uptime: ${formatUptime(serverStats.uptime)}`);
    
    // Отправляем статус админу каждые 30 минут
    if (ADMIN_CHAT_ID && new Date().getMinutes() % 30 === 0) {
      await sendStatusToAdmin();
    }
  } catch (error) {
    console.error('❌ Ошибка пинга:', error.message);
    // Пробуем альтернативный URL
    await fetch(REPLIT_URL).catch(e => console.error('Альтернативный пинг тоже не работает'));
  }
}

// ==================== НАСТРОЙКА СЕРВЕРА ====================
app.use(express.json());

// Маршрут для пинга
app.get('/ping', (req, res) => {
  serverStats.totalRequests++;
  serverStats.uptime = Date.now() - serverStats.startTime;
  
  res.json({
    status: 'active',
    uptime: formatUptime(serverStats.uptime),
    totalRequests: serverStats.totalRequests,
    memory: process.memoryUsage(),
    lastPing: serverStats.lastPing?.toLocaleTimeString() || 'never'
  });
});

// Главная страница
app.get('/', (req, res) => {
  serverStats.totalRequests++;
  
  res.send(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Video Sticker Bot</title>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {
          font-family: Arial, sans-serif;
          max-width: 800px;
          margin: 0 auto;
          padding: 20px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          min-height: 100vh;
        }
        .container {
          background: rgba(255, 255, 255, 0.1);
          backdrop-filter: blur(10px);
          border-radius: 20px;
          padding: 30px;
          margin-top: 20px;
        }
        h1 {
          text-align: center;
          margin-bottom: 30px;
        }
        .status {
          background: rgba(0, 0, 0, 0.2);
          padding: 15px;
          border-radius: 10px;
          margin: 15px 0;
        }
        .btn {
          display: inline-block;
          background: #4CAF50;
          color: white;
          padding: 12px 24px;
          text-decoration: none;
          border-radius: 8px;
          margin: 10px 5px;
          transition: transform 0.3s;
        }
        .btn:hover {
          transform: translateY(-2px);
          background: #45a049;
        }
        .telegram-btn {
          background: #0088cc;
        }
        .stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 15px;
          margin: 20px 0;
        }
        .stat-box {
          background: rgba(255, 255, 255, 0.15);
          padding: 15px;
          border-radius: 10px;
          text-align: center;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <h1>🎬 Video Sticker Bot</h1>
        
        <div class="status">
          <h3>✅ Бот активен</h3>
          <p>Сервер автоматически поддерживается в рабочем состоянии</p>
        </div>
        
        <div class="stats">
          <div class="stat-box">
            <h4>🕐 Uptime</h4>
            <p>${formatUptime(serverStats.uptime)}</p>
          </div>
          <div class="stat-box">
            <h4>📊 Запросов</h4>
            <p>${serverStats.totalRequests}</p>
          </div>
          <div class="stat-box">
            <h4>🔄 Пинг</h4>
            <p>Каждые ${PING_INTERVAL} мин</p>
          </div>
        </div>
        
        <h3>Как использовать:</h3>
        <ol>
          <li>Найдите в Telegram бота: @YourBotUsername</li>
          <li>Отправьте ему любое видео</li>
          <li>Бот автоматически конвертирует его в стикер</li>
          <li>Используйте стикер в своих чатах!</li>
        </ol>
        
        <div style="text-align: center; margin-top: 30px;">
          <a href="https://t.me/YourBotUsername" class="btn telegram-btn" target="_blank">
            📲 Открыть в Telegram
          </a>
          <a href="/ping" class="btn">🔄 Проверить статус</a>
        </div>
      </div>
      
      <script>
        // Автоматическое обновление статуса
        async function updateStatus() {
          try {
            const response = await fetch('/ping');
            const data = await response.json();
            document.querySelector('.status h3').innerHTML = 
              \`✅ Бот активен (Uptime: \${data.uptime})\`;
          } catch (error) {
            document.querySelector('.status h3').innerHTML = '❌ Ошибка соединения';
          }
        }
        
        // Обновляем статус каждые 30 секунд
        setInterval(updateStatus, 30000);
        
        // Пинг сервера при загрузке страницы
        updateStatus();
      </script>
    </body>
    </html>
  `);
});

// ==================== TELEGRAM WEBHOOK ====================

app.post('/webhook', async (req, res) => {
  serverStats.totalRequests++;
  
  try {
    const update = req.body;
    
    if (update.message) {
      await handleTelegramMessage(update.message);
    }
    
    res.status(200).json({ ok: true });
  } catch (error) {
    console.error('❌ Ошибка webhook:', error);
    res.status(200).json({ ok: true });
  }
});

// ==================== ОБРАБОТКА TELEGRAM СООБЩЕНИЙ ====================

async function handleTelegramMessage(message) {
  const chatId = message.chat.id;
  const text = message.text || '';

  // Команда /start
  if (text.startsWith('/start')) {
    await sendTelegramMessage(chatId,
      `🎬 *Video Sticker Bot*\n\n` +
      `Привет! Я превращаю видео в Telegram стикеры.\n\n` +
      `*Как использовать:*\n` +
      `1. Отправь мне любое видео\n` +
      `2. Я скачаю и обработаю его\n` +
      `3. Пришлю готовый стикер!\n\n` +
      `*О сервере:*\n` +
      `✅ Автопилот включен\n` +
      `🔄 Пинг каждые ${PING_INTERVAL} минут\n` +
      `⚡ Replit бесплатный тариф\n\n` +
      `Отправь видео прямо сейчас!`
    );
  }

  // Команда /status
  else if (text.startsWith('/status')) {
    await sendTelegramMessage(chatId,
      `📊 *Статус сервера*\n\n` +
      `🕐 Uptime: ${formatUptime(serverStats.uptime)}\n` +
      `📊 Запросов: ${serverStats.totalRequests}\n` +
      `🔄 Последний пинг: ${serverStats.lastPing?.toLocaleTimeString() || 'никогда'}\n` +
      `⚡ Пинг каждые: ${PING_INTERVAL} минут\n\n` +
      `Сервер активен и работает! ✅`
    );
  }

  // Обработка видео
  else if (message.video || message.document) {
    await processVideo(chatId, message);
  }

  // Любое другое сообщение
  else if (text) {
    await sendTelegramMessage(chatId,
      `Отправь мне видео, и я сделаю из него стикер!\n\n` +
      `Доступные команды:\n` +
      `/start - начать работу\n` +
      `/status - статус сервера\n` +
      `/help - помощь`
    );
  }
}

// ==================== ОБРАБОТКА ВИДЕО ====================

async function processVideo(chatId, message) {
  try {
    await sendTelegramMessage(chatId, '🔄 Скачиваю видео...');

    // Получаем информацию о файле
    const fileId = message.video?.file_id || message.document?.file_id;
    const fileUrl = await getTelegramFileUrl(fileId);
    
    // Скачиваем файл
    const videoPath = join(tmpdir(), `video_${Date.now()}.mp4`);
    await downloadFile(fileUrl, videoPath);
    
    await sendTelegramMessage(chatId, '⚡ Конвертирую в стикер...');
    
    // Конвертируем в WebM стикер
    const stickerPath = join(tmpdir(), `sticker_${Date.now()}.webm`);
    await convertToWebM(videoPath, stickerPath);
    
    // Отправляем стикер
    await sendTelegramDocument(chatId, stickerPath, 'sticker.webm');
    
    await sendTelegramMessage(chatId, '✅ Готово! Стикер создан!');
    
    // Очищаем временные файлы
    unlinkSync(videoPath);
    unlinkSync(stickerPath);
    
  } catch (error) {
    console.error('❌ Ошибка обработки видео:', error);
    await sendTelegramMessage(chatId, `❌ Ошибка: ${error.message}`);
  }
}

// ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

// Форматирование времени
function formatUptime(ms) {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) return `${days}д ${hours % 24}ч`;
  if (hours > 0) return `${hours}ч ${minutes % 60}м`;
  if (minutes > 0) return `${minutes}м ${seconds % 60}с`;
  return `${seconds}с`;
}

// Конвертация видео в WebM
async function convertToWebM(inputPath, outputPath) {
  const cmd = `ffmpeg -i "${inputPath}" -vf "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:-1:-1:color=black" -c:v libvpx-vp9 -crf 30 -b:v 0 -t 3 -y "${outputPath}"`;
  await execAsync(cmd, { timeout: 60000 });
}

// Скачивание файла
async function downloadFile(url, outputPath) {
  const response = await fetch(url);
  const writer = createWriteStream(outputPath);
  response.body.pipe(writer);
  
  return new Promise((resolve, reject) => {
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
}

// Получение URL файла Telegram
async function getTelegramFileUrl(fileId) {
  const response = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/getFile?file_id=${fileId}`);
  const data = await response.json();
  return `https://api.telegram.org/file/bot${BOT_TOKEN}/${data.result.file_path}`;
}

// Отправка сообщения в Telegram
async function sendTelegramMessage(chatId, text) {
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: 'Markdown'
    })
  });
}

// Отправка документа в Telegram
async function sendTelegramDocument(chatId, filePath, filename) {
  const formData = new FormData();
  const fileBuffer = readFileSync(filePath);
  
  formData.append('chat_id', chatId);
  formData.append('document', new Blob([fileBuffer]), filename);
  
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendDocument`, {
    method: 'POST',
    body: formData
  });
}

// Отправка статуса админу
async function sendStatusToAdmin() {
  if (!ADMIN_CHAT_ID) return;
  
  await sendTelegramMessage(ADMIN_CHAT_ID,
    `📊 *Статус сервера*\n\n` +
    `🕐 Uptime: ${formatUptime(serverStats.uptime)}\n` +
    `📊 Запросов: ${serverStats.totalRequests}\n` +
    `💾 Память: ${Math.round(process.memoryUsage().heapUsed / 1024 / 1024)}MB\n\n` +
    `✅ Сервер активен, пинг работает`
  );
}

// ==================== ЗАПУСК СЕРВЕРА ====================

// Запускаем сервер
app.listen(PORT, () => {
  console.log(`
  🚀 Video Sticker Bot запущен!
  🔗 URL: ${REPLIT_URL}
  📊 Порт: ${PORT}
  🔄 Автопилот: включен (пинг каждые ${PING_INTERVAL} минут)
  ⏰ Время запуска: ${serverStats.startTime.toLocaleString()}
  `);
  
  // Первый пинг сразу после запуска
  setTimeout(() => {
    keepServerAwake();
  }, 5000);
});

// Обработка ошибок
process.on('uncaughtException', (error) => {
  console.error('❌ Необработанная ошибка:', error);
});

// Форма для FormData
class FormData {
  constructor() {
    this.boundary = '----VideoStickerBotBoundary' + Math.random().toString(16);
    this.body = [];
  }
  
  append(name, value, filename) {
    let content = `--${this.boundary}\r\n`;
    content += `Content-Disposition: form-data; name="${name}"`;
    
    if (filename) {
      content += `; filename="${filename}"\r\n`;
      content += `Content-Type: application/octet-stream\r\n\r\n`;
      this.body.push(Buffer.from(content, 'utf8'));
      this.body.push(value);
    } else {
      content += `\r\n\r\n${value}`;
      this.body.push(Buffer.from(content + '\r\n', 'utf8'));
    }
  }
  
  getBuffer() {
    const finalBoundary = Buffer.from(`--${this.boundary}--\r\n`, 'utf8');
    return Buffer.concat([...this.body, finalBoundary]);
  }
  
  getHeaders() {
    return {
      'Content-Type': `multipart/form-data; boundary=${this.boundary}`,
      'Content-Length': this.getBuffer().length.toString()
    };
  }
}
