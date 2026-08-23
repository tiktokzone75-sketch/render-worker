"""
Flovo Render Job — نسخة كاملة مع بطاقة Reddit
=================================================
"""

import os
import subprocess
import json
import requests
from intro_card import generate_intro_card

WORK_DIR = "/tmp/render_job"
os.makedirs(WORK_DIR, exist_ok=True)


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


def download_file(url, dest_path):
    r = requests.get(url, stream=True, timeout=90)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


def get_audio_duration(audio_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def main():
    job_id = os.environ.get("JOB_ID", "unknown")
    background_video_url = os.environ["BACKGROUND_VIDEO_URL"]
    audio_url = os.environ["AUDIO_URL"]
    webhook_url = os.environ["WEBHOOK_URL"]
    secret = os.environ.get("RENDER_WORKER_SECRET", "")
    captions_raw = os.environ.get("CAPTIONS_JSON", "[]")
    intro_card_raw = os.environ.get("INTRO_CARD_JSON", "null")

    try:
        captions = json.loads(captions_raw) if captions_raw and captions_raw != "null" else []
    except Exception:
        captions = []

    try:
        intro_card_config = json.loads(intro_card_raw) if intro_card_raw and intro_card_raw != "null" else None
    except Exception:
        intro_card_config = None

    bg_path = os.path.join(WORK_DIR, "bg.mp4")
    audio_path = os.path.join(WORK_DIR, "audio.mp3")
    srt_path = os.path.join(WORK_DIR, "captions.srt")
    card_path = os.path.join(WORK_DIR, "card.png")
    output_path = os.path.join(WORK_DIR, "output.mp4")

    try:
        print(f"[{job_id}] جاري تحميل فيديو الخلفية...")
        download_file(background_video_url, bg_path)

        print(f"[{job_id}] جاري تحميل الصوت...")
        download_file(audio_url, audio_path)

        audio_duration = get_audio_duration(audio_path)
        print(f"[{job_id}] مدة الصوت: {audio_duration} ثانية")

        has_card = bool(intro_card_config and intro_card_config.get("enabled"))
        if has_card:
            print(f"[{job_id}] جاري رسم بطاقة Reddit...")
            generate_intro_card(intro_card_config, card_path)

        filter_parts = []
        filter_parts.append("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg]")

        if captions:
            build_srt(captions, srt_path)
            subtitle_filter = (
                f"subtitles={srt_path}:force_style="
                "'FontName=Arial,FontSize=16,PrimaryColour=&HFFFFFF&,"
                "OutlineColour=&H000000&,BorderStyle=1,Outline=2,Alignment=2,MarginV=120'"
            )
            filter_parts[-1] = filter_parts[-1].replace("[bg]", f",{subtitle_filter}[bg]")

        inputs = ["-stream_loop", "-1", "-i", bg_path, "-i", audio_path]

        if has_card:
            inputs += ["-i", card_path]
            filter_parts.append(
                f"[bg][2:v]overlay=0:0:enable='between(t,0,5)'[outv]"
            )
            final_video_label = "[outv]"
        else:
            final_video_label = "[bg]"

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-t", str(audio_duration),
            "-filter_complex", filter_complex,
            "-map", final_video_label, "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path,
        ]
        print(f"[{job_id}] جاري تركيب الفيديو بـFFmpeg...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1500)

        if result.returncode != 0 or not os.path.exists(output_path):
            print(f"[{job_id}] فشل الترميز: {result.stderr[-500:]}")
            requests.post(webhook_url, json={
                "job_id": job_id, "ok": False,
                "error": result.stderr[-1000:] if result.stderr else "فشل الترميز",
                "secret": secret,
            }, timeout=30)
            return

        print(f"[{job_id}] نجح الترميز، جاري إرسال النتيجة...")
        with open(output_path, "rb") as f:
            files = {"video": (f"{job_id}.mp4", f, "video/mp4")}
            data = {"job_id": job_id, "ok": "true", "secret": secret}
            r = requests.post(webhook_url, files=files, data=data, timeout=120)
            print(f"[{job_id}] رد السيرفر: {r.status_code}")

    except Exception as e:
        print(f"[{job_id}] خطأ: {e}")
        try:
            requests.post(webhook_url, json={"job_id": job_id, "ok": False, "error": str(e), "secret": secret}, timeout=30)
        except Exception:
            pass


if __name__ == "__main__":
    main()
