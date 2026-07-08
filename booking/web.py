"""고객용 예약 웹 (/booking). 모바일 웹 기준의 서버 렌더링 페이지."""

import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from booking import engine, photos
from booking.auth import current_customer
from booking.db import get_conn, get_config

router = APIRouter(prefix="/booking")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
# 카카오톡 채널 1:1 채팅 URL - 설정 시 모든 페이지에 문의 버튼 노출
templates.env.globals["kakao_channel_url"] = os.environ.get("KAKAO_CHANNEL_URL", "")
# 매장 인스타그램 URL - 설정 시 웹에 SNS 링크 노출 (마케팅 접점)
templates.env.globals["instagram_url"] = os.environ.get("INSTAGRAM_URL", "")


def _render(request: Request, conn, name: str, **context):
    config = get_config(conn)
    context.setdefault("shop_name", config["shop_name"])
    context.setdefault("config", config)
    context.setdefault("customer", current_customer(request, conn))
    return templates.TemplateResponse(request, name, context)


def _get_service(conn, service_id: int):
    return conn.execute(
        "SELECT * FROM service WHERE id = ? AND active = 1", (service_id,)
    ).fetchone()


def _date_label(date_str: str) -> str:
    """다이어리 느낌의 날짜 표기: '7월 8일 (화)'."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.month}월 {d.day}일 ({'월화수목금토일'[d.weekday()]})"


def _day_chips(conn, selected: str, count: int = 14) -> list[dict]:
    """가로 스크롤 날짜 선택 칩: 오늘부터 2주, 휴무일 표시."""
    config = get_config(conn)
    today = engine.now_kst()
    chips = []
    for i in range(count):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        chips.append({
            "date": date_str,
            "dow": "오늘" if i == 0 else "월화수목금토일"[d.weekday()],
            "num": d.day,
            "closed": engine.is_closed_day(conn, config, date_str),
            "on": date_str == selected,
        })
    return chips


def _split_slots(slots: list[str]) -> tuple[list[str], list[str]]:
    """오전/오후 그룹으로 분리."""
    return [t for t in slots if t < "12:00"], [t for t in slots if t >= "12:00"]


def _my_context(conn, reservation) -> dict:
    """my.html 렌더링용: 예약 + 고객이 올린 희망 스타일 사진."""
    ref_photos = [
        p for p in photos.photos_for_reservation(conn, reservation["id"])
        if p["kind"] == "reference"
    ]
    return {"r": reservation, "ref_photos": ref_photos}


@router.get("")
def booking_home(request: Request):
    conn = get_conn()
    try:
        services = conn.execute(
            "SELECT * FROM service WHERE active = 1 ORDER BY id"
        ).fetchall()
        return _render(request, conn, "services.html", services=services)
    finally:
        conn.close()


@router.get("/time")
def choose_time(request: Request, service_id: int, date: str = ""):
    conn = get_conn()
    try:
        service = _get_service(conn, service_id)
        if service is None:
            return _render(request, conn, "services.html",
                           services=[], error="존재하지 않는 시술 메뉴입니다.")
        today = engine.now_kst().strftime("%Y-%m-%d")
        date = date or today
        slots = engine.available_slots(conn, service["duration_min"], date)
        slots_am, slots_pm = _split_slots(slots)
        return _render(request, conn, "time.html", service=service,
                       date=date, today=today, slots=slots, change_mode=False,
                       slots_am=slots_am, slots_pm=slots_pm,
                       wait_slots=engine.waitlist_slots(conn, service["duration_min"], date),
                       day_chips=_day_chips(conn, date),
                       date_label=_date_label(date))
    finally:
        conn.close()


@router.get("/form")
def reserve_form(request: Request, service_id: int, start: str):
    conn = get_conn()
    try:
        service = _get_service(conn, service_id)
        if service is None:
            return _render(request, conn, "services.html",
                           services=[], error="존재하지 않는 시술 메뉴입니다.")
        # 로그인 고객이면 닉네임을 이름 칸에 미리 채워줌
        customer = current_customer(request, conn)
        return _render(request, conn, "form.html", service=service, start=start,
                       customer_name=customer["nickname"] if customer else "")
    finally:
        conn.close()


@router.post("/reserve")
def reserve(
    request: Request,
    service_id: int = Form(...),
    start: str = Form(...),
    customer_name: str = Form(...),
    phone: str = Form(...),
    request_note: str = Form(""),
    style_photos: list[UploadFile] = File([]),
):
    conn = get_conn()
    try:
        customer = current_customer(request, conn)

        def form_error(message: str):
            service = _get_service(conn, service_id)
            return _render(request, conn, "form.html", service=service, start=start,
                           customer_name=customer_name, phone=phone,
                           request_note=request_note, error=message)

        # 예약 확정 전에 사진부터 검증 (잘못된 파일로 예약만 생기는 것 방지)
        try:
            validated = [
                v for v in (photos.validate_upload(f) for f in style_photos)
                if v is not None
            ][: photos.MAX_REFERENCE_PHOTOS]
        except photos.PhotoValidationError as exc:
            return form_error(str(exc))

        try:
            reservation = engine.create_reservation(
                conn, service_id, customer_name, phone, request_note, start,
                customer_id=customer["id"] if customer else None,
            )
        except (ValueError, engine.SlotUnavailableError) as exc:
            return form_error(str(exc))

        for ext, data in validated:
            photos.save_photo(conn, reservation["id"], "reference", ext, data)
        return _render(request, conn, "done.html", r=reservation)
    finally:
        conn.close()


@router.get("/my")
def my_reservations(request: Request):
    """로그인 고객의 예약 목록 (예약번호 입력 불필요)."""
    conn = get_conn()
    try:
        customer = current_customer(request, conn)
        if customer is None:
            return RedirectResponse("/booking/login", status_code=303)
        reservations = conn.execute(
            "SELECT r.*, s.name AS service_name FROM reservation r"
            " JOIN service s ON s.id = r.service_id"
            " WHERE r.customer_id = ? ORDER BY r.start_at DESC LIMIT 20",
            (customer["id"],),
        ).fetchall()
        return _render(request, conn, "mybookings.html", reservations=reservations)
    finally:
        conn.close()


@router.get("/my/{code}")
def my_reservation_detail(request: Request, code: str):
    conn = get_conn()
    try:
        customer = current_customer(request, conn)
        if customer is None:
            return RedirectResponse("/booking/login", status_code=303)
        reservation = conn.execute(
            "SELECT r.*, s.name AS service_name, s.base_price, s.extra_charge_note,"
            " s.duration_min FROM reservation r JOIN service s ON s.id = r.service_id"
            " WHERE r.code = ? AND r.customer_id = ?",
            (code.strip().upper(), customer["id"]),
        ).fetchone()
        if reservation is None:
            return RedirectResponse("/booking/my", status_code=303)
        return _render(request, conn, "my.html", **_my_context(conn, reservation))
    finally:
        conn.close()


@router.get("/photo/{photo_id}")
def serve_photo(request: Request, photo_id: int, code: str = "", phone: str = ""):
    """본인 예약의 사진만 열람 가능 (예약번호+전화번호 또는 로그인 세션)."""
    conn = get_conn()
    try:
        photo = photos.get_photo(conn, photo_id)
        if photo is None:
            return RedirectResponse("/booking", status_code=303)
        reservation = conn.execute(
            "SELECT * FROM reservation WHERE id = ?", (photo["reservation_id"],)
        ).fetchone()
        customer = current_customer(request, conn)
        owns_by_code = (
            code and phone
            and engine.find_reservation(conn, code, phone) is not None
            and reservation["code"] == code.strip().upper()
        )
        owns_by_login = (
            customer is not None and reservation["customer_id"] == customer["id"]
        )
        if not (owns_by_code or owns_by_login):
            return RedirectResponse("/booking", status_code=303)
        path = photos.photo_file(photo["filename"])
        if not path.exists():
            return RedirectResponse("/booking", status_code=303)
        return FileResponse(path)
    finally:
        conn.close()


@router.get("/lookup")
def lookup_form(request: Request):
    conn = get_conn()
    try:
        return _render(request, conn, "lookup.html")
    finally:
        conn.close()


@router.post("/lookup")
def lookup(request: Request, code: str = Form(...), phone: str = Form(...)):
    conn = get_conn()
    try:
        reservation = engine.find_reservation(conn, code, phone)
        if reservation is None:
            return _render(request, conn, "lookup.html",
                           error="예약을 찾지 못했어요. 예약번호와 전화번호를 확인해 주세요.")
        return _render(request, conn, "my.html", **_my_context(conn, reservation))
    finally:
        conn.close()


@router.post("/cancel")
def cancel(request: Request, code: str = Form(...), phone: str = Form(...)):
    conn = get_conn()
    try:
        try:
            reservation, late = engine.cancel_reservation(conn, code, phone)
        except ValueError as exc:
            return _render(request, conn, "lookup.html", error=str(exc))
        message = "예약이 취소되었습니다."
        if late:
            message += " (취소 마감 시간 이후 취소로 매장에 안내됩니다)"
        return _render(request, conn, "my.html", message=message,
                       **_my_context(conn, reservation))
    finally:
        conn.close()


@router.get("/change")
def change_form(request: Request, code: str, phone: str, date: str = ""):
    conn = get_conn()
    try:
        reservation = engine.find_reservation(conn, code, phone)
        if reservation is None or reservation["status"] != "confirmed":
            return _render(request, conn, "lookup.html",
                           error="변경할 수 있는 예약을 찾지 못했습니다.")
        today = engine.now_kst().strftime("%Y-%m-%d")
        date = date or reservation["start_at"][:10]
        slots = engine.available_slots(
            conn, reservation["duration_min"], date,
            exclude_reservation_id=reservation["id"],
        )
        service = conn.execute(
            "SELECT * FROM service WHERE id = ?", (reservation["service_id"],)
        ).fetchone()
        slots_am, slots_pm = _split_slots(slots)
        return _render(request, conn, "time.html", service=service,
                       date=date, today=today, slots=slots,
                       slots_am=slots_am, slots_pm=slots_pm, wait_slots=[],
                       day_chips=_day_chips(conn, date),
                       change_mode=True, code=reservation["code"],
                       phone=reservation["phone"], date_label=_date_label(date))
    finally:
        conn.close()


@router.post("/change")
def change(
    request: Request,
    code: str = Form(...),
    phone: str = Form(...),
    new_start: str = Form(...),
):
    conn = get_conn()
    try:
        try:
            reservation = engine.change_reservation(conn, code, phone, new_start)
        except (ValueError, engine.SlotUnavailableError) as exc:
            return _render(request, conn, "lookup.html", error=str(exc))
        return _render(request, conn, "my.html", message="예약 시간이 변경되었습니다.",
                       **_my_context(conn, reservation))
    finally:
        conn.close()
