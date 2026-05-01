"""
Database initialization and connection management.
"""

import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "videos.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
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
                filename    TEXT    DEFAULT '',
                error_msg   TEXT    DEFAULT '',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add filename column if it doesn't exist (for old DBs)
        try:
            conn.execute("ALTER TABLE videos ADD COLUMN filename TEXT DEFAULT ''")
        except Exception:
            pass
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()
