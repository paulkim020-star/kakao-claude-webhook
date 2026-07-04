"""
시술 사진 저장/조회 헬퍼.

- reference: 고객이 예약 시 올리는 "원하는 스타일" 사진 (예약당 최대 3장)
- front/side/back: 원장이 시술 후 기록하는 결과 사진 (각 1장, 재업로드 시 교체)

파일은 PHOTO_DIR 폴더에 저장하고 DB(photo 테이블)에는 연결 정보만 둡니다.
고객 얼굴이 담기는 민감 정보이므로 정적 경로로 공개하지 않고, 반드시
본인 확인(web.py) 또는 관리자 인증(admin.py)을 거친 라우트로만 서빙합니다.
S3 등 외부 저장소로 옮길 때는 이 파일의 저장/삭제/경로 함수만 교체하면 됩니다.
"""

import os
import secrets
import sqlite3
from pathlib import Path

from booking.engine import now_kst, TIME_FMT

PHOTO_DIR = os.environ.get("PHOTO_DIR", "photos")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 8 * 1024 * 1024  # 8MB
MAX_REFERENCE_PHOTOS = 3
RESULT_KINDS = ("front", "side", "back")


class PhotoValidationError(ValueError):
    pass


def validate_upload(upload) -> tuple[str, bytes] | None:
    """UploadFile 검증. 파일이 비어 있으면 None, 문제 있으면 예외."""
    if not upload or not upload.filename:
        return None
    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise PhotoValidationError("사진은 jpg/png/webp 형식만 올릴 수 있어요.")
    data = upload.file.read()
    if not data:
        return None
    if len(data) > MAX_BYTES:
        raise PhotoValidationError("사진 용량은 8MB 이하로 올려주세요.")
    return ext, data


def save_photo(
    conn: sqlite3.Connection, reservation_id: int, kind: str, ext: str, data: bytes
) -> int:
    if kind == "reference":
        count = conn.execute(
            "SELECT COUNT(*) FROM photo WHERE reservation_id = ? AND kind = 'reference'",
            (reservation_id,),
        ).fetchone()[0]
        if count >= MAX_REFERENCE_PHOTOS:
            raise PhotoValidationError(
                f"원하는 스타일 사진은 최대 {MAX_REFERENCE_PHOTOS}장까지예요."
            )
    elif kind in RESULT_KINDS:
        # 결과 사진은 각도당 1장: 기존 것 교체
        for row in conn.execute(
            "SELECT id, filename FROM photo WHERE reservation_id = ? AND kind = ?",
            (reservation_id, kind),
        ).fetchall():
            delete_photo_file(row["filename"])
            conn.execute("DELETE FROM photo WHERE id = ?", (row["id"],))
    else:
        raise PhotoValidationError(f"알 수 없는 사진 종류: {kind}")

    filename = f"r{reservation_id}_{kind}_{secrets.token_hex(8)}{ext}"
    directory = Path(PHOTO_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(data)
    cur = conn.execute(
        "INSERT INTO photo (reservation_id, kind, filename, created_at)"
        " VALUES (?, ?, ?, ?)",
        (reservation_id, kind, filename, now_kst().strftime(TIME_FMT)),
    )
    return cur.lastrowid


def photo_file(filename: str) -> Path:
    return Path(PHOTO_DIR) / filename


def delete_photo_file(filename: str) -> None:
    path = photo_file(filename)
    if path.exists():
        path.unlink()


def get_photo(conn: sqlite3.Connection, photo_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM photo WHERE id = ?", (photo_id,)).fetchone()


def photos_for_reservation(
    conn: sqlite3.Connection, reservation_id: int
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM photo WHERE reservation_id = ? ORDER BY id",
        (reservation_id,),
    ).fetchall()
