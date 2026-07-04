"""
예약 시스템 SQLite DB.

1인샵 가정이라 디자이너 테이블은 없습니다. 매장 설정(영업시간, 휴무 등)은
shop_config 키-값 테이블에, 특정일 휴무는 closed_date 테이블에 저장합니다.
"""

import os
import sqlite3

DB_PATH = os.environ.get("BOOKING_DB", "booking.db")

# 매장 기본 설정 (관리자 화면에서 변경 가능)
DEFAULT_CONFIG = {
    "shop_name": "우리 미용실",
    "open_time": "10:00",
    "close_time": "20:00",
    "weekly_closed": "0",  # 정기 휴무 요일 (월=0 ... 일=6, 콤마 구분. 빈 문자열이면 없음)
    "slot_minutes": "30",  # 예약 시간 간격(분)
    "cancel_deadline_hours": "24",  # 이 시간 이내 취소는 '마감 후 취소'로 표시
}

# 최초 실행 시 넣어주는 예시 메뉴 (관리자 화면에서 수정)
SEED_SERVICES = [
    ("컷", "컷", 20000, "", 40),
    ("펌", "펌", 80000, "기장(어깨 아래) +10,000원", 120),
    ("염색", "염색", 70000, "기장/뿌리 상태에 따라 +10,000~20,000원", 90),
    ("클리닉", "클리닉", 50000, "", 60),
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS shop_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS closed_date (
    date TEXT PRIMARY KEY  -- 'YYYY-MM-DD' 지정 휴무일
);
CREATE TABLE IF NOT EXISTS service (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    category          TEXT NOT NULL,
    base_price        INTEGER NOT NULL,
    extra_charge_note TEXT NOT NULL DEFAULT '',  -- 추가금 조건 (가격 투명성: 예약 전에 고지)
    duration_min      INTEGER NOT NULL,
    active            INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS customer (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    provider     TEXT NOT NULL,  -- kakao/naver
    provider_uid TEXT NOT NULL,  -- 소셜 로그인 제공자의 고유 회원 ID
    nickname     TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    UNIQUE (provider, provider_uid)
);
CREATE TABLE IF NOT EXISTS reservation (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code          TEXT NOT NULL UNIQUE,  -- 고객에게 주는 예약번호
    service_id    INTEGER NOT NULL REFERENCES service(id),
    customer_name TEXT NOT NULL,
    phone         TEXT NOT NULL,         -- 숫자만 저장
    request_note  TEXT NOT NULL DEFAULT '',
    start_at      TEXT NOT NULL,         -- 'YYYY-MM-DDTHH:MM' (KST 나이브)
    end_at        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'confirmed',  -- confirmed/done/noshow/canceled
    canceled_late INTEGER NOT NULL DEFAULT 0,         -- 취소 마감 이후 취소 여부
    source        TEXT NOT NULL DEFAULT 'web',        -- web/chatbot/manual
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reservation_start ON reservation(start_at);
CREATE TABLE IF NOT EXISTS photo (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id INTEGER NOT NULL REFERENCES reservation(id),
    kind           TEXT NOT NULL,  -- reference(고객 희망 스타일) / front/side/back(시술 결과)
    filename       TEXT NOT NULL,  -- PHOTO_DIR 안의 파일명 (booking/photos.py)
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id INTEGER NOT NULL REFERENCES reservation(id),
    kind           TEXT NOT NULL,  -- confirm/day_before/same_day
    due_at         TEXT NOT NULL,  -- 'YYYY-MM-DDTHH:MM'
    sent_at        TEXT,
    status         TEXT NOT NULL DEFAULT 'pending'  -- pending/sent/canceled
);
"""


def get_conn() -> sqlite3.Connection:
    # isolation_level=None: 자동커밋 모드. 쓰기 구간은 engine.py에서
    # BEGIN IMMEDIATE로 직접 감싸 동시 예약 충돌을 막습니다.
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(_SCHEMA)
        # 기존 DB 마이그레이션: 소셜 로그인 고객과 예약 연결 컬럼
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(reservation)")]
        if "customer_id" not in columns:
            conn.execute(
                "ALTER TABLE reservation ADD COLUMN customer_id INTEGER"
                " REFERENCES customer(id)"
            )
        for key, value in DEFAULT_CONFIG.items():
            conn.execute(
                "INSERT OR IGNORE INTO shop_config (key, value) VALUES (?, ?)",
                (key, value),
            )
        if conn.execute("SELECT COUNT(*) FROM service").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO service (name, category, base_price, extra_charge_note,"
                " duration_min) VALUES (?, ?, ?, ?, ?)",
                SEED_SERVICES,
            )
    finally:
        conn.close()


def get_config(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM shop_config").fetchall()
    config = dict(DEFAULT_CONFIG)
    config.update({r["key"]: r["value"] for r in rows})
    return config


def set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO shop_config (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
