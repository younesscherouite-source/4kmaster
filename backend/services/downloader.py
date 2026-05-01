"""
Download service: wraps yt-dlp to download videos asynchronously.
Progress is tracked in the DB so the frontend can poll for updates.
"""

import os
import threading
import logging
import yt_dlp

from backend.models.video import update_video

logger = logging.getLogger(__name__)

# Where finished videos are saved
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Map UI quality labels to yt-dlp format strings
QUALITY_FORMAT_MAP = {
    "4K":    "best[height<=2160]/best",
    "1080p": "best[height<=1080]/best",
    "720p":  "best[height<=720]/best",
    "480p":  "best[height<=480]/best",
    "best":  "best",
}


def _make_progress_hook(video_id: int):
    """
    Returns a yt-dlp progress hook that writes % and file size to the DB.
    Called by yt-dlp several times per second during download.
    """
    def hook(d: dict):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            pct = int(downloaded / total * 100) if total else 0
            size_mb = f"{total / 1_048_576:.1f} MB" if total else ""
            update_video(video_id, progress=pct, file_size=size_mb)

        elif d["status"] == "finished":
            update_video(video_id, progress=99)  # merging phase

    return hook

def _run_download(video_id: int, url: str, quality: str):
    fmt = QUALITY_FORMAT_MAP.get(quality, "best")
    
    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "progress_hooks": [_make_progress_hook(video_id)],
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "abort_on_error": False,
        "cookiefile": os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt"),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown")[:120]
            update_video(video_id, title=title)
            ydl.download([url])

        # احفظ اسم الملف في DB
        filename = ydl_opts["outtmpl"] % {"title": title, "ext": "mp4"}
        update_video(video_id, status="done", progress=100, filename=filename)
        
    except Exception as exc:
        update_video(video_id, status="error", error_msg=str(exc)[:300])


def start_download(video_id: int, url: str, quality: str):
    """
    Kick off a download in a daemon background thread so Flask stays responsive.
    """
    t = threading.Thread(
        target=_run_download,
        args=(video_id, url, quality),
        daemon=True,
        name=f"download-{video_id}",
    )
    t.start()
    logger.info("Started download thread [id=%d] quality=%s", video_id, quality)
