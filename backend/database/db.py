"""
Database initialization and connection management.
Uses SQLite for lightweight, zero-config storage.
"""

import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

# Database file path — stored in the backend/database directory
DB_PATH = os.path.join(os.path.dirname(__file__), "videos.db")


def get_connection():
    """Return a new SQLite connection with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Rows behave like dicts
    return conn


def init_db():
    """
    Create the videos table if it doesn't already exist.
    Called once at app startup.
    """
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT    NOT NULL,
                title       TEXT    DEFAULT 'Unknown',
                quality     TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'downloading',
                progress    INTEGER DEFAULT 0,
                file_size   TEXT    DEFAULT '',
                error_msg   TEXT    DEFAULT '',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()
