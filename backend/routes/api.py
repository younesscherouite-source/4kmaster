"""
REST API routes:
  POST /api/download         — enqueue a new download
  GET  /api/videos           — list all downloads
  GET  /api/videos/<id>      — poll a single download for progress
"""
import re
import logging
import os
from flask import Blueprint, request, jsonify, send_from_directory

from backend.models.video import create_video, get_all_videos, get_video_by_id
from backend.services.downloader import start_download, QUALITY_FORMAT_MAP, DOWNLOAD_DIR

logger = logging.getLogger(__name__)
api = Blueprint("api", __name__, url_prefix="/api")

VALID_QUALITIES = list(QUALITY_FORMAT_MAP.keys())
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


@api.route("/download-file/<path:filename>")
def download_file(filename):
    return send_from_directory(
        os.path.abspath(DOWNLOAD_DIR),
        filename,
        as_attachment=True
    )

# ... باقي الـ routes


@api.route("/download", methods=["POST"])
def download():
    """
    Body JSON: { "url": "...", "quality": "1080p" }
    Returns:   { "id": 42, "message": "..." }
    """
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    quality = (data.get("quality") or "1080p").strip()

    # --- Validation ---
    if not url:
        return jsonify({"error": "URL is required."}), 400

    if not URL_RE.match(url):
        return jsonify({"error": "Please enter a valid URL starting with http:// or https://"}), 400

    if quality not in VALID_QUALITIES:
        return jsonify({"error": f"Quality must be one of: {', '.join(VALID_QUALITIES)}"}), 400

    # --- Create DB record & start background thread ---
    video_id = create_video(url, quality)
    start_download(video_id, url, quality)

    logger.info("Enqueued download id=%d url=%s quality=%s", video_id, url, quality)
    return jsonify({"id": video_id, "message": "Download started!"}), 202


@api.route("/videos", methods=["GET"])
def list_videos():
    """Return all download records, newest first."""
    videos = get_all_videos()
    return jsonify(videos), 200


@api.route("/videos/<int:video_id>", methods=["GET"])
def get_video(video_id: int):
    """Poll a single download for live progress/status."""
    video = get_video_by_id(video_id)
    if not video:
        return jsonify({"error": "Not found"}), 404
    return jsonify(video), 200
