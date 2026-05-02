"""
Download service - uses best available format from server.
Note: YouTube restricts cloud servers to 360p max.
"""

import os
import shutil
import threading
import logging
import yt_dlp

from backend.models.video import update_video

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

QUALITY_FORMAT_MAP = {
    "4K":    "18/best",
    "1080p": "18/best",
    "720p":  "18/best",
    "480p":  "18/best",
    "best":  "18/best",
}


def _get_ffmpeg_dir():
    found = shutil.which("ffmpeg")
    if found:
        return os.path.dirname(found)
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return os.path.dirname(path)
    except Exception:
        pass
    return None


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
    ffmpeg_dir = _get_ffmpeg_dir()
    fmt = QUALITY_FORMAT_MAP.get(quality, "18/best")

    ydl_opts = {
        "format": fmt,
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "progress_hooks": [_make_progress_hook(video_id)],
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "abort_on_error": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "web_creator", "android"],
            }
        },
    }

    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir
        ydl_opts["merge_output_format"] = "mp4"

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
        logger.info("Done [id=%d]", video_id)

    except Exception as exc:
        msg = str(exc)[:300]
        update_video(video_id, status="error", error_msg=msg)
        logger.error("Failed [id=%d]: %s", video_id, msg)


def start_download(video_id: int, url: str, quality: str):
    t = threading.Thread(
        target=_run_download,
        args=(video_id, url, quality),
        daemon=True,
        name=f"download-{video_id}",
    )
    t.start()
