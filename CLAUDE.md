# CLAUDE.md

This file guides Claude Code when working in this repository.

## Project Overview

A FastAPI webhook server that bridges Kakao i 오픈빌더 (Kakao's chatbot builder) skills
with the Claude API. Flow: KakaoTalk user message -> Kakao Open Builder -> POST
`/kakao/webhook` -> this server calls Claude -> response is wrapped in Kakao's
skill response JSON format (`simpleText`) and returned.

- `main.py` - FastAPI app entry point (Kakao payload parsing, Claude call,
  in-memory per-user conversation history, booking router mounting).
- `booking/` - 미용실(1인샵) 예약 시스템 모듈. SQLite 기반. 고객용 예약 웹
  (`/booking`), 관리자 웹 (`/admin`, HTTP Basic - `ADMIN_PASSWORD` env),
  슬롯 계산/충돌 방지(`engine.py`), 리마인드 알림 스케줄러(`notify.py`).
  기획 배경은 `docs/살롱예약시스템-기획안.md` 참고.
- `storybook/` - 동화책 생성 모듈. 작가 에이전트(`writer.py`, Claude가 페이지별
  이야기 + 삽화 프롬프트 생성)와 화가 에이전트(`painter.py`, 이미지 API 호출,
  키 없으면 SVG 플레이스홀더로 그레이스풀 폴백)로 그림 동화를 만들어 페이지별
  HTML로 보여줌(`/storybook`). SQLite 기반(`db.py`, 이미지는 data URL로 저장).
- `tests/` - pytest 테스트 (슬롯 계산, 예약 충돌, 웹 플로우).
- `requirements.txt` - pinned dependencies (fastapi, uvicorn, anthropic, httpx,
  python-dotenv, jinja2, python-multipart).

### Running locally

```
pip install -r requirements.txt
# .env with ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --host 0.0.0.0 --port 8000
# tests: pip install -r requirements-dev.txt && pytest
```

Booking env vars: `BOOKING_DB` (SQLite path, default `booking.db`),
`ADMIN_PASSWORD` (admin Basic auth), `BOOKING_BASE_URL` (챗봇이 안내하는
예약 페이지 공개 URL), `KAKAO_CHANNEL_URL` (선택 - 카카오톡 채널 1:1 채팅 URL,
설정 시 웹에 문의 버튼 노출 + 챗봇이 상담 발화를 원장 직접 응대로 안내),
`INSTAGRAM_URL` (선택 - 매장 인스타그램, 설정 시 웹에 SNS 링크 노출).
동시간대 예약은 첫 손님 자동 확정, 2~3번째는 pending(원장 승인제) -
`engine.MAX_OVERLAP` 참고.
소셜 로그인(선택, `booking/auth.py`):
`KAKAO_CLIENT_ID`/`KAKAO_CLIENT_SECRET`, `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`,
`SESSION_SECRET` - 키가 없는 제공자는 로그인 버튼이 숨겨지고 비회원 예약만 동작.
사진(`booking/photos.py`): `PHOTO_DIR` (기본 `photos/`) - 고객 희망 스타일 사진과
시술 결과 사진(정면/측면/뒷면) 저장 폴더. 사진은 반드시 인증 라우트로만 서빙
(고객: 본인 예약 확인, 관리자: Basic 인증). 정적 경로로 공개 금지.

Storybook env vars: `STORYBOOK_DB` (SQLite path, default `storybook.db`),
`IMAGE_API_PROVIDER` (기본 `openai`), `OPENAI_API_KEY` (선택 - 없으면 삽화는 SVG
플레이스홀더로 대체, 동화 텍스트는 정상 생성), `STORYBOOK_IMAGE_SIZE`
(기본 `1024x1024`). 작가 에이전트는 `ANTHROPIC_API_KEY`/`CLAUDE_MODEL` 공용.

### Key constraints to keep in mind

- Kakao's skill server expects a response within ~5 seconds, or it times out. Don't
  add slow synchronous work to the webhook path without considering Kakao's
  `useCallback` async response option.
- Conversation history is a plain in-memory dict (`_conversation_store`), capped at
  `MAX_HISTORY_TURNS`. It resets on restart/scale-out - this is a known, accepted
  limitation for this simple deployment, not a bug to silently "fix" with Redis
  unless asked.
- `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, and `SYSTEM_PROMPT` are configured via
  environment variables with defaults in `main.py`.

## Working Guidelines

These behavioral guidelines reduce common LLM coding mistakes. They bias toward
caution over speed - use judgment on trivial tasks.

### 1. Think Before Coding

Don't assume, don't hide confusion, surface tradeoffs.

- State assumptions explicitly before implementing. If uncertain, ask.
- If multiple interpretations exist, present them - don't silently pick one.
- If a simpler approach exists, say so and push back when warranted.
- If something is unclear, stop, name what's confusing, and ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for scenarios that can't happen.
- If a change could be much shorter, rewrite it shorter.

Ask: "Would a senior engineer call this overcomplicated?" If yes, simplify.

### 3. Surgical Changes

Touch only what you must; clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style (including this file's Korean comments in `main.py`), even
  if you'd write it differently.
- If you notice unrelated dead code, mention it - don't delete it unasked.
- Remove imports/variables/functions that your own change made unused; leave
  pre-existing dead code alone.
- Every changed line should trace directly to the request.

### 4. Goal-Driven Execution

Define success criteria, then loop until verified.

- "Add validation" -> write tests/checks for invalid inputs, then make them pass.
- "Fix the bug" -> reproduce it first, then verify the fix resolves it.
- "Refactor X" -> confirm behavior is unchanged before and after.
- For multi-step tasks, state a brief plan with a verification step per item, e.g.:

```
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
```

Since this repo currently has no automated tests, verification for webhook changes
means manually exercising `/kakao/webhook` (e.g. with `curl` or `httpx`) against a
sample Kakao payload, not just reading the code.
