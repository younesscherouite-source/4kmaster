"""
REST API routes
"""

import re
import logging
import os
import yt_dlp
from flask import Blueprint, request, jsonify, send_from_directory

from backend.models.video import create_video, get_all_videos, get_video_by_id
from backend.services.downloader import start_download, QUALITY_FORMAT_MAP, DOWNLOAD_DIR

logger = logging.getLogger(__name__)
api = Blueprint("api", __name__, url_prefix="/api")

VALID_QUALITIES = list(QUALITY_FORMAT_MAP.keys())
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


@api.route("/formats", methods=["POST"])
def list_formats():
    """Debug: list available formats for a URL"""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL required"}), 400

    cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {
            "youtube": {"player_client": ["ios", "web_creator", "android"]}
        },
    }
    if os.path.exists(cookies_path):
        ydl_opts["cookiefile"] = cookies_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [
                {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "height": f.get("height"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                    "filesize": f.get("filesize"),
                }
                for f in info.get("formats", [])
            ]
            return jsonify({"title": info.get("title"), "formats": formats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    quality = (data.get("quality") or "1080p").strip()

    if not url:
        return jsonify({"error": "URL is required."}), 400
    if not URL_RE.match(url):
        return jsonify({"error": "Please enter a valid URL starting with http:// or https://"}), 400
    if quality not in VALID_QUALITIES:
        return jsonify({"error": f"Quality must be one of: {', '.join(VALID_QUALITIES)}"}), 400

    video_id = create_video(url, quality)
    start_download(video_id, url, quality)
    return jsonify({"id": video_id, "message": "Download started!"}), 202


@api.route("/videos", methods=["GET"])
def list_videos():
    return jsonify(get_all_videos()), 200


@api.route("/videos/<int:video_id>", methods=["GET"])
def get_video(video_id: int):
    video = get_video_by_id(video_id)
    if not video:
        return jsonify({"error": "Not found"}), 404
    return jsonify(video), 200


@api.route("/download-file/<path:filename>")
def download_file(filename):
    return send_from_directory(os.path.abspath(DOWNLOAD_DIR), filename, as_attachment=True)
