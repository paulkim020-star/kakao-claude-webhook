"""
예약 코어 로직: 가용 슬롯 계산, 예약 생성/변경/취소, 리마인드 예약.

시간은 모두 KST 나이브 datetime / 'YYYY-MM-DDTHH:MM' 문자열로 다룹니다.
동시 예약 충돌은 BEGIN IMMEDIATE 트랜잭션 안에서 가용 여부를 재확인하는
방식으로 막습니다 (SQLite는 쓰기 잠금이 DB 단위라 이것으로 충분).
"""

import secrets
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from booking.db import get_config

KST = ZoneInfo("Asia/Seoul")
TIME_FMT = "%Y-%m-%dT%H:%M"

# 리마인드 3단계: 확정 즉시 / 전날 19시 / 당일 9시 (노쇼 방어의 핵심)
DAY_BEFORE_HOUR = 19
SAME_DAY_HOUR = 9

# 예약번호에서 헷갈리는 문자(0/O, 1/I/L) 제외
_CODE_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


class SlotUnavailableError(Exception):
    """이미 예약됐거나 예약 불가능한 시간."""


def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None, second=0, microsecond=0)


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, TIME_FMT)


def generate_code() -> str:
    return "".join(secrets.choice(_CODE_CHARS) for _ in range(6))


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not (9 <= len(digits) <= 11):
        raise ValueError("전화번호 형식이 올바르지 않습니다.")
    return digits


def is_closed_day(conn: sqlite3.Connection, config: dict[str, str], date_str: str) -> bool:
    """정기 휴무 요일 또는 지정 휴무일 여부."""
    weekday = datetime.strptime(date_str, "%Y-%m-%d").weekday()
    closed_weekdays = {
        int(d) for d in config["weekly_closed"].split(",") if d.strip() != ""
    }
    if weekday in closed_weekdays:
        return True
    row = conn.execute(
        "SELECT 1 FROM closed_date WHERE date = ?", (date_str,)
    ).fetchone()
    return row is not None


def available_slots(
    conn: sqlite3.Connection,
    duration_min: int,
    date_str: str,
    now: datetime | None = None,
    exclude_reservation_id: int | None = None,
) -> list[str]:
    """해당 날짜에 예약 가능한 시작 시각('HH:MM') 목록.

    exclude_reservation_id: 예약 시간 변경 시 자기 자신과의 충돌을 무시하기 위함.
    """
    now = now or now_kst()
    config = get_config(conn)
    if is_closed_day(conn, config, date_str):
        return []

    open_dt = parse_dt(f"{date_str}T{config['open_time']}")
    close_dt = parse_dt(f"{date_str}T{config['close_time']}")
    step = timedelta(minutes=int(config["slot_minutes"]))
    duration = timedelta(minutes=duration_min)

    # 그날의 유효한 예약(confirmed)만 충돌 검사 대상
    query = (
        "SELECT id, start_at, end_at FROM reservation"
        " WHERE status = 'confirmed' AND start_at < ? AND end_at > ?"
    )
    params: list = [close_dt.strftime(TIME_FMT), open_dt.strftime(TIME_FMT)]
    if exclude_reservation_id is not None:
        query += " AND id != ?"
        params.append(exclude_reservation_id)
    existing = [
        (parse_dt(r["start_at"]), parse_dt(r["end_at"]))
        for r in conn.execute(query, params).fetchall()
    ]

    slots = []
    cursor = open_dt
    while cursor + duration <= close_dt:
        if cursor > now and not any(
            cursor < e_end and cursor + duration > e_start
            for e_start, e_end in existing
        ):
            slots.append(cursor.strftime("%H:%M"))
        cursor += step
    return slots


def _schedule_notifications(
    conn: sqlite3.Connection, reservation_id: int, start_dt: datetime, now: datetime
) -> None:
    """확정/전날/당일 리마인드를 예약. 이미 지난 시점의 리마인드는 만들지 않음."""
    due_list = [("confirm", now)]
    day_before = start_dt.replace(hour=DAY_BEFORE_HOUR, minute=0) - timedelta(days=1)
    same_day = start_dt.replace(hour=SAME_DAY_HOUR, minute=0)
    if day_before > now:
        due_list.append(("day_before", day_before))
    if now < same_day < start_dt:
        due_list.append(("same_day", same_day))
    conn.executemany(
        "INSERT INTO notification (reservation_id, kind, due_at) VALUES (?, ?, ?)",
        [(reservation_id, kind, due.strftime(TIME_FMT)) for kind, due in due_list],
    )


def _cancel_pending_notifications(conn: sqlite3.Connection, reservation_id: int) -> None:
    conn.execute(
        "UPDATE notification SET status = 'canceled'"
        " WHERE reservation_id = ? AND status = 'pending'",
        (reservation_id,),
    )


