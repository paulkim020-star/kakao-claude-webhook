"""맛집찾기 프로토타입 테스트: 점수 산식, 영업 상태, 웹 플로우."""

from datetime import datetime

from fastapi.testclient import TestClient

from matjib import data, engine
from main import app

client = TestClient(app)


def _signals(blog=50, positive=0.8, sponsored=0.05, videos=3, views=100_000,
             insta=1000, rating=4.3, rating_count=200, last_mention=10):
    return {
        "blog": {"review_count_6m": blog, "positive_ratio": positive, "sponsored_ratio": sponsored},
        "youtube": {"video_count": videos, "total_views": views},
        "insta": {"hashtag_posts": insta},
        "rating": {"avg": rating, "review_count": rating_count},
        "last_mention_days": last_mention,
    }


def _restaurant(rid, **signal_overrides):
    return {"id": rid, "signals": _signals(**signal_overrides)}


# ---------------------------------------------------------------- 점수 산식

def test_all_channel_winner_gets_cross_grade_and_bonus():
    # 1번이 모든 채널 1등 → 백분위 100 → 3채널 통과 → 교차검증 + ×1.2 보너스
    rs = [
        _restaurant(1, blog=200, videos=10, views=2_000_000, insta=5000, rating=4.8),
        _restaurant(2, blog=50, videos=2, views=100_000, insta=800, rating=4.0),
        _restaurant(3, blog=10, videos=0, views=0, insta=100, rating=3.5),
    ]
    scores = engine.score_region(rs)
    top = scores[1]
    assert top["grade"] == "교차검증"
    assert top["total"] == 100.0  # 100 × 1.2는 100점으로 캡
    assert scores[3]["grade"] == "후보"


def test_ad_penalty_applied_over_30_percent_sponsored():
    rs = [
        _restaurant(1, sponsored=0.45),
        _restaurant(2, blog=200, videos=10, views=2_000_000, insta=5000),
    ]
    scores = engine.score_region(rs)
    assert scores[1]["ad_penalty"] is True
    # 페널티 전 점수(백분위 합)에 ×0.7이 곱해졌는지 역산으로 확인
    base = sum(scores[1]["channel_scores"][ch] * w for ch, w in engine.WEIGHTS.items())
    assert scores[1]["total"] == round(base * engine.AD_PENALTY, 1)


def test_stale_penalty_applied_after_90_days():
    rs = [_restaurant(1, last_mention=120), _restaurant(2)]
    scores = engine.score_region(rs)
    assert scores[1]["stale"] is True
    assert scores[2]["stale"] is False


def test_two_channel_pass_gets_verified_grade():
    # 1번: 블로그·유튜브 상위, 인스타 하위 → 2채널 통과 = 검증
    rs = [
        _restaurant(1, blog=200, videos=10, views=2_000_000, insta=10),
        _restaurant(2, blog=100, videos=5, views=500_000, insta=3000),
        _restaurant(3, blog=10, videos=0, views=0, insta=2000),
    ]
    assert engine.score_region(rs)[1]["grade"] == "검증"


# ---------------------------------------------------------------- 영업 상태

HOURS = {"open": "11:30", "close": "22:00", "break_start": "15:00",
         "break_end": "17:00", "last_order": "21:00", "closed_weekdays": [0]}


def _at(hm, weekday=1):  # 기본 화요일
    # 2026-08-11은 화요일
    h, m = map(int, hm.split(":"))
    return datetime(2026, 8, 10 + weekday, h, m)


def test_open_status_transitions():
    assert engine.open_status(HOURS, _at("10:00"))["code"] == "closed"     # 영업 전
    assert engine.open_status(HOURS, _at("12:00"))["code"] == "open"       # 영업 중
    assert engine.open_status(HOURS, _at("15:30"))["code"] == "break"      # 브레이크타임
    assert engine.open_status(HOURS, _at("20:10"))["code"] == "last_order" # LO 60분 이내
    assert engine.open_status(HOURS, _at("20:10"))["can_eat"] is True
    assert engine.open_status(HOURS, _at("21:30"))["code"] == "closed"     # LO 마감
    assert engine.open_status(HOURS, _at("23:00"))["code"] == "closed"     # 영업 종료
    assert engine.open_status(HOURS, _at("12:00", weekday=0))["can_eat"] is False  # 월요일 휴무


def test_open_status_over_midnight():
    hours = {"open": "18:00", "close": "01:00", "break_start": None,
             "break_end": None, "last_order": "00:00", "closed_weekdays": []}
    assert engine.open_status(hours, _at("19:00"))["code"] == "open"
    assert engine.open_status(hours, _at("23:30"))["code"] == "last_order"
    assert engine.open_status(hours, _at("00:30"))["code"] == "closed"  # LO 마감
    assert engine.open_status(hours, _at("15:00"))["code"] == "closed"  # 영업 전


# ---------------------------------------------------------------- 웹 플로우

def test_home_page():
    res = client.get("/matjib?t=12:30")
    assert res.status_code == 200
    assert "진짜맛집" in res.text


def test_search_lists_region_restaurants():
    res = client.get("/matjib/search", params={"region": "성수동", "t": "12:30"})
    assert res.status_code == 200
    assert "소문난 성수족발" in res.text


def test_search_resolves_alias_and_filters():
    # "강남 맛집" 자유 입력 → 강남역, 일식 필터 → 스시 하루만
    res = client.get("/matjib/search",
                     params={"region": "강남 맛집", "category": "일식", "t": "12:30"})
    assert res.status_code == 200
    assert "스시 하루" in res.text
    assert "마라공방" not in res.text


def test_search_open_now_filter_excludes_break_time():
    # 15:30 성수동: 족발·라멘은 브레이크타임 → "지금 영업 중" 필터에서 제외
    res = client.get("/matjib/search",
                     params={"region": "성수동", "open_now": "1", "t": "15:30"})
    assert res.status_code == 200
    assert "소문난 성수족발" not in res.text
    assert "카페 온도" in res.text  # 브레이크타임 없는 곳은 표시


def test_unknown_region_shows_analyzing_ux():
    res = client.get("/matjib/search", params={"region": "제주도"})
    assert res.status_code == 200
    assert "분석" in res.text


def test_detail_page_shows_cross_validation_report():
    res = client.get("/matjib/r/1", params={"t": "12:30"})
    assert res.status_code == 200
    assert "교차검증 리포트" in res.text
    assert "블로그 후기" in res.text


def test_detail_unknown_id_redirects_home():
    res = client.get("/matjib/r/999", follow_redirects=False)
    assert res.status_code == 307


def test_every_mock_restaurant_detail_renders():
    for r in data.RESTAURANTS:
        assert client.get(f"/matjib/r/{r['id']}").status_code == 200
