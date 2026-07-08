"""
원장용 관리자 웹 (/admin).

인증은 HTTP Basic (아이디 admin / 비밀번호는 환경변수 ADMIN_PASSWORD).
1인샵 운영에 필요한 최소 기능: 일별 예약 현황, 상태 변경(방문/노쇼/취소),
수기(전화) 예약 입력, 메뉴 관리, 영업시간·휴무 설정.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status,
)
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from booking import engine, photos
from booking.db import get_conn, get_config, set_config
from booking.engine import _cancel_pending_notifications

logger = logging.getLogger("booking.admin")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")
if ADMIN_PASSWORD == "changeme":
    logger.warning("ADMIN_PASSWORD가 설정되지 않아 기본값을 사용합니다. 운영 전 꼭 바꾸세요.")

_security = HTTPBasic()


def _admin_auth(credentials: HTTPBasicCredentials = Depends(_security)) -> str:
    ok = secrets.compare_digest(credentials.username, "admin") and secrets.compare_digest(
        credentials.password, ADMIN_PASSWORD
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


router = APIRouter(prefix="/admin", dependencies=[Depends(_admin_auth)])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["kakao_channel_url"] = os.environ.get("KAKAO_CHANNEL_URL", "")

STATUS_LABEL = {
    "confirmed": "확정",
    "done": "방문 완료",
    "noshow": "노쇼",
    "canceled": "취소",
}


def _render(request: Request, conn, name: str, **context):
    config = get_config(conn)
    context.setdefault("shop_name", config["shop_name"])
    context.setdefault("config", config)
    context.setdefault("status_label", STATUS_LABEL)
    return templates.TemplateResponse(request, name, context)


@router.get("")
def day_view(request: Request, date: str = "", error: str = "", message: str = ""):
    conn = get_conn()
    try:
        date = date or engine.now_kst().strftime("%Y-%m-%d")
        day = datetime.strptime(date, "%Y-%m-%d")
        reservations = conn.execute(
            "SELECT r.*, s.name AS service_name FROM reservation r"
            " JOIN service s ON s.id = r.service_id"
            " WHERE r.start_at LIKE ? ORDER BY r.start_at",
            (f"{date}T%",),
        ).fetchall()
        return _render(
            request, conn, "admin_day.html",
            date=date,
            prev_date=(day - timedelta(days=1)).strftime("%Y-%m-%d"),
            next_date=(day + timedelta(days=1)).strftime("%Y-%m-%d"),
            reservations=reservations,
            closed=engine.is_closed_day(conn, get_config(conn), date),
            error=error, message=message,
        )
    finally:
        conn.close()


@router.post("/status")
def change_status(
    reservation_id: int = Form(...),
    new_status: str = Form(...),
    date: str = Form(...),
):
    if new_status not in STATUS_LABEL:
        raise HTTPException(status_code=400)
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE reservation SET status = ? WHERE id = ?",
                (new_status, reservation_id),
            )
            if new_status in ("canceled", "noshow", "done"):
                _cancel_pending_notifications(conn, reservation_id)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        return RedirectResponse(f"/admin?date={date}", status_code=303)
    finally:
        conn.close()


@router.get("/new")
def manual_new_form(request: Request, service_id: int = 0, date: str = ""):
    conn = get_conn()
    try:
        services = conn.execute(
            "SELECT * FROM service WHERE active = 1 ORDER BY id"
        ).fetchall()
        date = date or engine.now_kst().strftime("%Y-%m-%d")
        service = next((s for s in services if s["id"] == service_id), None)
        slots = (
            engine.available_slots(conn, service["duration_min"], date)
            if service else []
        )
        return _render(request, conn, "admin_new.html", services=services,
                       service=service, date=date, slots=slots)
    finally:
        conn.close()


@router.post("/new")
def manual_new(
    request: Request,
    service_id: int = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    customer_name: str = Form(...),
    phone: str = Form(...),
    request_note: str = Form(""),
):
    conn = get_conn()
    try:
        try:
            reservation = engine.create_reservation(
                conn, service_id, customer_name, phone, request_note,
                f"{date}T{time}", source="manual",
            )
        except (ValueError, engine.SlotUnavailableError) as exc:
            services = conn.execute(
                "SELECT * FROM service WHERE active = 1 ORDER BY id"
            ).fetchall()
            service = next((s for s in services if s["id"] == service_id), None)
            slots = (
                engine.available_slots(conn, service["duration_min"], date)
                if service else []
            )
            return _render(request, conn, "admin_new.html", services=services,
                           service=service, date=date, slots=slots, error=str(exc))
        return RedirectResponse(f"/admin?date={reservation['start_at'][:10]}",
                                status_code=303)
    finally:
        conn.close()


PHOTO_KIND_LABEL = {
    "reference": "희망 스타일", "front": "정면", "side": "측면", "back": "뒷면",
}


@router.get("/customers")
def customers_view(request: Request, q: str = ""):
    """고객 아카이브: 전화번호 기준으로 방문 이력을 묶어 보여줌."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT customer_name, phone, status, start_at FROM reservation"
            " ORDER BY start_at DESC"
        ).fetchall()
        groups: dict[str, dict] = {}
        for r in rows:
            g = groups.setdefault(r["phone"], {
                "name": r["customer_name"], "phone": r["phone"],
                "total": 0, "done": 0, "noshow": 0, "last": r["start_at"],
            })
            g["total"] += 1
            if r["status"] == "done":
                g["done"] += 1
            elif r["status"] == "noshow":
                g["noshow"] += 1
        customers = list(groups.values())
        if q.strip():
            needle = q.strip()
            digits = "".join(ch for ch in needle if ch.isdigit())
            customers = [
                c for c in customers
                if needle in c["name"] or (digits and digits in c["phone"])
            ]
        return _render(request, conn, "admin_customers.html",
                       customers=customers, q=q)
    finally:
        conn.close()


