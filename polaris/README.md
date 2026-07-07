# POLARIS (폴라리스)

> 오늘의 15분이 10년의 나에게 닿는 것을 매일 눈으로 확인하는 앱.

10년 비전 → 5년 이정표 → 연간 목표 → 월간/주간 계획 → 오늘 할 일이 하나의
별자리처럼 연결되는, 미니멀 목표 계층형 투두 앱. 기획서(`POLARIS_기획서 v2`)의
구현체입니다.

이 앱은 저장소의 Python 카카오/예약 서버와 **무관한 독립 프론트엔드**로,
`polaris/` 아래에서 자체 완결됩니다.

## 스택

- React 18 + TypeScript + Vite
- Tailwind CSS (디자인 토큰은 `src/index.css`의 CSS 변수 → `tailwind.config.js` 매핑)
- Zustand + `persist` (localStorage, 서버 불필요)
- 별자리/도넛 차트: 라이브러리 없이 SVG + CSS 애니메이션

## 실행

```bash
cd polaris
npm install
npm run dev      # 개발 서버
npm run build    # 타입체크 + 프로덕션 빌드
npm run preview  # 빌드 결과 미리보기
```

## 문서 (`docs/`)

실제 화면 스크린샷을 담은 자체 완결(single-file) HTML 문서. 브라우저로 바로 엽니다.

- `docs/store.html` — 앱스토어 등록용 소개 페이지 (기능·미리보기·앱 정보)
- `docs/manual.html` — 사용 매뉴얼 (화면별 사용법 + FAQ)

## 구현 범위 (기획서 §5 기준)

- **1단계 MVP** — 오늘 화면(빠른 추가, 핵심 3, 우선순위 자동 정렬, 완료 빛 모션,
  목표 색 점), 연간 목표(5개 하드 리밋)와 태스크-목표 연결, 로컬 저장, 역방향 온보딩
- **2단계** — 주간/월간 뷰, 아침 리추얼, 3회 이월 규칙, 반복 태스크 자동 소멸, 저녁 회고
- **3단계** — 별자리 화면(북극성/이정표/연간 목표, 밝기 = 최근 활동), 5년 이정표 관리,
  10년 비전 작성, 수정 이력, 별 흐려짐(생성 후 2주 경과 시)
- **4단계** — 주간 계획 위저드(인박스→미완료→초점→배분), 요일 드래그·탭 이동,
  프로필/설정, 알림(옵트인·하루 최대 2회), 데이터 내보내기·가져오기(JSON), PWA 설치
- **회고** — 목표 연결 비율을 1순위로 둔 3개 지표, 완료 분포 도넛
- **온보딩 이후** — 3일차(5년 이정표) / 7일차(북극성) 부드러운 초대, 분기 비전 리마인드

> 알림은 서버·푸시가 없어 **앱이 열려 있을 때만** 도착합니다(로컬 스케줄). 이 한계는
> 설정 화면에도 명시돼 있습니다.

## 설계 원칙 (기획서 §1.3 / §1.6)

- **노 스트릭 원칙**: 연속일/붉은 X/"놓쳤어요" 표기 없음. 활동은 '누적 빛'(별 밝기,
  진행 링)으로만 시각화.
- **오늘이 기본값**: 앱을 열면 오늘 화면. 장기 비전은 원할 때만 줌 아웃.
- **입력은 3초**: 텍스트 한 줄 + 별 + 시간 칩 + 목표 점. 날짜 미지정 시 인박스로.
- **최소 자연어 파싱**: "내일/모레/다음주 X요일"만, 결과는 항상 칩으로 표시해 수정 가능.

## 디렉터리

```
public/                  # PWA manifest + 아이콘(SVG)
src/
  types.ts               # 데이터 모델 (§3)
  store.ts               # Zustand 스토어 + 자정 유지보수 + 설정/데이터 입출력
  lib/                   # 날짜, 우선순위 알고리즘, 영역/데일리 문장 메타, 알림 스케줄
  components/            # Card, Checkbox, Stars, TimeChip, ProgressRing, GoalDot,
                         #   QuickAdd, TaskRow, MorningRitual, CarryThriceCard,
                         #   InviteCards, VisionEditor, MilestoneEditor,
                         #   WeeklyPlanner, TabBar
  screens/               # Onboarding, Today, Week, Plan, Constellation,
                         #   Review, Settings
```
