"""
카카오 i 오픈빌더 <-> Claude API 연동 웹훅 서버
=================================================

이 서버는 카카오 i 오픈빌더의 "스킬(Skill)" 기능에서 호출하는 webhook 엔드포인트입니다.
사용자가 카카오톡 채널(챗봇)에 메시지를 보내면 -> 오픈빌더가 이 서버로 POST 요청 ->
이 서버가 Claude API를 호출 -> 응답을 카카오 스킬 응답 포맷(JSON)으로 돌려줍니다.

[필요한 사전 준비물] (사용자가 직접 해야 하는 것 - Claude가 대신 만들어줄 수 없음)
1. Anthropic API 키 (https://console.anthropic.com 에서 직접 발급)
2. 카카오 i 오픈빌더 계정 + 챗봇 + 카카오톡 채널 (https://i.kakao.com 에서 직접 생성)
3. 이 서버를 인터넷에 공개로 띄울 호스팅 (Render, Railway, Fly.io 등 - 무료 티어 있음)

[실행 방법]
1. pip install -r requirements.txt
2. .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 입력
3. uvicorn main:app --host 0.0.0.0 --port 8000
4. 배포 후 발급되는 공개 URL + "/kakao/webhook" 을 카카오 오픈빌더 스킬의
   웹훅 URL로 등록 (가이드 문서 참고)
"""

import os
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kakao-claude-webhook")

app = FastAPI(title="Kakao <-> Claude Webhook")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "당신은 카카오톡 챗봇으로 응답하는 어시스턴트입니다. "
    "답변은 카카오톡 말풍선에 어울리게 간결하게(3~5문장 이내) 작성하세요.",
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# 사용자별 최근 대화 맥락을 잠깐 기억하기 위한 매우 단순한 인메모리 저장소.
# 운영 환경에서는 Redis 등 외부 저장소로 교체하는 것을 권장합니다.
# (서버 재시작/스케일아웃 시 초기화됩니다)
_conversation_store: dict[str, list[dict[str, str]]] = {}
MAX_HISTORY_TURNS = 6


def _kakao_simple_text_response(text: str) -> dict[str, Any]:
    """카카오 스킬 응답 포맷(simpleText)으로 감싸기."""
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": text}},
            ]
        },
    }


def _extract_user_id_and_utterance(payload: dict[str, Any]) -> tuple[str, str]:
    """카카오 스킬 요청 JSON에서 사용자 ID와 발화 텍스트를 추출."""
    utterance = (
        payload.get("userRequest", {}).get("utterance", "").strip()
    )
    user_id = (
        payload.get("userRequest", {})
        .get("user", {})
        .get("id", "unknown-user")
    )
    return user_id, utterance


@app.get("/")
def health_check():
    return {"status": "ok", "service": "kakao-claude-webhook"}


@app.post("/kakao/webhook")
async def kakao_webhook(request: Request):
    payload = await request.json()
    user_id, utterance = _extract_user_id_and_utterance(payload)

    if not utterance:
        return JSONResponse(
            _kakao_simple_text_response("메시지를 인식하지 못했어요. 다시 말씀해 주세요.")
        )

    if client is None:
        logger.error("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        return JSONResponse(
            _kakao_simple_text_response(
                "서버에 Claude API 키가 설정되어 있지 않아요. 관리자에게 문의해주세요."
            )
        )

    history = _conversation_store.get(user_id, [])
    history.append({"role": "user", "content": utterance})

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=history,
        )
        reply_text = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip() or "응답을 생성하지 못했어요."
    except Exception as exc:  # noqa: BLE001
        logger.exception("Claude API 호출 실패")
        reply_text = f"죄송해요, 처리 중 오류가 발생했어요. ({exc.__class__.__name__})"

    history.append({"role": "assistant", "content": reply_text})
    _conversation_store[user_id] = history[-(MAX_HISTORY_TURNS * 2):]

    # 카카오 스킬 서버는 약 5초 내 응답해야 타임아웃이 나지 않습니다.
    # Claude 응답이 길어질 경우 "콜백 사용하기" 옵션을 오픈빌더에서 켜고
    # useCallback 방식으로 비동기 응답하도록 확장하는 것을 권장합니다.
    return JSONResponse(_kakao_simple_text_response(reply_text))