@router.get("/customers/{phone}")
def customer_history(request: Request, phone: str):
    """고객 1명의 시술 아카이브: 방문 이력 + 희망 스타일/시술 결과 사진."""
    conn = get_conn()
    try:
        reservations = conn.execute(
            "SELECT r.*, s.name AS service_name FROM reservation r"
            " JOIN service s ON s.id = r.service_id"
            " WHERE r.phone = ? ORDER BY r.start_at DESC",
            (phone,),
        ).fetchall()
        if not reservations:
            return RedirectResponse("/admin/customers", status_code=303)
        photos_by_res: dict[int, list] = {}
        for p in conn.execute(
            "SELECT p.* FROM photo p JOIN reservation r ON r.id = p.reservation_id"
            " WHERE r.phone = ? ORDER BY p.id",
            (phone,),
        ).fetchall():
            photos_by_res.setdefault(p["reservation_id"], []).append(p)
        done = sum(1 for r in reservations if r["status"] == "done")
        noshow = sum(1 for r in reservations if r["status"] == "noshow")
        return _render(request, conn, "admin_history.html",
                       reservations=reservations, photos_by_res=photos_by_res,
                       customer_name=reservations[0]["customer_name"], phone=phone,
                       done=done, noshow=noshow,
                       photo_kind_label=PHOTO_KIND_LABEL)
    finally:
        conn.close()


@router.get("/photos/file/{photo_id}")
def photo_file(photo_id: int):
    """사진 원본 서빙 (관리자 인증 필수 - 공개 정적 경로로 노출 금지)."""
    conn = get_conn()
    try:
        photo = photos.get_photo(conn, photo_id)
    finally:
        conn.close()
    if photo is None or not photos.photo_file(photo["filename"]).exists():
        raise HTTPException(status_code=404)
    return FileResponse(photos.photo_file(photo["filename"]))


