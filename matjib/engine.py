"""
교차검증 점수 엔진 + 영업 상태 계산 (프로토타입).

점수 산식은 docs/맛집찾기앱-기획안.md 4장을 그대로 구현:
  1) 채널별 원시 점수 → 지역 내 상대평가(백분위)로 0~100 정규화
  2) 종합점수 = 블로그×0.35 + 유튜브×0.30 + 인스타×0.20 + 평점×0.15
  3) 교차검증 보너스 ×1.2 / 광고 페널티 ×0.7 / 신선도 가중 ×0.8
  4) 등급: 3채널 통과=교차검증 🏆, 2채널=검증 ✅, 그 외=후보 📌

시간은 booking과 동일하게 KST 나이브 'HH:MM' 문자열 비교로 다룬다.
"""

import math
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

WEIGHTS = {"blog": 0.35, "youtube": 0.30, "insta": 0.20, "rating": 0.15}
PASS_SCORE = 60          # 채널 "통과" 기준치 (지역 내 상위 40%)
AD_RATIO_LIMIT = 0.30    # 협찬/광고 비율 30% 초과 → ×0.7
STALE_DAYS = 90          # 최근 3개월 언급 없음 → ×0.8
CROSS_BONUS = 1.2
AD_PENALTY = 0.7
STALE_PENALTY = 0.8

GRADE_BADGES = {"교차검증": "🏆 교차검증 맛집", "검증": "✅ 검증 맛집", "후보": "📌 후보"}


def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


# ---------------------------------------------------------------- 점수 계산

def _raw_scores(signals: dict) -> dict[str, float]:
    """채널별 원시 점수. 조회수·리뷰수는 로그 스케일로 눌러 롱테일 왜곡을 줄인다."""
    blog = signals["blog"]["review_count_6m"] * signals["blog"]["positive_ratio"]
    youtube = signals["youtube"]["video_count"] * math.log10(signals["youtube"]["total_views"] + 10)
    insta = float(signals["insta"]["hashtag_posts"])
    rating = signals["rating"]["avg"] * math.log10(signals["rating"]["review_count"] + 10)
    return {"blog": blog, "youtube": youtube, "insta": insta, "rating": rating}


def _percentile(values: list[float], value: float) -> float:
    """지역 내 백분위(0~100). 강남과 소도시를 같은 기준으로 비교하는 오류 방지."""
    return sum(1 for v in values if v <= value) / len(values) * 100


def score_region(restaurants: list[dict]) -> dict[int, dict]:
    """한 지역의 가게 목록을 받아 id → 점수 리포트를 돌려준다."""
    raws = {r["id"]: _raw_scores(r["signals"]) for r in restaurants}
    result = {}
    for r in restaurants:
        channel_scores = {
            ch: round(_percentile([raws[o["id"]][ch] for o in restaurants], raws[r["id"]][ch]), 1)
            for ch in WEIGHTS
        }
        total = sum(channel_scores[ch] * w for ch, w in WEIGHTS.items())

        # 등급은 성격이 다른 3채널(블로그·유튜브·인스타) 기준 - 평점은 보조 신호
        passed = [ch for ch in ("blog", "youtube", "insta") if channel_scores[ch] >= PASS_SCORE]
        cross_bonus = len(passed) == 3
        ad_penalty = r["signals"]["blog"]["sponsored_ratio"] > AD_RATIO_LIMIT
        stale = r["signals"]["last_mention_days"] > STALE_DAYS

        if cross_bonus:
            total *= CROSS_BONUS
        if ad_penalty:
            total *= AD_PENALTY
        if stale:
            total *= STALE_PENALTY

        grade = "교차검증" if len(passed) == 3 else ("검증" if len(passed) == 2 else "후보")
        result[r["id"]] = {
            "channel_scores": channel_scores,
            "total": round(min(total, 100.0), 1),
            "grade": grade,
            "badge": GRADE_BADGES[grade],
            "passed_channels": passed,
            "ad_penalty": ad_penalty,
            "stale": stale,
        }
    return result


# ---------------------------------------------------------------- 영업 상태

def _minutes(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def open_status(hours: dict, now: datetime) -> dict:
    """지금 가면 먹을 수 있는지 계산 (기획안 2장 기능 6).

    반환: {code, label, can_eat}
      open          🟢 영업 중
      last_order    🔴 라스트오더 임박 (60분 이내) - 아직은 먹을 수 있음
      break         🟡 브레이크타임
      closed        ⚫ 영업 전/종료/휴무/라스트오더 마감
    """
    if now.weekday() in hours.get("closed_weekdays", []):
        return {"code": "closed", "label": "⚫ 오늘 휴무", "can_eat": False}

    t = now.strftime("%H:%M")
    open_, close = hours["open"], hours["close"]
    # 새벽 마감(예: 18:00~01:00)은 자정 넘김을 펼쳐서 비교
    t_min = _minutes(t)
    open_min, close_min = _minutes(open_), _minutes(close)
    if close_min <= open_min:  # 자정 넘김
        close_min += 24 * 60
        if t_min < open_min:
            t_min += 24 * 60

    if not (open_min <= t_min < close_min):
        label = "⚫ 영업 전" if t_min < open_min else "⚫ 영업 종료"
        return {"code": "closed", "label": label, "can_eat": False}

    bs, be = hours.get("break_start"), hours.get("break_end")
    if bs and be and _minutes(bs) <= _minutes(t) < _minutes(be):
        return {"code": "break", "label": f"🟡 브레이크타임 {bs}~{be}", "can_eat": False}

    lo = hours.get("last_order")
    if lo:
        lo_min = _minutes(lo)
        if lo_min <= open_min:  # 자정 넘김 가게의 새벽 라스트오더
            lo_min += 24 * 60
        if t_min >= lo_min:
            return {"code": "closed", "label": "⚫ 라스트오더 마감", "can_eat": False}
        if lo_min - t_min <= 60:
            return {"code": "last_order", "label": f"🔴 라스트오더 {lo} 임박", "can_eat": True}

    return {"code": "open", "label": "🟢 영업 중", "can_eat": True}


# ---------------------------------------------------------------- 거리

def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """하버사인 거리(km). 거리순 정렬·"근처" 표시에 사용."""
    rad = math.radians
    dlat, dlng = rad(lat2 - lat1), rad(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlng / 2) ** 2
    return round(6371 * 2 * math.asin(math.sqrt(a)), 2)