def create_reservation(
    conn: sqlite3.Connection,
    service_id: int,
    customer_name: str,
    phone: str,
    request_note: str,
    start_str: str,  # 'YYYY-MM-DDTHH:MM'
    source: str = "web",
    now: datetime | None = None,
) -> sqlite3.Row:
    now = now or now_kst()
    customer_name = customer_name.strip()
    if not customer_name:
        raise ValueError("이름을 입력해 주세요.")
    phone = normalize_phone(phone)
    start_dt = parse_dt(start_str)

    service = conn.execute(
        "SELECT * FROM service WHERE id = ? AND active = 1", (service_id,)
    ).fetchone()
    if service is None:
        raise ValueError("존재하지 않는 시술 메뉴입니다.")
    end_dt = start_dt + timedelta(minutes=service["duration_min"])

    conn.execute("BEGIN IMMEDIATE")
    try:
        # 트랜잭션(쓰기 잠금) 안에서 가용 여부를 재확인 → 동시 요청이 와도 한 건만 성공
        slots = available_slots(
            conn, service["duration_min"], start_dt.strftime("%Y-%m-%d"), now=now
        )
        if start_dt.strftime("%H:%M") not in slots:
            raise SlotUnavailableError("선택한 시간은 예약할 수 없습니다. 다른 시간을 선택해 주세요.")

        code = generate_code()
        while conn.execute(
            "SELECT 1 FROM reservation WHERE code = ?", (code,)
        ).fetchone():
            code = generate_code()

        cur = conn.execute(
            "INSERT INTO reservation (code, service_id, customer_name, phone,"
            " request_note, start_at, end_at, source, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                code,
                service_id,
                customer_name,
                phone,
                request_note.strip(),
                start_dt.strftime(TIME_FMT),
                end_dt.strftime(TIME_FMT),
                source,
                now.strftime(TIME_FMT),
            ),
        )
        _schedule_notifications(conn, cur.lastrowid, start_dt, now)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return find_reservation(conn, code, phone)


def find_reservation(
    conn: sqlite3.Connection, code: str, phone: str
) -> sqlite3.Row | None:
    """예약번호 + 전화번호로 본인 예약 조회 (간단한 본인 확인)."""
    try:
        phone = normalize_phone(phone)
    except ValueError:
        return None
    return conn.execute(
        "SELECT r.*, s.name AS service_name, s.base_price, s.extra_charge_note,"
        " s.duration_min FROM reservation r JOIN service s ON s.id = r.service_id"
        " WHERE r.code = ? AND r.phone = ?",
        (code.strip().upper(), phone),
    ).fetchone()


def cancel_reservation(
    conn: sqlite3.Connection, code: str, phone: str, now: datetime | None = None
) -> tuple[sqlite3.Row, bool]:
    """고객 셀프 취소. 반환값의 bool은 '취소 마감 이후 취소' 여부."""
    now = now or now_kst()
    reservation = find_reservation(conn, code, phone)
    if reservation is None or reservation["status"] != "confirmed":
        raise ValueError("취소할 수 있는 예약을 찾지 못했습니다.")

    deadline_hours = int(get_config(conn)["cancel_deadline_hours"])
    late = now > parse_dt(reservation["start_at"]) - timedelta(hours=deadline_hours)

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE reservation SET status = 'canceled', canceled_late = ? WHERE id = ?",
            (1 if late else 0, reservation["id"]),
        )
        _cancel_pending_notifications(conn, reservation["id"])
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return find_reservation(conn, code, phone), late


def change_reservation(
    conn: sqlite3.Connection,
    code: str,
    phone: str,
    new_start_str: str,
    now: datetime | None = None,
) -> sqlite3.Row:
    """예약 시간 변경 (시술 메뉴는 그대로). 리마인드도 새 시간 기준으로 다시 예약."""
    now = now or now_kst()
    reservation = find_reservation(conn, code, phone)
    if reservation is None or reservation["status"] != "confirmed":
        raise ValueError("변경할 수 있는 예약을 찾지 못했습니다.")

    new_start = parse_dt(new_start_str)
    new_end = new_start + timedelta(minutes=reservation["duration_min"])

    conn.execute("BEGIN IMMEDIATE")
    try:
        slots = available_slots(
            conn,
            reservation["duration_min"],
            new_start.strftime("%Y-%m-%d"),
            now=now,
            exclude_reservation_id=reservation["id"],
        )
        if new_start.strftime("%H:%M") not in slots:
            raise SlotUnavailableError("선택한 시간은 예약할 수 없습니다. 다른 시간을 선택해 주세요.")
        conn.execute(
            "UPDATE reservation SET start_at = ?, end_at = ? WHERE id = ?",
            (new_start.strftime(TIME_FMT), new_end.strftime(TIME_FMT), reservation["id"]),
        )
        _cancel_pending_notifications(conn, reservation["id"])
        _schedule_notifications(conn, reservation["id"], new_start, now)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return find_reservation(conn, code, phone)
