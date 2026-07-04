"""고객용 예약 웹 (/booking). 모바일 웹 기준의 서버 렌더링 페이지."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from booking import engine
from booking.auth import current_customer
from booking.db import get_conn, get_config

router = APIRouter(prefix="/booking")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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
        return _render(request, conn, "time.html", service=service,
                       date=date, today=today, slots=slots, change_mode=False)
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
):
    conn = get_conn()
    try:
        customer = current_customer(request, conn)
        try:
            reservation = engine.create_reservation(
                conn, service_id, customer_name, phone, request_note, start,
                customer_id=customer["id"] if customer else None,
            )
        except (ValueError, engine.SlotUnavailableError) as exc:
            service = _get_service(conn, service_id)
            return _render(request, conn, "form.html", service=service, start=start,
                           customer_name=customer_name, phone=phone,
                           request_note=request_note, error=str(exc))
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
        return _render(request, conn, "my.html", r=reservation)
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
        return _render(request, conn, "my.html", r=reservation)
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
        return _render(request, conn, "my.html", r=reservation, message=message)
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
        return _render(request, conn, "time.html", service=service,
                       date=date, today=today, slots=slots,
                       change_mode=True, code=reservation["code"],
                       phone=reservation["phone"])
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
        return _render(request, conn, "my.html", r=reservation,
                       message="예약 시간이 변경되었습니다.")
    finally:
        conn.close()
