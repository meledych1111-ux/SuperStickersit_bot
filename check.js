#!/usr/bin/env node

console.log(`
╔══════════════════════════════════════════╗
║     🔍 ПРОВЕРКА СИСТЕМЫ БОТА           ║
╚══════════════════════════════════════════╝
`);

const { execSync, exec } = require('child_process');
const fs = require('fs');
const path = require('path');

async function checkSystem() {
  const checks = [];
  
  // 1. Проверка Node.js
  try {
    const nodeVersion = process.version;
    const nodeMajor = parseInt(nodeVersion.slice(1).split('.')[0]);
    checks.push({
      name: 'Node.js',
      status: nodeMajor >= 20 ? '✅' : '⚠️',
      message: `${nodeVersion} ${nodeMajor >= 20 ? '(>=20 OK)' : '(требуется 20+)'}`
    });
  } catch (e) {
    checks.push({ name: 'Node.js', status: '❌', message: e.message });
  }
  
  // 2. Проверка FFmpeg
  try {
    const ffmpegVersion = execSync('ffmpeg -version 2>&1 | head -1').toString().trim();
    checks.push({
      name: 'FFmpeg',
      status: '✅',
      message: ffmpegVersion.substring(0, 50)
    });
  } catch (e) {
    checks.push({ name: 'FFmpeg', status: '❌', message: 'Не установлен' });
  }
  
  // 3. Проверка памяти
  const memory = process.memoryUsage();
  const memoryMB = Math.round(memory.heapUsed / 1024 / 1024);
  checks.push({
    name: 'Память',
    status: memoryMB < 400 ? '✅' : '⚠️',
    message: `${memoryMB}MB/512MB`
  });
  
  // 4. Проверка файлов
  const requiredFiles = ['.replit', 'replit.nix', 'package.json', 'index.js'];
  requiredFiles.forEach(file => {
    const exists = fs.existsSync(file);
    checks.push({
      name: `Файл ${file}`,
      status: exists ? '✅' : '❌',
      message: exists ? 'Существует' : 'Отсутствует'
    });
  });
  
  // 5. Проверка зависимостей
  try {
    const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
    const deps = Object.keys(packageJson.dependencies || {});
    checks.push({
      name: 'Зависимости',
      status: deps.length >= 3 ? '✅' : '⚠️',
      message: `${deps.length} пакетов: ${deps.join(', ')}`
    });
  } catch (e) {
    checks.push({ name: 'Зависимости', status: '❌', message: e.message });
  }
  
  // 6. Проверка переменных окружения
  const envVars = ['BOT_TOKEN', 'PORT', 'MAX_VIDEO_SIZE'];
  envVars.forEach(varName => {
    const value = process.env[varName];
    checks.push({
      name: `Переменная ${varName}`,
      status: value ? '✅' : varName === 'BOT_TOKEN' ? '⚠️' : '✅',
      message: value ? `Установлена (${varName === 'BOT_TOKEN' ? 'скрыто' : value.substring(0, 20)})` : 'Не установлена'
    });
  });
  
  // 7. Проверка порта
  try {
    execSync(`timeout 1 curl -s http://localhost:${process.env.PORT || 3000} > /dev/null`);
    checks.push({
      name: 'Порт сервера',
      status: '✅',
      message: `Порт ${process.env.PORT || 3000} открыт`
    });
  } catch (e) {
    checks.push({
      name: 'Порт сервера',
      status: '❌',
      message: `Порт ${process.env.PORT || 3000} не отвечает`
    });
  }
  
  // Вывод результатов
  console.log('\n📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ:\n');
  console.log('┌' + '─'.repeat(40) + '┐');
  checks.forEach(check => {
    const name = check.name.padEnd(25);
    const status = check.status.padEnd(3);
    console.log(`│ ${status} ${name} │ ${check.message}`);
  });
  console.log('└' + '─'.repeat(40) + '┘');
  
  // Сводка
  const total = checks.length;
  const passed = checks.filter(c => c.status === '✅').length;
  const warnings = checks.filter(c => c.status === '⚠️').length;
  const failed = checks.filter(c => c.status === '❌').length;
  
  console.log(`\n📈 СВОДКА: ${passed}/${total} ✅, ${warnings} ⚠️, ${failed} ❌`);
  
  if (failed > 0) {
    console.log('\n❌ КРИТИЧЕСКИЕ ОШИБКИ:');
    checks.filter(c => c.status === '❌').forEach(check => {
      console.log(`• ${check.name}: ${check.message}`);
    });
  }
  
  if (warnings > 0) {
    console.log('\n⚠️ ПРЕДУПРЕЖДЕНИЯ:');
    checks.filter(c => c.status === '⚠️').forEach(check => {
      console.log(`• ${check.name}: ${check.message}`);
    });
  }
  
  if (failed === 0 && warnings === 0) {
    console.log('\n🎉 Все проверки пройдены! Бот готов к работе!');
  }
}

checkSystem();