@router.get("/photos/{reservation_id}")
def photos_view(request: Request, reservation_id: int, error: str = ""):
    conn = get_conn()
    try:
        reservation = conn.execute(
            "SELECT r.*, s.name AS service_name FROM reservation r"
            " JOIN service s ON s.id = r.service_id WHERE r.id = ?",
            (reservation_id,),
        ).fetchone()
        if reservation is None:
            raise HTTPException(status_code=404)
        all_photos = photos.photos_for_reservation(conn, reservation_id)
        return _render(
            request, conn, "admin_photos.html",
            r=reservation,
            ref_photos=[p for p in all_photos if p["kind"] == "reference"],
            result_photos={p["kind"]: p for p in all_photos
                           if p["kind"] in photos.RESULT_KINDS},
            angles=[("front", "정면"), ("side", "측면"), ("back", "뒷면")],
            error=error,
        )
    finally:
        conn.close()


@router.post("/photos/{reservation_id}")
def photos_upload(
    reservation_id: int,
    front: UploadFile = File(None),
    side: UploadFile = File(None),
    back: UploadFile = File(None),
):
    conn = get_conn()
    try:
        try:
            for kind, upload in (("front", front), ("side", side), ("back", back)):
                validated = photos.validate_upload(upload)
                if validated is not None:
                    photos.save_photo(conn, reservation_id, kind, *validated)
        except photos.PhotoValidationError as exc:
            return RedirectResponse(
                f"/admin/photos/{reservation_id}?error={exc}", status_code=303
            )
        return RedirectResponse(f"/admin/photos/{reservation_id}", status_code=303)
    finally:
        conn.close()


@router.get("/services")
def services_view(request: Request):
    conn = get_conn()
    try:
        services = conn.execute("SELECT * FROM service ORDER BY id").fetchall()
        return _render(request, conn, "admin_services.html", services=services)
    finally:
        conn.close()


@router.post("/services/add")
def service_add(
    name: str = Form(...),
    category: str = Form(...),
    base_price: int = Form(...),
    extra_charge_note: str = Form(""),
    duration_min: int = Form(...),
):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO service (name, category, base_price, extra_charge_note,"
            " duration_min) VALUES (?, ?, ?, ?, ?)",
            (name.strip(), category.strip(), base_price, extra_charge_note.strip(),
             duration_min),
        )
        return RedirectResponse("/admin/services", status_code=303)
    finally:
        conn.close()


@router.post("/services/{service_id}/update")
def service_update(
    service_id: int,
    name: str = Form(...),
    base_price: int = Form(...),
    extra_charge_note: str = Form(""),
    duration_min: int = Form(...),
    active: int = Form(...),
):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE service SET name = ?, base_price = ?, extra_charge_note = ?,"
            " duration_min = ?, active = ? WHERE id = ?",
            (name.strip(), base_price, extra_charge_note.strip(), duration_min,
             active, service_id),
        )
        return RedirectResponse("/admin/services", status_code=303)
    finally:
        conn.close()


@router.get("/settings")
def settings_view(request: Request):
    conn = get_conn()
    try:
        closed_dates = conn.execute(
            "SELECT date FROM closed_date ORDER BY date"
        ).fetchall()
        return _render(request, conn, "admin_settings.html",
                       closed_dates=closed_dates, weekdays=list(enumerate("월화수목금토일")))
    finally:
        conn.close()


@router.post("/settings")
async def settings_save(request: Request):
    form = await request.form()
    conn = get_conn()
    try:
        for key in ("shop_name", "open_time", "close_time", "slot_minutes",
                    "cancel_deadline_hours"):
            set_config(conn, key, str(form.get(key, "")).strip())
        # 체크박스로 들어온 정기 휴무 요일들
        set_config(conn, "weekly_closed", ",".join(form.getlist("weekly_closed")))
        return RedirectResponse("/admin/settings", status_code=303)
    finally:
        conn.close()


@router.post("/closed-dates/add")
def closed_date_add(date: str = Form(...)):
    conn = get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO closed_date (date) VALUES (?)", (date,))
        return RedirectResponse("/admin/settings", status_code=303)
    finally:
        conn.close()


@router.post("/closed-dates/delete")
def closed_date_delete(date: str = Form(...)):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM closed_date WHERE date = ?", (date,))
        return RedirectResponse("/admin/settings", status_code=303)
    finally:
        conn.close()
