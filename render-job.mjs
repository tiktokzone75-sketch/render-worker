import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';
import http from 'http';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const jobId = process.env.JOB_ID || 'unknown';
const backgroundVideoUrl = process.env.BACKGROUND_VIDEO_URL;
const audioUrl = process.env.AUDIO_URL;
const webhookUrl = process.env.WEBHOOK_URL;
const secret = process.env.RENDER_WORKER_SECRET || '';
const captionsJson = process.env.CAPTIONS_JSON || '[]';
const introCardJson = process.env.INTRO_CARD_JSON || 'null';

let captionTiming = { sentences: [], confidence: 0, usedFallback: true };
try {
  const captions = JSON.parse(captionsJson) || [];
  captionTiming = { sentences: captions, confidence: 1, usedFallback: false };
} catch {}

let introCard = { enabled: false };
try {
  const parsed = JSON.parse(introCardJson);
  if (parsed && parsed.enabled) {
    introCard = {
      enabled: true,
      theme: parsed.theme || 'light',
      avatarImageUrl: parsed.avatar_url || null,
      username: parsed.username || '',
      postText: parsed.post_text || '',
    };
  }
} catch {}

const config = {
  backgroundVideoUrl,
  audioUrl,
  captionTiming,
  captionStyle: 'classic',
  isEnglish: false,
  introCard,
};

// سيرفر محلي بسيط بيقدّم الملفات (render.html, bridge.js) - عشان
// المتصفح المخفي يقدر يفتحها كصفحة ويب عادية، مش ملف محلي مباشر
function startLocalServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      let filePath = req.url === '/' ? '/render.html' : req.url;
      filePath = path.join(__dirname, filePath.split('?')[0]);
      fs.readFile(filePath, (err, data) => {
        if (err) { res.writeHead(404); res.end(); return; }
        const ext = path.extname(filePath);
        const contentType = ext === '.js' ? 'application/javascript' : 'text/html';
        res.writeHead(200, { 'Content-Type': contentType });
        res.end(data);
      });
    });
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, port: server.address().port });
    });
  });
}

async function main() {
  console.log(`[${jobId}] جاري تشغيل سيرفر محلي...`);
  const { server, port } = await startLocalServer();

  console.log(`[${jobId}] جاري فتح متصفح مخفي...`);
  const browser = await chromium.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--autoplay-policy=no-user-gesture-required'],
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => console.log(`[${jobId}][browser] ${msg.text()}`));
  page.on('pageerror', (err) => console.log(`[${jobId}][pageerror] ${err}`));
  page.on('requestfailed', (req) => console.log(`[${jobId}][requestfailed] ${req.url()} -- ${req.failure()?.errorText}`));

  await page.addInitScript((injectedConfig) => {
    window.__FLOVO_CONFIG__ = injectedConfig;
  }, { config, jobId, webhookUrl, secret });

  console.log(`[${jobId}] جاري فتح الصفحة...`);
  await page.goto(`http://127.0.0.1:${port}/render.html`, { waitUntil: 'load', timeout: 30000 });

  console.log(`[${jobId}] جاري انتظار اكتمال الرندر (حتى ٢٠ دقيقة)...`);
  let finalStatus = null;
  for (let i = 0; i < 240; i++) {
    await page.waitForTimeout(5000);
    const status = await page.evaluate(() => document.getElementById('status')?.textContent || '');
    console.log(`[${jobId}] الحالة: ${status}`);
    if (status === 'DONE' || status.startsWith('FAILED') || status.startsWith('UPLOAD_FAILED') || status.startsWith('ERROR')) {
      finalStatus = status;
      break;
    }
  }

  console.log(`[${jobId}] النتيجة النهائية: ${finalStatus}`);

  await browser.close();
  server.close();

  if (!finalStatus || finalStatus !== 'DONE') {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(`[${jobId}] خطأ عام:`, err);
  process.exit(1);
});
