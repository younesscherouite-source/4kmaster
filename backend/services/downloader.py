"""
Download service: wraps yt-dlp with smart format selection.
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
    "4K":    "bestvideo[height<=2160]+bestaudio/bestvideo[height<=2160]/best[height<=2160]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/bestvideo[height<=1080]/best[height<=1080]/best",
    "720p":  "bestvideo[height<=720]+bestaudio/bestvideo[height<=720]/best[height<=720]/best",
    "480p":  "bestvideo[height<=480]+bestaudio/bestvideo[height<=480]/best[height<=480]/best",
    "best":  "bestvideo+bestaudio/bestvideo/best",
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
    for p in ["/usr/bin", "/usr/local/bin", "/nix/var/nix/profiles/default/bin"]:
        if os.path.exists(os.path.join(p, "ffmpeg")):
            return p
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


def _build_ydl_opts(fmt: str, video_id: int, ffmpeg_dir):
    opts = {
        "format": fmt,
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "progress_hooks": [_make_progress_hook(video_id)],
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "abort_on_error": False,
        # مهم جداً — يجرب player clients مختلفة
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "web_creator", "android"],
            }
        },
    }
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir
        opts["merge_output_format"] = "mp4"

    cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt")
    if os.path.exists(cookies_path):
        opts["cookiefile"] = cookies_path

    return opts


def _run_download(video_id: int, url: str, quality: str):
    ffmpeg_dir = _get_ffmpeg_dir()
    fmt = QUALITY_FORMAT_MAP.get(quality, "bestvideo+bestaudio/best")

    try:
        ydl_opts = _build_ydl_opts(fmt, video_id, ffmpeg_dir)

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
