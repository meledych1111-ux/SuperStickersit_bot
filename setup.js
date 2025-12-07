#!/usr/bin/env node

console.log(`
╔══════════════════════════════════════════╗
║     🛠️  УСТАНОВКА VIDEO STICKER BOT    ║
╚══════════════════════════════════════════╝
`);

const fs = require('fs');
const { execSync } = require('child_process');

async function setup() {
  try {
    console.log('🔍 Шаг 1: Проверка системы...');
    
    // Проверка Node.js
    console.log(`✅ Node.js: ${process.version}`);
    
    // Проверка файлов
    console.log('\n📁 Шаг 2: Проверка конфигурационных файлов...');
    
    const files = [
      { name: '.replit', required: true },
      { name: 'replit.nix', required: true },
      { name: 'package.json', required: true },
      { name: 'index.js', required: true }
    ];
    
    files.forEach(file => {
      if (fs.existsSync(file.name)) {
        console.log(`✅ ${file.name} существует`);
      } else if (file.required) {
        console.log(`❌ ${file.name} отсутствует!`);
        process.exit(1);
      }
    });
    
    // Проверка зависимостей
    console.log('\n📦 Шаг 3: Проверка зависимостей...');
    try {
      execSync('npm list express', { stdio: 'pipe' });
      console.log('✅ Зависимости установлены');
    } catch {
      console.log('⚠️ Устанавливаю зависимости...');
      execSync('npm install', { stdio: 'inherit' });
    }
    
    // Проверка FFmpeg
    console.log('\n🎬 Шаг 4: Проверка FFmpeg...');
    try {
      const ffmpegVersion = execSync('ffmpeg -version | head -1').toString().trim();
      console.log(`✅ FFmpeg: ${ffmpegVersion}`);
    } catch {
      console.log('❌ FFmpeg не найден!');
      console.log('\n💡 Решение:');
      console.log('1. Убедитесь что в .replit есть "ffmpeg = \\"6.1\\""');
      console.log('2. Перезапустите Replit (Stop → Run)');
      console.log('3. FFmpeg установится автоматически');
    }
    
    // Проверка переменных окружения
    console.log('\n🔧 Шаг 5: Проверка переменных окружения...');
    const requiredEnvVars = ['PORT', 'MAX_VIDEO_SIZE', 'MAX_GIF_SIZE'];
    requiredEnvVars.forEach(varName => {
      if (process.env[varName]) {
        console.log(`✅ ${varName}=${process.env[varName]}`);
      } else {
        console.log(`⚠️ ${varName} не установлена (но может быть по умолчанию)`);
      }
    });
    
    if (!process.env.BOT_TOKEN) {
      console.log('\n⚠️ BOT_TOKEN не установлен!');
      console.log('💡 Для работы бота нужно:');
      console.log('1. Получить токен у @BotFather');
      console.log('2. Добавить в Replit Secrets: BOT_TOKEN=ваш_токен');
    } else {
      console.log('✅ BOT_TOKEN установлен');
    }
    
    console.log('\n' + '═'.repeat(50));
    console.log('🎉 УСТАНОВКА ЗАВЕРШЕНА!');
    console.log('═'.repeat(50));
    console.log('\n📋 Следующие шаги:');
    console.log('1. Нажмите "Run" для запуска бота');
    console.log('2. Проверьте веб-интерфейс: http://localhost:3000');
    console.log('3. Настройте вебхук Telegram');
    console.log('4. Отправьте боту видео или GIF!');
    console.log('\n✅ Бот готов к работе!');
    
  } catch (error) {
    console.error('❌ Ошибка установки:', error.message);
    console.log('\n🔧 Попробуйте вручную:');
    console.log('1. Убедитесь что все файлы на месте');
    console.log('2. Перезапустите Replit (Stop → Run)');
    console.log('3. Проверьте консоль на ошибки');
  }
}

setup();
