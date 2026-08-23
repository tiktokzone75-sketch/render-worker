import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition, getAudioDurationInSeconds} from '@remotion/renderer';
import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const jobId = process.env.JOB_ID || 'unknown';
const backgroundVideoUrl = process.env.BACKGROUND_VIDEO_URL;
const audioUrl = process.env.AUDIO_URL;
const webhookUrl = process.env.WEBHOOK_URL;
const secret = process.env.RENDER_WORKER_SECRET || '';
const captionsJson = process.env.CAPTIONS_JSON || '[]';
const introCardJson = process.env.INTRO_CARD_JSON || 'null';

let captions = [];
try {
  captions = JSON.parse(captionsJson) || [];
} catch {}

let introCard = null;
try {
  const parsed = JSON.parse(introCardJson);
  if (parsed && parsed !== null) {
    introCard = {
      enabled: !!parsed.enabled,
      theme: parsed.theme || 'light',
      isRTL: !!parsed.is_rtl,
      avatarUrl: parsed.avatar_url || '',
      username: parsed.username || '',
      postText: parsed.post_text || '',
    };
  }
} catch {}

async function sendWebhookJson(payload) {
  try {
    await fetch(webhookUrl, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...payload, secret}),
    });
  } catch (e) {
    console.error('فشل إرسال webhook:', e);
  }
}

async function main() {
  const outputDir = '/tmp/render_output';
  fs.mkdirSync(outputDir, {recursive: true});
  const outputPath = path.join(outputDir, `${jobId}.mp4`);

  try {
    console.log(`[${jobId}] جاري حساب مدة الصوت...`);
    const audioDurationSec = await getAudioDurationInSeconds(audioUrl);
    console.log(`[${jobId}] مدة الصوت: ${audioDurationSec} ثانية`);

    const fps = 30;
    const durationInFrames = Math.ceil(audioDurationSec * fps);

    console.log(`[${jobId}] جاري تجهيز المشروع (Bundling)...`);
    const bundleLocation = await bundle({
      entryPoint: path.join(__dirname, 'src', 'index.ts'),
    });

    const inputProps = {
      backgroundVideoUrl,
      audioUrl,
      captions,
      introCard,
    };

    console.log(`[${jobId}] جاري اختيار القالب...`);
    const composition = await selectComposition({
      serveUrl: bundleLocation,
      id: 'RedditStory',
      inputProps,
    });

    console.log(`[${jobId}] جاري الترميز (Rendering)...`);
    await renderMedia({
      composition: {...composition, durationInFrames, fps},
      serveUrl: bundleLocation,
      codec: 'h264',
      outputLocation: outputPath,
      inputProps,
      onProgress: ({progress}) => {
        if (Math.round(progress * 100) % 10 === 0) {
          console.log(`[${jobId}] التقدّم: ${Math.round(progress * 100)}%`);
        }
      },
    });

    console.log(`[${jobId}] نجح الترميز، جاري الإرسال...`);
    const videoBuffer = fs.readFileSync(outputPath);

    const FormData = (await import('form-data')).default;
    const form = new FormData();
    form.append('video', videoBuffer, {filename: `${jobId}.mp4`, contentType: 'video/mp4'});
    form.append('job_id', jobId);
    form.append('ok', 'true');
    form.append('secret', secret);

    const res = await fetch(webhookUrl, {method: 'POST', body: form});
    console.log(`[${jobId}] رد السيرفر: ${res.status}`);
  } catch (err) {
    console.error(`[${jobId}] خطأ:`, err);
    await sendWebhookJson({job_id: jobId, ok: false, error: String(err.message || err)});
  }
}

main();
