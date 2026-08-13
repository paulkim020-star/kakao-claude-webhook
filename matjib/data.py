"""
맛집찾기(진짜맛집) 프로토타입 목업 데이터.

실서비스에서는 배치 수집기가 카카오 로컬 → 네이버 블로그 → 유튜브 → 인스타(간접)
순으로 신호를 모아 DB에 저장하지만, 프로토타입은 "수집이 끝난 상태"를 가정한
목업 신호를 여기에 둔다. 구조는 기획안 7장(데이터 모델)의 Restaurant + Score
신호 + OpeningHours + Reservation을 합친 형태.

가게 이름은 전부 가상이다 (실존 상호 아님).
"""

# 기획안 3장: 대분류 7개
CATEGORIES = ["한식", "중식", "일식", "양식", "아시안", "카페·디저트", "술집·바"]

# 콜드 스타트 대응: 인기 지역부터 미리 수집 (기획안 10장)
REGIONS = {
    "성수동": {"lat": 37.5446, "lng": 127.0559},
    "강남역": {"lat": 37.4979, "lng": 127.0276},
    "홍대": {"lat": 37.5563, "lng": 126.9236},
}

# 검색어 → 지역 매핑 ("성수", "성수동 맛집" 등 자유 입력 흡수)
REGION_ALIASES = {"성수": "성수동", "강남": "강남역", "홍대": "홍대", "연남": "홍대"}

PRICE_LABELS = {1: "₩ 1만 미만", 2: "₩₩ 1~3만", 3: "₩₩₩ 3~7만", 4: "₩₩₩₩ 7만 이상"}

