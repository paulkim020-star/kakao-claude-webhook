"""
카카오/네이버 소셜 로그인 (선택 기능).

- 로그인 없이도 예약(예약번호+전화번호)은 전부 가능. 로그인하면 예약번호
  입력 없이 "내 예약" 목록이 자동으로 보이는 편의 기능입니다.
- 환경변수(KAKAO_CLIENT_ID / NAVER_CLIENT_ID)가 없는 제공자는 버튼 자체가
  숨겨집니다. 카카오는 developers.kakao.com, 네이버는 developers.naver.com
  에서 앱 등록 후 발급받아야 하며, 각 콘솔에 콜백 URL
  ({BOOKING_BASE_URL}/booking/login/{provider}/callback)을 등록해야 합니다.
- 세션은 HMAC 서명 쿠키. SESSION_SECRET 미설정 시 프로세스마다 랜덤 생성
  (서버 재시작 시 로그인이 풀림 - 운영에서는 고정값 설정 권장).
"""

import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from booking.db import get_conn, get_config
from booking.engine import now_kst, TIME_FMT

logger = logging.getLogger("booking.auth")

BOOKING_BASE_URL = os.environ.get("BOOKING_BASE_URL", "http://localhost:8000")
KAKAO_CLIENT_ID = os.environ.get("KAKAO_CLIENT_ID", "")
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "")
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)

SESSION_COOKIE = "bk_session"
STATE_COOKIE = "bk_oauth_state"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30일

router = APIRouter(prefix="/booking")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["kakao_channel_url"] = os.environ.get("KAKAO_CHANNEL_URL", "")
templates.env.globals["instagram_url"] = os.environ.get("INSTAGRAM_URL", "")


def available_providers() -> list[str]:
    providers = []
    if KAKAO_CLIENT_ID:
        providers.append("kakao")
    if NAVER_CLIENT_ID:
        providers.append("naver")
    return providers


def _redirect_uri(provider: str) -> str:
    return f"{BOOKING_BASE_URL}/booking/login/{provider}/callback"


# ---------- 세션 (HMAC 서명 쿠키) ----------

def _sign(value: str) -> str:
    return hmac.new(SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def make_session_value(customer_id: int) -> str:
    return f"{customer_id}:{_sign(str(customer_id))}"


def parse_session_value(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    customer_id, signature = value.split(":", 1)
    if not hmac.compare_digest(signature, _sign(customer_id)):
        return None
    return int(customer_id)


def current_customer(request: Request, conn: sqlite3.Connection) -> sqlite3.Row | None:
    customer_id = parse_session_value(request.cookies.get(SESSION_COOKIE))
    if customer_id is None:
        return None
    return conn.execute(
        "SELECT * FROM customer WHERE id = ?", (customer_id,)
    ).fetchone()


def upsert_customer(
    conn: sqlite3.Connection, provider: str, provider_uid: str, nickname: str
) -> int:
    conn.execute(
        "INSERT INTO customer (provider, provider_uid, nickname, created_at)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT(provider, provider_uid) DO UPDATE SET nickname = excluded.nickname",
        (provider, provider_uid, nickname, now_kst().strftime(TIME_FMT)),
    )
    return conn.execute(
        "SELECT id FROM customer WHERE provider = ? AND provider_uid = ?",
        (provider, provider_uid),
    ).fetchone()["id"]


# ---------- OAuth 제공자 연동 ----------

def _exchange(provider: str, code: str, state: str) -> tuple[str, str]:
    """인가 코드 -> (제공자 고유 ID, 닉네임). 실패 시 예외."""
    if provider == "kakao":
        token_data = {
            "grant_type": "authorization_code",
            "client_id": KAKAO_CLIENT_ID,
            "redirect_uri": _redirect_uri("kakao"),
            "code": code,
        }
        if KAKAO_CLIENT_SECRET:
            token_data["client_secret"] = KAKAO_CLIENT_SECRET
        token = httpx.post(
            "https://kauth.kakao.com/oauth/token", data=token_data, timeout=10
        ).raise_for_status().json()
        me = httpx.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=10,
        ).raise_for_status().json()
        nickname = (
            me.get("kakao_account", {}).get("profile", {}).get("nickname")
            or me.get("properties", {}).get("nickname")
            or "카카오 회원"
        )
        return str(me["id"]), nickname

    if provider == "naver":
        token = httpx.post(
            "https://nid.naver.com/oauth2.0/token",
            data={
                "grant_type": "authorization_code",
                "client_id": NAVER_CLIENT_ID,
                "client_secret": NAVER_CLIENT_SECRET,
                "code": code,
                "state": state,
            },
            timeout=10,
        ).raise_for_status().json()
        me = httpx.get(
            "https://openapi.naver.com/v1/nid/me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=10,
        ).raise_for_status().json()["response"]
        return str(me["id"]), me.get("nickname") or me.get("name") or "네이버 회원"

    raise ValueError(f"지원하지 않는 로그인 제공자: {provider}")


def _authorize_url(provider: str, state: str) -> str:
    if provider == "kakao":
        return (
            "https://kauth.kakao.com/oauth/authorize?response_type=code"
            f"&client_id={KAKAO_CLIENT_ID}&redirect_uri={_redirect_uri('kakao')}"
            f"&state={state}"
        )
    return (
        "https://nid.naver.com/oauth2.0/authorize?response_type=code"
        f"&client_id={NAVER_CLIENT_ID}&redirect_uri={_redirect_uri('naver')}"
        f"&state={state}"
    )


# ---------- 라우트 ----------

def _render(request: Request, conn, name: str, **context):
    config = get_config(conn)
    context.setdefault("shop_name", config["shop_name"])
    context.setdefault("config", config)
    context.setdefault("customer", current_customer(request, conn))
    return templates.TemplateResponse(request, name, context)


@router.get("/login")
def login_page(request: Request):
    conn = get_conn()
    try:
        return _render(request, conn, "login.html", providers=available_providers())
    finally:
        conn.close()


@router.get("/login/{provider}")
def login_start(provider: str):
    if provider not in available_providers():
        return RedirectResponse("/booking/login", status_code=303)
    state = secrets.token_urlsafe(16)
    response = RedirectResponse(_authorize_url(provider, state), status_code=307)
    response.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax")
    return response


@router.get("/login/{provider}/callback")
def login_callback(request: Request, provider: str, code: str = "", state: str = ""):
    conn = get_conn()
    try:
        if provider not in available_providers() or not code:
            return _render(request, conn, "login.html",
                           providers=available_providers(),
                           error="로그인에 실패했어요. 다시 시도해 주세요.")
        if not state or state != request.cookies.get(STATE_COOKIE):
            return _render(request, conn, "login.html",
                           providers=available_providers(),
                           error="로그인 요청이 만료되었어요. 다시 시도해 주세요.")
        try:
            provider_uid, nickname = _exchange(provider, code, state)
        except Exception:  # noqa: BLE001
            logger.exception("%s 로그인 실패", provider)
            return _render(request, conn, "login.html",
                           providers=available_providers(),
                           error="로그인 처리 중 오류가 발생했어요. 다시 시도해 주세요.")
        customer_id = upsert_customer(conn, provider, provider_uid, nickname)
        response = RedirectResponse("/booking/my", status_code=303)
        response.set_cookie(
            SESSION_COOKIE, make_session_value(customer_id),
            max_age=SESSION_MAX_AGE, httponly=True, samesite="lax",
        )
        response.delete_cookie(STATE_COOKIE)
        return response
    finally:
        conn.close()


@router.get("/logout")
def logout():
    response = RedirectResponse("/booking", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response
