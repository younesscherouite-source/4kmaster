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
    """
    Blocking download — intended to run inside a background thread.
    Updates the DB record through its lifecycle.
    """
    fmt = QUALITY_FORMAT_MAP.get(quality, QUALITY_FORMAT_MAP["best"])

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
            # Extract info first to get the title
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown")[:120]  # truncate long titles
            update_video(video_id, title=title)

            # Now actually download
            ydl.download([url])

        update_video(video_id, status="done", progress=100)
        logger.info("Download complete [id=%d] %s", video_id, title)

    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc)[:300]
        update_video(video_id, status="error", error_msg=msg)
        logger.error("Download failed [id=%d]: %s", video_id, msg)

    except Exception as exc:  # noqa: BLE001
        msg = f"Unexpected error: {exc}"[:300]
        update_video(video_id, status="error", error_msg=msg)
        logger.exception("Unexpected download error [id=%d]", video_id)


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