# signals 구조 (채널별 수집 신호 - 기획안 4.2):
#   blog:    최근 6개월 리뷰 수 / 긍정 표현 비율 / "협찬·광고" 언급 비율(감점 재료)
#   youtube: 언급 영상 수 / 조회수 합
#   insta:   해시태그 게시물 수 (간접 수집, 하루 1회 배치 갱신 가정)
#   rating:  지도 평점 / 리뷰 수
#   last_mention_days: 마지막 언급 경과일 (신선도 가중 재료)
RESTAURANTS = [
    # ---- 성수동 ----
    {
        "id": 1, "name": "소문난 성수족발", "region": "성수동",
        "category": "한식", "sub_category": "고기·구이",
        "lat": 37.5449, "lng": 127.0587, "address": "성동구 성수이로 12",
        "price_tier": 2, "phone": "02-555-0101",
        "hours": {"open": "11:30", "close": "22:00", "break_start": "15:00",
                  "break_end": "17:00", "last_order": "21:00", "closed_weekdays": [0]},
        "signals": {
            "blog": {"review_count_6m": 128, "positive_ratio": 0.84, "sponsored_ratio": 0.06},
            "youtube": {"video_count": 6, "total_views": 840_000},
            "insta": {"hashtag_posts": 2_400},
            "rating": {"avg": 4.4, "review_count": 512},
            "last_mention_days": 8,
        },
        "reservation": {"naver_booking_url": "https://booking.naver.com", "catchtable_url": None},
        "signature": [["앞다리 족발(중)", 33000], ["막국수", 8000]],
    },
    {
        "id": 2, "name": "라멘 코야", "region": "성수동",
        "category": "일식", "sub_category": "라멘·우동",
        "lat": 37.5432, "lng": 127.0545, "address": "성동구 연무장길 41",
        "price_tier": 2, "phone": "02-555-0102",
        "hours": {"open": "11:00", "close": "21:00", "break_start": "15:30",
                  "break_end": "17:00", "last_order": "20:30", "closed_weekdays": [1]},
        "signals": {
            "blog": {"review_count_6m": 96, "positive_ratio": 0.88, "sponsored_ratio": 0.04},
            "youtube": {"video_count": 9, "total_views": 1_920_000},
            "insta": {"hashtag_posts": 1_850},
            "rating": {"avg": 4.6, "review_count": 340},
            "last_mention_days": 3,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["돈코츠 라멘", 11000], ["차슈덮밥", 9000]],
    },
    {
        "id": 3, "name": "카페 온도", "region": "성수동",
        "category": "카페·디저트", "sub_category": "베이커리",
        "lat": 37.5461, "lng": 127.0571, "address": "성동구 서울숲길 17",
        "price_tier": 1, "phone": "02-555-0103",
        "hours": {"open": "10:00", "close": "21:00", "break_start": None,
                  "break_end": None, "last_order": "20:30", "closed_weekdays": []},
        "signals": {
            "blog": {"review_count_6m": 74, "positive_ratio": 0.79, "sponsored_ratio": 0.12},
            "youtube": {"video_count": 1, "total_views": 42_000},
            "insta": {"hashtag_posts": 5_200},
            "rating": {"avg": 4.3, "review_count": 610},
            "last_mention_days": 5,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["소금빵", 3800], ["아인슈페너", 6000]],
    },
    {
        "id": 4, "name": "트라토리아 몬테", "region": "성수동",
        "category": "양식", "sub_category": "이탈리안",
        "lat": 37.5438, "lng": 127.0602, "address": "성동구 상원길 8",
        "price_tier": 3, "phone": "02-555-0104",
        "hours": {"open": "11:30", "close": "22:00", "break_start": "15:00",
                  "break_end": "17:30", "last_order": "21:00", "closed_weekdays": [0]},
        "signals": {
            # 협찬 비율 42% → 광고 페널티(×0.7) 대상 (기획안 4.3)
            "blog": {"review_count_6m": 150, "positive_ratio": 0.90, "sponsored_ratio": 0.42},
            "youtube": {"video_count": 4, "total_views": 260_000},
            "insta": {"hashtag_posts": 3_100},
            "rating": {"avg": 4.1, "review_count": 220},
            "last_mention_days": 15,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": "https://app.catchtable.co.kr"},
        "signature": [["트러플 크림 파스타", 24000], ["마르게리타", 19000]],
    },
    {
        "id": 5, "name": "성수 옛날분식", "region": "성수동",
        "category": "한식", "sub_category": "분식",
        "lat": 37.5421, "lng": 127.0533, "address": "성동구 뚝섬로 220",
        "price_tier": 1, "phone": "02-555-0105",
        "hours": {"open": "10:30", "close": "20:00", "break_start": None,
                  "break_end": None, "last_order": "19:30", "closed_weekdays": [6]},
        "signals": {
            "blog": {"review_count_6m": 41, "positive_ratio": 0.81, "sponsored_ratio": 0.02},
            "youtube": {"video_count": 0, "total_views": 0},
            "insta": {"hashtag_posts": 210},
            "rating": {"avg": 4.5, "review_count": 95},
            "last_mention_days": 21,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["떡볶이", 4500], ["김말이", 3000]],
    },
    {
        "id": 6, "name": "바 이스트엔드", "region": "성수동",
        "category": "술집·바", "sub_category": "와인바",
        "lat": 37.5455, "lng": 127.0611, "address": "성동구 성수일로 99",
        "price_tier": 3, "phone": "02-555-0106",
        "hours": {"open": "18:00", "close": "01:00", "break_start": None,
                  "break_end": None, "last_order": "00:00", "closed_weekdays": [0]},
        "signals": {
            # 최근 3개월 언급 없음 → 신선도 가중(×0.8) 대상 (기획안 4.3)
            "blog": {"review_count_6m": 62, "positive_ratio": 0.77, "sponsored_ratio": 0.10},
            "youtube": {"video_count": 2, "total_views": 98_000},
            "insta": {"hashtag_posts": 1_400},
            "rating": {"avg": 4.2, "review_count": 180},
            "last_mention_days": 130,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": "https://app.catchtable.co.kr"},
        "signature": [["글라스 와인", 12000], ["치즈 플레이트", 28000]],
    },

    # ---- 강남역 ----
    {
        "id": 7, "name": "스시 하루", "region": "강남역",
        "category": "일식", "sub_category": "스시·오마카세",
        "lat": 37.4991, "lng": 127.0295, "address": "강남구 테헤란로1길 15",
        "price_tier": 4, "phone": "02-555-0107",
        "hours": {"open": "12:00", "close": "22:00", "break_start": "15:00",
                  "break_end": "18:00", "last_order": "20:30", "closed_weekdays": [6]},
        "signals": {
            "blog": {"review_count_6m": 210, "positive_ratio": 0.91, "sponsored_ratio": 0.08},
            "youtube": {"video_count": 12, "total_views": 3_400_000},
            "insta": {"hashtag_posts": 4_800},
            "rating": {"avg": 4.7, "review_count": 730},
            "last_mention_days": 2,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": "https://app.catchtable.co.kr"},
        "signature": [["런치 오마카세", 88000], ["디너 오마카세", 160000]],
    },
    {
        "id": 8, "name": "마라공방", "region": "강남역",
        "category": "중식", "sub_category": "마라·훠궈",
        "lat": 37.4968, "lng": 127.0301, "address": "강남구 강남대로84길 6",
        "price_tier": 2, "phone": "02-555-0108",
        "hours": {"open": "11:00", "close": "23:00", "break_start": None,
                  "break_end": None, "last_order": "22:00", "closed_weekdays": []},
        "signals": {
            "blog": {"review_count_6m": 88, "positive_ratio": 0.80, "sponsored_ratio": 0.14},
            "youtube": {"video_count": 3, "total_views": 310_000},
            "insta": {"hashtag_posts": 1_600},
            "rating": {"avg": 4.2, "review_count": 410},
            "last_mention_days": 9,
        },
        "reservation": {"naver_booking_url": "https://booking.naver.com", "catchtable_url": None},
        "signature": [["마라탕(1인)", 12000], ["꿔바로우", 16000]],
    },
    {
        "id": 9, "name": "버거 리퍼블릭", "region": "강남역",
        "category": "양식", "sub_category": "스테이크·버거",
        "lat": 37.5002, "lng": 127.0262, "address": "서초구 서초대로77길 3",
        "price_tier": 2, "phone": "02-555-0109",
        "hours": {"open": "11:00", "close": "21:30", "break_start": None,
                  "break_end": None, "last_order": "21:00", "closed_weekdays": []},
        "signals": {
            "blog": {"review_count_6m": 105, "positive_ratio": 0.83, "sponsored_ratio": 0.09},
            "youtube": {"video_count": 7, "total_views": 1_150_000},
            "insta": {"hashtag_posts": 2_900},
            "rating": {"avg": 4.4, "review_count": 520},
            "last_mention_days": 6,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["시그니처 치즈버거", 13500], ["트러플 감자튀김", 7000]],
    },
    {
        "id": 10, "name": "남도밥상", "region": "강남역",
        "category": "한식", "sub_category": "백반·정식",
        "lat": 37.4955, "lng": 127.0288, "address": "서초구 서운로 12",
        "price_tier": 1, "phone": "02-555-0110",
        "hours": {"open": "11:00", "close": "20:30", "break_start": "14:30",
                  "break_end": "17:00", "last_order": "20:00", "closed_weekdays": [6]},
        "signals": {
            "blog": {"review_count_6m": 35, "positive_ratio": 0.86, "sponsored_ratio": 0.03},
            "youtube": {"video_count": 1, "total_views": 28_000},
            "insta": {"hashtag_posts": 150},
            "rating": {"avg": 4.5, "review_count": 130},
            "last_mention_days": 30,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["제육 백반", 9000], ["갈치조림 정식", 14000]],
    },
    {
        "id": 11, "name": "포 사이공", "region": "강남역",
        "category": "아시안", "sub_category": "베트남",
        "lat": 37.4985, "lng": 127.0250, "address": "서초구 강남대로 361",
        "price_tier": 1, "phone": "02-555-0111",
        "hours": {"open": "10:30", "close": "21:00", "break_start": "15:00",
                  "break_end": "16:30", "last_order": "20:30", "closed_weekdays": []},
        "signals": {
            "blog": {"review_count_6m": 67, "positive_ratio": 0.82, "sponsored_ratio": 0.07},
            "youtube": {"video_count": 2, "total_views": 180_000},
            "insta": {"hashtag_posts": 980},
            "rating": {"avg": 4.3, "review_count": 290},
            "last_mention_days": 11,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["양지 쌀국수", 9500], ["분짜", 12000]],
    },
    {
        "id": 12, "name": "위스키 라이브러리", "region": "강남역",
        "category": "술집·바", "sub_category": "위스키바",
        "lat": 37.4972, "lng": 127.0310, "address": "강남구 역삼로3길 20",
        "price_tier": 4, "phone": "02-555-0112",
        "hours": {"open": "19:00", "close": "02:00", "break_start": None,
                  "break_end": None, "last_order": "01:00", "closed_weekdays": [0]},
        "signals": {
            "blog": {"review_count_6m": 28, "positive_ratio": 0.75, "sponsored_ratio": 0.11},
            "youtube": {"video_count": 0, "total_views": 0},
            "insta": {"hashtag_posts": 640},
            "rating": {"avg": 4.1, "review_count": 88},
            "last_mention_days": 44,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": "https://app.catchtable.co.kr"},
        "signature": [["하이볼", 15000], ["싱글몰트 글라스", 25000]],
    },

    # ---- 홍대 ----
    {
        "id": 13, "name": "연남 화로곱창", "region": "홍대",
        "category": "한식", "sub_category": "고기·구이",
        "lat": 37.5602, "lng": 126.9225, "address": "마포구 성미산로 190",
        "price_tier": 2, "phone": "02-555-0113",
        "hours": {"open": "16:00", "close": "24:00", "break_start": None,
                  "break_end": None, "last_order": "23:00", "closed_weekdays": [0]},
        "signals": {
            "blog": {"review_count_6m": 142, "positive_ratio": 0.85, "sponsored_ratio": 0.05},
            "youtube": {"video_count": 8, "total_views": 2_100_000},
            "insta": {"hashtag_posts": 3_300},
            "rating": {"avg": 4.5, "review_count": 460},
            "last_mention_days": 4,
        },
        "reservation": {"naver_booking_url": "https://booking.naver.com", "catchtable_url": None},
        "signature": [["모둠곱창(중)", 38000], ["볶음밥", 4000]],
    },
    {
        "id": 14, "name": "타이 바질", "region": "홍대",
        "category": "아시안", "sub_category": "태국",
        "lat": 37.5551, "lng": 126.9219, "address": "마포구 와우산로 105",
        "price_tier": 2, "phone": "02-555-0114",
        "hours": {"open": "11:30", "close": "21:30", "break_start": "15:00",
                  "break_end": "17:00", "last_order": "21:00", "closed_weekdays": [1]},
        "signals": {
            "blog": {"review_count_6m": 71, "positive_ratio": 0.84, "sponsored_ratio": 0.10},
            "youtube": {"video_count": 3, "total_views": 240_000},
            "insta": {"hashtag_posts": 1_250},
            "rating": {"avg": 4.4, "review_count": 260},
            "last_mention_days": 7,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["팟타이", 12000], ["푸팟퐁커리", 26000]],
    },
    {
        "id": 15, "name": "딤섬당", "region": "홍대",
        "category": "중식", "sub_category": "딤섬",
        "lat": 37.5570, "lng": 126.9258, "address": "마포구 홍익로 22",
        "price_tier": 2, "phone": "02-555-0115",
        "hours": {"open": "11:30", "close": "21:00", "break_start": "15:00",
                  "break_end": "17:00", "last_order": "20:20", "closed_weekdays": []},
        "signals": {
            "blog": {"review_count_6m": 58, "positive_ratio": 0.80, "sponsored_ratio": 0.13},
            "youtube": {"video_count": 2, "total_views": 130_000},
            "insta": {"hashtag_posts": 1_700},
            "rating": {"avg": 4.2, "review_count": 310},
            "last_mention_days": 13,
        },
        "reservation": {"naver_booking_url": "https://booking.naver.com", "catchtable_url": None},
        "signature": [["샤오롱바오(6pc)", 9000], ["새우 하가우", 8500]],
    },
    {
        "id": 16, "name": "브런치클럽 연남", "region": "홍대",
        "category": "카페·디저트", "sub_category": "브런치카페",
        "lat": 37.5615, "lng": 126.9242, "address": "마포구 동교로 250",
        "price_tier": 2, "phone": "02-555-0116",
        "hours": {"open": "09:00", "close": "18:00", "break_start": None,
                  "break_end": None, "last_order": "17:00", "closed_weekdays": [2]},
        "signals": {
            # 협찬 비율 35% → 광고 페널티 대상
            "blog": {"review_count_6m": 118, "positive_ratio": 0.88, "sponsored_ratio": 0.35},
            "youtube": {"video_count": 1, "total_views": 55_000},
            "insta": {"hashtag_posts": 4_100},
            "rating": {"avg": 4.0, "review_count": 350},
            "last_mention_days": 10,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["리코타 팬케이크", 15000], ["에그 베네딕트", 16500]],
    },
    {
        "id": 17, "name": "카츠 텐", "region": "홍대",
        "category": "일식", "sub_category": "돈카츠·규동",
        "lat": 37.5540, "lng": 126.9227, "address": "마포구 어울마당로 55",
        "price_tier": 1, "phone": "02-555-0117",
        "hours": {"open": "11:00", "close": "21:00", "break_start": "15:30",
                  "break_end": "16:30", "last_order": "20:30", "closed_weekdays": []},
        "signals": {
            "blog": {"review_count_6m": 93, "positive_ratio": 0.87, "sponsored_ratio": 0.04},
            "youtube": {"video_count": 5, "total_views": 890_000},
            "insta": {"hashtag_posts": 2_050},
            "rating": {"avg": 4.6, "review_count": 400},
            "last_mention_days": 6,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["로스카츠 정식", 11000], ["치즈카츠", 13000]],
    },
    {
        "id": 18, "name": "펍 홉하우스", "region": "홍대",
        "category": "술집·바", "sub_category": "포차·펍",
        "lat": 37.5535, "lng": 126.9250, "address": "마포구 잔다리로 33",
        "price_tier": 2, "phone": "02-555-0118",
        "hours": {"open": "17:00", "close": "02:00", "break_start": None,
                  "break_end": None, "last_order": "01:00", "closed_weekdays": []},
        "signals": {
            "blog": {"review_count_6m": 22, "positive_ratio": 0.72, "sponsored_ratio": 0.05},
            "youtube": {"video_count": 0, "total_views": 0},
            "insta": {"hashtag_posts": 480},
            "rating": {"avg": 4.0, "review_count": 140},
            "last_mention_days": 26,
        },
        "reservation": {"naver_booking_url": None, "catchtable_url": None},
        "signature": [["수제 IPA", 8000], ["피시앤칩스", 17000]],
    },
]


def resolve_region(query: str) -> str | None:
    """자유 입력 검색어("성수동 맛집", "강남" 등)를 서비스 지역명으로 변환.

    매칭 실패 시 None → 미수집 지역이므로 "분석 중" UX로 응답 (기획안 10장 콜드 스타트).
    """
    q = query.strip()
    if not q:
        return None
    if q in REGIONS:
        return q
    for alias, region in REGION_ALIASES.items():
        if alias in q:
            return region
    return None


def by_region(region: str) -> list[dict]:
    return [r for r in RESTAURANTS if r["region"] == region]


def by_id(rid: int) -> dict | None:
    return next((r for r in RESTAURANTS if r["id"] == rid), None)
