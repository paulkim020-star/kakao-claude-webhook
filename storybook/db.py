"""
동화책 생성기 SQLite DB.

책(storybook) 한 권과 그 페이지들(storybook_page)을 저장합니다.
페이지 이미지는 별도 정적 마운트 없이 템플릿에 바로 embed 할 수 있도록
data URL 문자열(base64)로 image 컬럼에 저장합니다.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.environ.get("STORYBOOK_DB", "storybook.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS storybook (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    topic      TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS storybook_page (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    page_no INTEGER NOT NULL,
    text    TEXT NOT NULL,          -- 한국어 이야기(한 페이지 분량)
    scene   TEXT NOT NULL,          -- 삽화용 영어 이미지 생성 프롬프트
    image   TEXT NOT NULL DEFAULT '',  -- data URL (base64)
    FOREIGN KEY (book_id) REFERENCES storybook(id) ON DELETE CASCADE
);
"""


def now_kst_str() -> str:
    """한국 시각(KST) 'YYYY-MM-DD HH:MM' 문자열."""
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(_SCHEMA)
    finally:
        conn.close()
