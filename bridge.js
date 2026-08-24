// الجسر بين Playwright ومحرك الرندر الأصلي (render_engine.js) - صفر تعديل
// على المحرك نفسه. التوقيت بيتحسب هنا طازة بنفس محرك التوقيت الأصلي
// (FlovoCaptionTiming بـWhisper) بدل ما يتم تمريره جاهز.

async function runRenderJob() {
  const statusEl = document.getElementById('status');
  const cfg = window.__FLOVO_CONFIG__;

  if (!cfg) {
    statusEl.textContent = 'ERROR: no config';
    return;
  }

  try {
    let captionTiming = { sentences: [], confidence: 0, usedFallback: true };

    if (cfg.sentences && cfg.sentences.length > 0) {
      statusEl.textContent = 'computing_timing';
      captionTiming = await window.FlovoCaptionTiming.extractTiming(
        cfg.sentences, cfg.config.audioUrl, !!cfg.isEnglish
      );
    }

    statusEl.textContent = 'rendering';

    const fullConfig = { ...cfg.config, captionTiming };

    const blob = await window.FlovoRenderEngine.render(fullConfig, (info) => {
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

setTimeout(runRenderJob, 300);
