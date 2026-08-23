"""
Flovo Render Worker
====================
سيرفر بسيط بيستقبل طلب تركيب فيديو (خلفية + صوت + تعليقات نصية)
وينفّذه بـFFmpeg، وبعدين يبعت النتيجة النهائية لسيرفرنا (Contabo) عن طريق Webhook.

الطلب المتوقَّع (POST /render):
{
  "job_id": "معرّف فريد للمهمة",
  "background_video_url": "رابط فيديو الخلفية",
  "audio_url": "رابط ملف الصوت",
  "captions": [{"text": "...", "start": 0.5, "end": 2.1}, ...],
  "webhook_url": "رابط سيرفرنا اللي هيستقبل النتيجة النهائية"
}
"""

import os
import subprocess
import threading
import uuid
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

WORK_DIR = "/tmp/render_jobs"
os.makedirs(WORK_DIR, exist_ok=True)

SECRET_KEY = os.environ.get("RENDER_WORKER_SECRET", "flovo-worker-secret-change-me")


def download_file(url, dest_path):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


def seconds_to_srt_time(t):
    hours = int(t // 3600)
    minutes = int((t % 3600) // 60)
    secs = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt(captions, srt_path):
    lines = []
    for i, c in enumerate(captions, 1):
        lines.append(str(i))
        lines.append(f"{seconds_to_srt_time(c['start'])} --> {seconds_to_srt_time(c['end'])}")
        lines.append(c["text"])
        lines.append("")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def get_audio_duration(audio_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrapers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def process_job(job_id, background_video_url, audio_url, captions, webhook_url):
    job_dir = os.path.join(WORK_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    bg_path = os.path.join(job_dir, "bg.mp4")
    audio_path = os.path.join(job_dir, "audio.mp3")
    srt_path = os.path.join(job_dir, "captions.srt")
    output_path = os.path.join(job_dir, "output.mp4")

    try:
        download_file(background_video_url, bg_path)
        download_file(audio_url, audio_path)

        audio_duration = get_audio_duration(audio_path)

        if captions:
            build_srt(captions, srt_path)
            subtitle_filter = (
                f"subtitles={srt_path}:force_style="
                "'FontName=Arial,FontSize=16,PrimaryColour=&HFFFFFF&,"
                "OutlineColour=&H000000&,BorderStyle=1,Outline=2,Alignment=2,MarginV=120'"
            )
            vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{subtitle_filter}"
        else:
            vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", bg_path,
            "-i", audio_path,
            "-t", str(audio_duration),
            "-vf", vf,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

        if result.returncode != 0 or not os.path.exists(output_path):
            _send_webhook(webhook_url, {
                "job_id": job_id, "ok": False,
                "error": result.stderr[-1000:] if result.stderr else "فشل الترميز"
            })
            return

        with open(output_path, "rb") as f:
            files = {"video": (f"{job_id}.mp4", f, "video/mp4")}
            data = {"job_id": job_id, "ok": "true", "secret": SECRET_KEY}
            requests.post(webhook_url, files=files, data=data, timeout=120)

    except Exception as e:
        _send_webhook(webhook_url, {"job_id": job_id, "ok": False, "error": str(e)})
    finally:
        try:
            for fp in [bg_path, audio_path, srt_path, output_path]:
                if os.path.exists(fp):
                    os.remove(fp)
            os.rmdir(job_dir)
        except Exception:
            pass


def _send_webhook(webhook_url, payload):
    try:
        payload["secret"] = SECRET_KEY
        requests.post(webhook_url, json=payload, timeout=30)
    except Exception:
        pass


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "alive"})


@app.route("/render", methods=["POST"])
def render():
    data = request.get_json(force=True)

    if data.get("secret") != SECRET_KEY:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    job_id = data.get("job_id") or str(uuid.uuid4())
    background_video_url = data.get("background_video_url")
    audio_url = data.get("audio_url")
    captions = data.get("captions", [])
    webhook_url = data.get("webhook_url")

    if not background_video_url or not audio_url or not webhook_url:
        return jsonify({"ok": False, "error": "بيانات ناقصة"}), 400

    thread = threading.Thread(
        target=process_job,
        args=(job_id, background_video_url, audio_url, captions, webhook_url),
    )
    thread.start()

    return jsonify({"ok": True, "job_id": job_id, "status": "accepted"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
