"""
Download service: wraps yt-dlp to download videos asynchronously.
"""

import os
import threading
import logging
import yt_dlp

from backend.models.video import update_video

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# bestvideo+bestaudio = جودة حقيقية مع ffmpeg
QUALITY_FORMAT_MAP = {
    "4K":    "bestvideo[height<=2160]+bestaudio/bestvideo[height<=2160]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/bestvideo[height<=1080]/best",
    "720p":  "bestvideo[height<=720]+bestaudio/bestvideo[height<=720]/best",
    "480p":  "bestvideo[height<=480]+bestaudio/bestvideo[height<=480]/best",
    "best":  "bestvideo+bestaudio/best",
}


def _make_progress_hook(video_id: int):
    def hook(d: dict):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            pct = int(downloaded / total * 100) if total else 0
            size_mb = f"{total / 1_048_576:.1f} MB" if total else ""
            update_video(video_id, progress=pct, file_size=size_mb)
        elif d["status"] == "finished":
            filepath = d.get("filename", "")
            filename = os.path.basename(filepath)
            update_video(video_id, progress=99, filename=filename)
    return hook


def _run_download(video_id: int, url: str, quality: str):
    # استعمل الـ format الصحيح حسب الجودة المختارة
    fmt = QUALITY_FORMAT_MAP.get(quality, "bestvideo+bestaudio/best")

    ydl_opts = {
        "format": fmt,                          # ← الجودة الحقيقية
        "merge_output_format": "mp4",           # ← دمج الفيديو والصوت
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "progress_hooks": [_make_progress_hook(video_id)],
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "abort_on_error": False,
        # ffmpeg path على Railway بعد nixpacks
        "ffmpeg_location": "/usr/bin/ffmpeg",
    }

    # زيد cookies إذا موجودة
    cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt")
    if os.path.exists(cookies_path):
        ydl_opts["cookiefile"] = cookies_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown")[:120]
            update_video(video_id, title=title)
            ydl.download([url])

        update_video(video_id, status="done", progress=100)
        logger.info("Download complete [id=%d]", video_id)

    except Exception as exc:
        msg = str(exc)[:300]
        update_video(video_id, status="error", error_msg=msg)
        logger.error("Download failed [id=%d]: %s", video_id, msg)


def start_download(video_id: int, url: str, quality: str):
    t = threading.Thread(
        target=_run_download,
        args=(video_id, url, quality),
        daemon=True,
        name=f"download-{video_id}",
    )
    t.start()
