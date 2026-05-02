"""
Download service: wraps yt-dlp with ffmpeg support.
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


def _get_ffmpeg_location():
    """Auto-detect ffmpeg — checks common paths."""
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/nix/var/nix/profiles/default/bin/ffmpeg"]:
        if os.path.exists(path):
            return os.path.dirname(path)
    # Try PATH
    found = shutil.which("ffmpeg")
    if found:
        return os.path.dirname(found)
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
    ffmpeg_loc = _get_ffmpeg_location()
    has_ffmpeg = ffmpeg_loc is not None
    logger.info("ffmpeg found: %s at %s", has_ffmpeg, ffmpeg_loc)

    # Use merge format if ffmpeg available, else fallback to single-file
    if has_ffmpeg:
        fmt = QUALITY_FORMAT_MAP.get(quality, "bestvideo+bestaudio/best")
    else:
        # Fallback without ffmpeg - single file formats only
        fmt = {
            "4K":    "best[height<=2160]/best",
            "1080p": "best[height<=1080]/best",
            "720p":  "best[height<=720]/best",
            "480p":  "best[height<=480]/best",
            "best":  "best",
        }.get(quality, "best")

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
        ydl_opts["ffmpeg_location"] = ffmpeg_loc
        ydl_opts["merge_output_format"] = "mp4"

    # Add cookies if file exists
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
        logger.info("Download complete [id=%d] ffmpeg=%s", video_id, has_ffmpeg)

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
