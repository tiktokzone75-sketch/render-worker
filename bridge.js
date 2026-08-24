// الجسر بين Playwright ومحرك الرندر الأصلي (render_engine.js) - صفر تعديل
// على المحرك نفسه. الإعدادات بتوصله عن طريق window.__FLOVO_CONFIG__ اللي
// Playwright بيحقنها قبل التحميل.

async function runRenderJob() {
  const statusEl = document.getElementById('status');
  const cfg = window.__FLOVO_CONFIG__;

  if (!cfg) {
    statusEl.textContent = 'ERROR: no config';
    return;
  }

  try {
    statusEl.textContent = 'rendering';

    const blob = await window.FlovoRenderEngine.render(cfg.config, (info) => {
      statusEl.textContent = 'progress:' + (info.progress || 0);
    });

    statusEl.textContent = 'uploading';

    const form = new FormData();
    form.append('video', blob, cfg.jobId + '.mp4');
    form.append('job_id', cfg.jobId);
    form.append('ok', 'true');
    form.append('secret', cfg.secret);

    const res = await fetch(cfg.webhookUrl, { method: 'POST', body: form });

    statusEl.textContent = res.ok ? 'DONE' : 'UPLOAD_FAILED:' + res.status;
  } catch (err) {
    statusEl.textContent = 'FAILED:' + (err && err.message ? err.message : String(err));

    try {
      await fetch(cfg.webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: cfg.jobId, ok: false,
          error: err && err.message ? err.message : String(err),
          secret: cfg.secret,
        }),
      });
    } catch (e) {}
  }
}

// بننتظر لحظة عشان نتأكد إن window.__FLOVO_CONFIG__ اتحقن فعلاً قبل ما نبدأ
setTimeout(runRenderJob, 300);
