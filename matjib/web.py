"""맛집찾기(진짜맛집) 프로토타입 웹 (/matjib). 모바일 웹 기준 서버 렌더링.

기획안 5장 화면 중 홈/검색·결과 리스트·가게 상세를 구현한다 (Phase 1 범위).
데모용으로 `t=HH:MM` 쿼리 파라미터를 주면 그 시각 기준으로 영업 상태를
계산한다 (브레이크타임·라스트오더 화면을 낮에도 확인하기 위한 프로토타입 장치).
"""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from matjib import data, engine

router = APIRouter(prefix="/matjib")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["CATEGORIES"] = data.CATEGORIES
templates.env.globals["PRICE_LABELS"] = data.PRICE_LABELS


def _now(t: str | None) -> datetime:
    """데모용 시각 오버라이드: t=HH:MM 이 있으면 오늘 그 시각으로 계산."""
    now = engine.now_kst()
    if t:
        try:
            hh, mm = t.split(":")
            now = now.replace(hour=int(hh), minute=int(mm))
        except ValueError:
            pass
    return now


def _enrich(region: str, now: datetime) -> list[dict]:
    """지역 가게 목록에 점수·영업상태·거리를 붙인 뷰 모델."""
    restaurants = data.by_region(region)
    scores = engine.score_region(restaurants)
    center = data.REGIONS[region]
    items = []
    for r in restaurants:
        items.append({
            **r,
            "score": scores[r["id"]],
            "status": engine.open_status(r["hours"], now),
            "distance": engine.distance_km(center["lat"], center["lng"], r["lat"], r["lng"]),
        })
    return items


@router.get("")
def home(request: Request, t: str | None = None):
    now = _now(t)
    # 현재 위치 목업: 성수동 기준 "지금 갈 수 있는 근처 교차검증 맛집" 3곳
    nearby = [
        i for i in _enrich("성수동", now)
        if i["status"]["can_eat"] and i["score"]["grade"] in ("교차검증", "검증")
    ]
    nearby.sort(key=lambda i: -i["score"]["total"])
    return templates.TemplateResponse(request, "home.html", {
        "nearby": nearby[:3], "now": now, "t": t,
    })


@router.get("/search")
def search(
    request: Request,
    region: str = "",
    category: str = "",
    price: str = "",
    open_now: str = "",
    no_lo_rush: str = "",
    reservable: str = "",
    sort: str = "score",
    t: str | None = None,
):
    now = _now(t)
    resolved = data.resolve_region(region)
    if resolved is None:
        # 미수집 지역: 즉석 수집 후 완성되는 "분석 중" UX (기획안 6.3 / 10장)
        return templates.TemplateResponse(request, "list.html", {
            "region": region, "resolved": None, "items": [], "now": now, "t": t,
            "category": category, "price": price, "open_now": open_now,
            "no_lo_rush": no_lo_rush, "reservable": reservable, "sort": sort,
        })

    items = _enrich(resolved, now)
    if category:
        items = [i for i in items if i["category"] == category]
    if price:
        items = [i for i in items if str(i["price_tier"]) == price]
    if open_now:
        items = [i for i in items if i["status"]["can_eat"]]
    if no_lo_rush:
        items = [i for i in items if i["status"]["code"] == "open"]
    if reservable:
        items = [i for i in items if i["reservation"]["naver_booking_url"]
                 or i["reservation"]["catchtable_url"]]

    if sort == "rating":
        items.sort(key=lambda i: -i["signals"]["rating"]["avg"])
    elif sort == "distance":
        items.sort(key=lambda i: i["distance"])
    else:
        items.sort(key=lambda i: -i["score"]["total"])

    return templates.TemplateResponse(request, "list.html", {
        "region": region, "resolved": resolved, "items": items, "now": now, "t": t,
        "category": category, "price": price, "open_now": open_now,
        "no_lo_rush": no_lo_rush, "reservable": reservable, "sort": sort,
    })


@router.get("/r/{rid}")
def detail(request: Request, rid: int, t: str | None = None):
    r = data.by_id(rid)
    if r is None:
        return RedirectResponse("/matjib")
    now = _now(t)
    scores = engine.score_region(data.by_region(r["region"]))
    weekdays = "월화수목금토일"
    return templates.TemplateResponse(request, "detail.html", {
        "r": r, "score": scores[rid],
        "status": engine.open_status(r["hours"], now),
        "weekdays": weekdays, "now": now, "t": t,
    })
