"""
Flask application factory.
Run with:  python app.py
"""

import logging
from flask import Flask, send_from_directory
from backend.database.db import init_db
from backend.routes.api import api
import os

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__, static_folder="frontend", static_url_path="")

    # Initialise database (creates file + table if absent)
    with app.app_context():
        init_db()

    # Register API blueprint
    app.register_blueprint(api)

    # Serve frontend SPA from /
    @app.route("/")
    def index():
        return send_from_directory("frontend", "index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    logger.info("🚀  4K Video Downloader running → http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
