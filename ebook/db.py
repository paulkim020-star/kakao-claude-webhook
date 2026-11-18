"""SQLite 저장소와 아카이브 폴더 경로.

데이터 폴더(EBOOK_DATA_DIR, 기본 ./ebook_data) 구조:
  library.db                      계정/책 목록
  secret.key                      로그인 쿠키 서명 키 (최초 1회 생성)
  archive/<user_id>/<book_id>/    original.<pdf|docx|hwpx>(내지), cover_original.*(별도 표지),
                                  cover.png, book.epub, meta.json
"""

import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    orig_name TEXT NOT NULL,
    pages INTEGER NOT NULL DEFAULT 0,
    file_size INTEGER NOT NULL DEFAULT 0,
    has_cover INTEGER NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL DEFAULT 'pdf',     -- 내지 형식: pdf / docx / hwpx
    cover_source TEXT NOT NULL DEFAULT 'page1',  -- page1 / image / pdf / none
    status TEXT NOT NULL DEFAULT 'converting',  -- converting / ready / failed
    error TEXT NOT NULL DEFAULT '',
    meta_json TEXT NOT NULL DEFAULT '{}',
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_books_user ON books(user_id);
CREATE TABLE IF NOT EXISTS progress (          -- 리더에서 읽던 위치 (계정별, 책별)
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chapter INTEGER NOT NULL DEFAULT 0,
    ratio REAL NOT NULL DEFAULT 0,             -- 그 장 안에서 스크롤한 비율 0~1
    percent REAL NOT NULL DEFAULT 0,           -- 책 전체 진행률 0~100
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, book_id)
);
CREATE TABLE IF NOT EXISTS notes (             -- 리더의 책갈피 / 밑줄(+메모)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,                        -- highlight / bookmark
    chapter INTEGER NOT NULL,
    start_off INTEGER NOT NULL DEFAULT 0,      -- highlight: 장 본문 글자 위치 [start, end)
    end_off INTEGER NOT NULL DEFAULT 0,
    text TEXT NOT NULL DEFAULT '',             -- highlight: 고른 글 / bookmark: 그 자리의 글 일부
    note TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT 'yellow',
    ratio REAL NOT NULL DEFAULT 0,             -- bookmark: 장 안에서의 위치 0~1
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notes_book ON notes(user_id, book_id);
"""


def data_dir() -> Path:
    path = Path(os.environ.get("EBOOK_DATA_DIR", "ebook_data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


# 이전 버전에서 만든 DB에 새 칸을 보태는 목록 (칸 이름, ALTER 문)
MIGRATIONS = [
    ("source_type", "ALTER TABLE books ADD COLUMN source_type TEXT NOT NULL DEFAULT 'pdf'"),
    ("cover_source", "ALTER TABLE books ADD COLUMN cover_source TEXT NOT NULL DEFAULT 'page1'"),
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(data_dir() / "library.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    have = {row["name"] for row in conn.execute("PRAGMA table_info(books)")}
    for column, ddl in MIGRATIONS:
        if column not in have:
            conn.execute(ddl)
    return conn


def book_dir(user_id: int, book_id: int) -> Path:
    path = data_dir() / "archive" / str(user_id) / str(book_id)
    path.mkdir(parents=True, exist_ok=True)
    return path
