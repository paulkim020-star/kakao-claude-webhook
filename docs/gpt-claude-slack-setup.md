# GPT ↔ Claude 대화 + Slack 연동 셋업 가이드

OpenAI GPT와 Anthropic Claude가 주어진 주제로 서로 대화하게 하고, 그 대화를
Slack에서 봇 멘션으로 실행하는 기능입니다.

전체 순서: **① 로컬 대화 테스트 → ② 터미널 결과 확인 → ③ Slack 앱 연결 → ④ 서버 배포**

> ⚠️ Claude가 대신 해줄 수 없는 것(사용자가 직접 해야 하는 것): OpenAI/Anthropic/Slack
> 콘솔에서 **계정 생성·API 키 발급·결제 등록·앱 설치 인증**. 아래에는 "어느 화면에서
> 무엇을 받아 어디에 넣는지"만 안내합니다.

---

## 0. 준비물 (직접 발급)

| 값 | 발급 위치 | 넣는 환경변수 |
|---|---|---|
| OpenAI API 키 | https://platform.openai.com/api-keys → **Create new secret key** | `OPENAI_API_KEY` |
| Anthropic API 키 | https://console.anthropic.com → **Settings → API Keys** | `ANTHROPIC_API_KEY` |
| Slack Signing Secret | Slack 앱 → **Basic Information → App Credentials → Signing Secret** | `SLACK_SIGNING_SECRET` |
| Slack Bot Token | Slack 앱 → **OAuth & Permissions → Bot User OAuth Token** (`xoxb-…`) | `SLACK_BOT_TOKEN` |

선택 환경변수: `OPENAI_MODEL`(기본 `gpt-4o`), `GPT_CLAUDE_MODEL`(기본 `claude-opus-4-8`),
`SLACK_DIALOGUE_ROUNDS`(각 모델 발언 횟수, 기본 `3`).

`.env.example`를 복사해 `.env`로 만들고 키를 채우면 됩니다.

---

## ① 로컬 대화 테스트  → ② 터미널 결과 확인

Slack 없이, 내 PC 터미널에서 GPT ↔ Claude 대화를 바로 확인합니다.

```bash
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...

# "주제" 를 놓고 GPT와 Claude가 3번씩(총 6턴) 대화
python -m gpt_claude.local_test "인공지능의 미래" --rounds 3
```

터미널 출력 예시:

```
=== 주제: 인공지능의 미래 ===

[GPT] AI는 앞으로 일상 업무를 크게 바꿀 겁니다. ...
[Claude] 동의해요. 다만 그 변화가 모두에게 고르게 ...
[GPT] 좋은 지적이에요. 격차 문제를 풀려면 ...
...
```

- `--first Claude` 로 Claude가 먼저 말하게 할 수 있습니다.
- 키가 잘못됐으면 해당 SDK가 인증 에러(401)를 냅니다 — 키를 다시 확인하세요.

---

## ③ Slack 앱 연결

1. **앱 생성**: https://api.slack.com/apps → **Create New App → From scratch** →
   이름/워크스페이스 선택.
2. **권한(Scopes) 추가**: **OAuth & Permissions → Scopes → Bot Token Scopes** 에
   `app_mentions:read`, `chat:write` 추가.
3. **워크스페이스 설치**: 같은 화면 상단 **Install to Workspace** → 승인 →
   `xoxb-…` 로 시작하는 **Bot User OAuth Token** 을 복사해 `SLACK_BOT_TOKEN` 에 넣기.
4. **Signing Secret 복사**: **Basic Information → Signing Secret** 을 `SLACK_SIGNING_SECRET` 에 넣기.
5. **이벤트 구독**: **Event Subscriptions → Enable Events → ON**.
   - **Request URL** 에 `https://<배포주소>/slack/events` 입력.
     서버가 떠 있어야 Slack이 URL 검증(challenge)에 성공합니다 → 먼저 **④ 배포**를 하고
     이 URL을 넣으세요.
   - **Subscribe to bot events** 에 `app_mention` 추가 → **Save Changes**.
6. **봇 초대**: Slack 채널에서 `/invite @봇이름`.

사용법: 채널에서 `@봇이름 인공지능의 미래` 처럼 멘션하면, 봇이 스레드에 GPT와 Claude의
대화를 한 턴씩 올려줍니다.

> Slack은 요청에 3초 안에 응답을 요구하므로, 서버는 즉시 200을 돌려주고 대화 생성은
> 백그라운드에서 처리합니다(중복 재시도는 무시). 서명 검증으로 위조 요청은 차단됩니다.

---

## ④ 서버 배포

이 저장소는 하나의 FastAPI 앱(`main.py`)이며 카카오 웹훅·예약 웹과 함께 Slack 라우터도
`/slack/*` 로 마운트됩니다. 로컬 실행:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

공개 배포(무료 티어 있는 곳): Render / Railway / Fly.io 등. 배포 시 위 환경변수를
설정하고, 발급된 공개 URL 뒤에 `/slack/events` 를 붙여 Slack **Request URL** 로 등록하세요.

배포 없이 잠깐 테스트만 하려면 `ngrok http 8000` 으로 임시 공개 URL을 만들어
`https://xxxx.ngrok.io/slack/events` 를 Request URL 로 써도 됩니다.

---

## 코드 위치

- `gpt_claude/conversation.py` — GPT ↔ Claude 대화 엔진(`run_dialogue`).
- `gpt_claude/local_test.py` — 터미널 테스트 스크립트(①·②).
- `gpt_claude/slack_app.py` — Slack 이벤트 웹훅 라우터(③), `main.py` 에 마운트.
