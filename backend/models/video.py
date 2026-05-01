"""
Video model: all database operations for the videos table.
"""

from backend.database.db import get_connection


def create_video(url: str, quality: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO videos (url, quality, status) VALUES (?, ?, 'downloading')",
            (url, quality),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_video(video_id: int, **kwargs):
    if not kwargs:
        return
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [video_id]
    conn = get_connection()
    try:
        conn.execute(f"UPDATE videos SET {cols} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_all_videos() -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM videos ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_video_by_id(video_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
