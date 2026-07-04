"""
예약 코어(슬롯 계산/충돌 방지)와 웹 플로우 검증.

실행: pip install -r requirements-dev.txt && pytest
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import booking.db as db
from booking import engine
from booking.notify import process_due_notifications

# 고정 기준: 2026-07-14은 화요일 (기본 정기 휴무는 월요일)
TUESDAY = "2026-07-14"
MONDAY = "2026-07-13"
NOW = datetime(2026, 7, 10, 9, 0)


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    conn = db.get_conn()
    yield conn
    conn.close()


def _cut_service(conn):
    return conn.execute("SELECT * FROM service WHERE name = '컷'").fetchone()


# ---------- 슬롯 계산 ----------

def test_slots_open_hours(conn):
    # 10:00~20:00, 30분 간격, 40분 시술 → 10:00부터 19:00까지
    slots = engine.available_slots(conn, 40, TUESDAY, now=NOW)
    assert slots[0] == "10:00"
    assert slots[-1] == "19:00"


def test_slots_weekly_closed(conn):
    assert engine.available_slots(conn, 40, MONDAY, now=NOW) == []


def test_slots_specific_closed_date(conn):
    conn.execute("INSERT INTO closed_date (date) VALUES (?)", (TUESDAY,))
    assert engine.available_slots(conn, 40, TUESDAY, now=NOW) == []


def test_slots_exclude_past_times(conn):
    noon = datetime(2026, 7, 14, 12, 0)
    slots = engine.available_slots(conn, 40, TUESDAY, now=noon)
    assert "12:00" not in slots  # 정각(지금)은 제외, 미래만
    assert slots[0] == "12:30"


# ---------- 예약 생성/충돌 ----------

def test_create_reservation_blocks_overlap(conn):
    service = _cut_service(conn)  # 40분
    r = engine.create_reservation(
        conn, service["id"], "김손님", "010-1234-5678", "", f"{TUESDAY}T11:00", now=NOW
    )
    assert r["status"] == "confirmed"
    slots = engine.available_slots(conn, 40, TUESDAY, now=NOW)
    # 11:00~11:40 예약과 겹치는 시작 시각은 모두 제외
    assert "10:30" not in slots and "11:00" not in slots and "11:30" not in slots
    assert "10:00" in slots and "12:00" in slots

    with pytest.raises(engine.SlotUnavailableError):
        engine.create_reservation(
            conn, service["id"], "박손님", "010-9999-8888", "", f"{TUESDAY}T11:30", now=NOW
        )


def test_create_reservation_rejects_closed_day(conn):
    service = _cut_service(conn)
    with pytest.raises(engine.SlotUnavailableError):
        engine.create_reservation(
            conn, service["id"], "김손님", "01012345678", "", f"{MONDAY}T11:00", now=NOW
        )


def test_create_reservation_validates_input(conn):
    service = _cut_service(conn)
    with pytest.raises(ValueError):
        engine.create_reservation(
            conn, service["id"], "  ", "01012345678", "", f"{TUESDAY}T11:00", now=NOW
        )
    with pytest.raises(ValueError):
        engine.create_reservation(
            conn, service["id"], "김손님", "12", "", f"{TUESDAY}T11:00", now=NOW
        )


# ---------- 취소/변경 ----------

def test_cancel_frees_slot_and_flags_late(conn):
    service = _cut_service(conn)
    r = engine.create_reservation(
        conn, service["id"], "김손님", "01012345678", "", f"{TUESDAY}T11:00", now=NOW
    )
    # 예약 23시간 전 취소 → 마감(24시간) 이후 취소
    late_now = datetime(2026, 7, 13, 12, 0)
    canceled, late = engine.cancel_reservation(conn, r["code"], "01012345678", now=late_now)
    assert canceled["status"] == "canceled" and late is True
    assert "11:00" in engine.available_slots(conn, 40, TUESDAY, now=NOW)
    # 취소되면 대기 중이던 리마인드도 함께 취소
    pending = conn.execute(
        "SELECT COUNT(*) FROM notification WHERE reservation_id = ? AND status = 'pending'",
        (r["id"],),
    ).fetchone()[0]
    assert pending == 0


def test_change_reservation_moves_slot(conn):
    service = _cut_service(conn)
    r = engine.create_reservation(
        conn, service["id"], "김손님", "01012345678", "", f"{TUESDAY}T11:00", now=NOW
    )
    changed = engine.change_reservation(
        conn, r["code"], "01012345678", f"{TUESDAY}T15:00", now=NOW
    )
    assert changed["start_at"] == f"{TUESDAY}T15:00"
    assert changed["end_at"] == f"{TUESDAY}T15:40"
    assert "11:00" in engine.available_slots(conn, 40, TUESDAY, now=NOW)
    # 새 시간 기준 리마인드가 다시 잡혀 있어야 함
    pending = conn.execute(
        "SELECT kind FROM notification WHERE reservation_id = ? AND status = 'pending'"
        " ORDER BY due_at",
        (r["id"],),
    ).fetchall()
    assert [p["kind"] for p in pending] == ["confirm", "day_before", "same_day"]


# ---------- 리마인드 ----------

def test_notifications_scheduled_and_sent(conn):
    service = _cut_service(conn)
    r = engine.create_reservation(
        conn, service["id"], "김손님", "01012345678", "", f"{TUESDAY}T11:00", now=NOW
    )
    rows = conn.execute(
        "SELECT kind, due_at FROM notification WHERE reservation_id = ? ORDER BY due_at",
        (r["id"],),
    ).fetchall()
    assert [(x["kind"], x["due_at"]) for x in rows] == [
        ("confirm", "2026-07-10T09:00"),
        ("day_before", "2026-07-13T19:00"),
        ("same_day", "2026-07-14T09:00"),
    ]
    # 예약 직후: confirm만 발송 대상
    assert process_due_notifications(now=NOW) == 1
    # 전날 저녁이 지나면 day_before 발송
    assert process_due_notifications(now=datetime(2026, 7, 13, 19, 5)) == 1
    assert process_due_notifications(now=datetime(2026, 7, 13, 19, 5)) == 0  # 중복 발송 없음


# ---------- 웹 플로우 (API) ----------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "web.db"))
    from main import app

    with TestClient(app) as c:
        yield c


def _future_open_date() -> str:
    d = engine.now_kst() + timedelta(days=3)
    while d.weekday() == 0:  # 기본 설정: 월요일 휴무
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def test_web_reserve_flow_and_conflict(client):
    date = _future_open_date()
    assert client.get("/booking").status_code == 200

    form = {
        "service_id": 1, "start": f"{date}T14:00",
        "customer_name": "웹손님", "phone": "010-1111-2222", "request_note": "테스트",
    }
    res = client.post("/booking/reserve", data=form)
    assert res.status_code == 200 and "예약이 확정되었습니다" in res.text

    # 같은 시간 중복 예약 시도 → 에러 안내
    res2 = client.post("/booking/reserve", data={**form, "phone": "010-3333-4444"})
    assert "예약할 수 없습니다" in res2.text


def test_web_lookup_and_cancel(client):
    date = _future_open_date()
    client.post("/booking/reserve", data={
        "service_id": 1, "start": f"{date}T16:00",
        "customer_name": "조회손님", "phone": "010-5555-6666", "request_note": "",
    })
    conn = db.get_conn()
    code = conn.execute(
        "SELECT code FROM reservation WHERE phone = '01055556666'"
    ).fetchone()["code"]
    conn.close()

    res = client.post("/booking/lookup", data={"code": code, "phone": "010-5555-6666"})
    assert "예약 정보" in res.text
    res = client.post("/booking/cancel", data={"code": code, "phone": "010-5555-6666"})
    assert "예약이 취소되었습니다" in res.text


def test_admin_requires_auth(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=("admin", "changeme")).status_code == 200


def test_webhook_booking_intent(client):
    payload = {"userRequest": {"utterance": "예약하고 싶어요", "user": {"id": "u1"}}}
    res = client.post("/kakao/webhook", json=payload)
    text = res.json()["template"]["outputs"][0]["simpleText"]["text"]
    assert "/booking" in text


# ---------- 소셜 로그인 ----------

def test_session_cookie_sign_and_tamper():
    from booking import auth

    value = auth.make_session_value(42)
    assert auth.parse_session_value(value) == 42
    assert auth.parse_session_value("43:" + value.split(":")[1]) is None  # 위조
    assert auth.parse_session_value(None) is None
    assert auth.parse_session_value("garbage") is None


def test_upsert_customer_is_idempotent(conn):
    from booking import auth

    first = auth.upsert_customer(conn, "kakao", "uid-1", "닉네임")
    second = auth.upsert_customer(conn, "kakao", "uid-1", "새닉네임")
    assert first == second
    row = conn.execute("SELECT * FROM customer WHERE id = ?", (first,)).fetchone()
    assert row["nickname"] == "새닉네임"


def test_login_page_without_providers(client, monkeypatch):
    from booking import auth

    monkeypatch.setattr(auth, "KAKAO_CLIENT_ID", "")
    monkeypatch.setattr(auth, "NAVER_CLIENT_ID", "")
    res = client.get("/booking/login")
    assert res.status_code == 200 and "준비되지 않았어요" in res.text


def test_social_login_flow_links_reservations(client, monkeypatch):
    from booking import auth

    monkeypatch.setattr(auth, "KAKAO_CLIENT_ID", "test-key")
    monkeypatch.setattr(auth, "_exchange", lambda p, c, s: ("kakao-uid-7", "테스트고객"))

    # 로그인 시작 → 카카오 인가 페이지로 리다이렉트 + state 쿠키
    res = client.get("/booking/login/kakao", follow_redirects=False)
    assert res.status_code == 307 and "kauth.kakao.com" in res.headers["location"]
    state = res.headers["location"].split("state=")[1]

    # 콜백 → 세션 쿠키 발급 + 내 예약으로 이동
    res = client.get(
        f"/booking/login/kakao/callback?code=dummy&state={state}",
        follow_redirects=False,
    )
    assert res.status_code == 303 and res.headers["location"] == "/booking/my"
    assert auth.SESSION_COOKIE in client.cookies

    # 로그인 상태로 예약 → customer_id가 연결됨
    date = _future_open_date()
    res = client.post("/booking/reserve", data={
        "service_id": 1, "start": f"{date}T11:00",
        "customer_name": "테스트고객", "phone": "010-2222-1111", "request_note": "",
    })
    assert "예약이 확정되었습니다" in res.text

    conn = db.get_conn()
    row = conn.execute(
        "SELECT r.customer_id, r.code, c.provider_uid FROM reservation r"
        " JOIN customer c ON c.id = r.customer_id WHERE r.phone = '01022221111'"
    ).fetchone()
    conn.close()
    assert row["provider_uid"] == "kakao-uid-7"

    # 내 예약 목록/상세에 예약번호 입력 없이 접근 가능
    res = client.get("/booking/my")
    assert res.status_code == 200 and row["code"] in res.text
    res = client.get(f"/booking/my/{row['code']}")
    assert res.status_code == 200 and "예약 정보" in res.text

    # 로그아웃하면 내 예약은 로그인 페이지로
    client.get("/booking/logout")
    res = client.get("/booking/my", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/booking/login"
