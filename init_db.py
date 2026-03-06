"""
init_db.py — Create all SQLite tables for ArtGallery.

Usage:
    python init_db.py
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gallery.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    description TEXT    DEFAULT '',
    mimetype    TEXT    NOT NULL DEFAULT 'image/jpeg',
    data        BLOB    NOT NULL,
    uploaded_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id   INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    text       TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS likes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    user_id  INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    UNIQUE(image_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_images_user    ON images(user_id);
CREATE INDEX IF NOT EXISTS idx_comments_image ON comments(image_id);
CREATE INDEX IF NOT EXISTS idx_likes_image    ON likes(image_id);
"""


def init():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.commit()
    con.close()
    print(f"✅ База данных создана: {DB}")


if __name__ == '__main__':
    init()