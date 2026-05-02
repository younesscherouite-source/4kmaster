"""
Download service: wraps yt-dlp with ffmpeg support.
Uses imageio-ffmpeg as fallback to get ffmpeg binary.
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
    "4K":    "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "best":  "bestvideo+bestaudio/best",
}

FALLBACK_FORMAT_MAP = {
    "4K":    "best[height<=2160]/best",
    "1080p": "best[height<=1080]/best",
    "720p":  "best[height<=720]/best",
    "480p":  "best[height<=480]/best",
    "best":  "best",
}


def _get_ffmpeg_dir():
    """Get ffmpeg directory - tries system, then imageio-ffmpeg pip package."""
    # 1. Check system PATH first
    found = shutil.which("ffmpeg")
    if found:
        logger.info("ffmpeg found in PATH: %s", found)
        return os.path.dirname(found)

    # 2. Try imageio-ffmpeg (installed via pip)
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            logger.info("ffmpeg found via imageio: %s", path)
            return os.path.dirname(path)
    except Exception as e:
        logger.warning("imageio-ffmpeg not available: %s", e)

    # 3. Common system paths
    for p in ["/usr/bin", "/usr/local/bin", "/nix/var/nix/profiles/default/bin"]:
        if os.path.exists(os.path.join(p, "ffmpeg")):
            logger.info("ffmpeg found at: %s", p)
            return p

    logger.warning("ffmpeg NOT found — using fallback formats")
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
    has_ffmpeg = ffmpeg_dir is not None

    fmt = QUALITY_FORMAT_MAP.get(quality, "bestvideo+bestaudio/best") if has_ffmpeg \
          else FALLBACK_FORMAT_MAP.get(quality, "best")

    ydl_opts = {
        "format": fmt,
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "progress_hooks": [_make_progress_hook(video_id)],
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "abort_on_error": False,
    }

    if has_ffmpeg:
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
        logger.info("Done [id=%d] ffmpeg=%s", video_id, has_ffmpeg)

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
