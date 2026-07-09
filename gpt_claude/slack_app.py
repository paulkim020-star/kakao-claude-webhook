"""
Slack <-> GPT-Claude 대화 연동
==============================
Slack 채널에서 봇을 멘션하면(@봇 <주제>) GPT와 Claude가 그 주제로 대화하고,
각 발언을 스레드로 실시간 게시한다.

[필요한 환경변수] (사용자가 Slack 앱에서 직접 발급)
- SLACK_SIGNING_SECRET : Slack 앱 Basic Information > Signing Secret
- SLACK_BOT_TOKEN      : Slack 앱 OAuth & Permissions > Bot User OAuth Token (xoxb-...)
  (필요 스코프: app_mentions:read, chat:write)

Slack Event Subscriptions Request URL 로 등록할 주소:
    https://<배포주소>/slack/events

Slack은 3초 안에 200 응답을 받아야 하므로, 실제 대화 생성은 백그라운드에서 처리하고
요청은 즉시 200으로 응답한다.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import time

from fastapi import APIRouter, Request, Response
from slack_sdk import WebClient

from gpt_claude.conversation import Turn, run_dialogue

logger = logging.getLogger("gpt-claude-slack")

SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

# 대화 라운드 수 (각 모델 발언 횟수). 너무 크면 Slack 메시지가 많아진다.
DIALOGUE_ROUNDS = int(os.environ.get("SLACK_DIALOGUE_ROUNDS", "3"))

router = APIRouter(prefix="/slack")
_slack = WebClient(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None

_MENTION_RE = re.compile(r"<@[^>]+>")


def _verify_signature(headers, body: bytes) -> bool:
    """Slack 요청 서명 검증 (변조/위조 요청 차단)."""
    if not SLACK_SIGNING_SECRET:
        return False
    timestamp = headers.get("x-slack-request-timestamp", "")
    signature = headers.get("x-slack-signature", "")
    if not timestamp or not signature:
        return False
    # 재전송 공격 방지: 5분 이상 지난 요청은 거부
    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
    except ValueError:
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    computed = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"), base, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def _post(channel: str, thread_ts: str, text: str) -> None:
    if _slack is None:
        return
    _slack.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)


async def _run_and_post(topic: str, channel: str, thread_ts: str) -> None:
    """백그라운드로 GPT-Claude 대화를 돌리고 각 발언을 스레드에 게시."""
    if _slack is None:
        logger.error("SLACK_BOT_TOKEN이 설정되지 않아 메시지를 보낼 수 없습니다.")
        return
    if not topic:
        await asyncio.to_thread(
            _post, channel, thread_ts,
            "대화 주제를 함께 적어주세요. 예: `@봇 인공지능의 미래`",
        )
        return

    await asyncio.to_thread(
        _post, channel, thread_ts,
        f":speech_balloon: *{topic}* 에 대해 GPT와 Claude가 대화를 시작합니다…",
    )

    def on_turn(turn: Turn) -> None:
        emoji = ":large_green_circle:" if turn.speaker == "GPT" else ":large_purple_circle:"
        _post(channel, thread_ts, f"{emoji} *{turn.speaker}*: {turn.text}")

    try:
        await asyncio.to_thread(
            run_dialogue, topic, DIALOGUE_ROUNDS, "GPT", on_turn
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("GPT-Claude 대화 처리 실패")
        await asyncio.to_thread(
            _post, channel, thread_ts,
            f"처리 중 오류가 발생했어요. ({exc.__class__.__name__})",
        )


@router.post("/events")
async def slack_events(request: Request):
    body = await request.body()

    if not _verify_signature(request.headers, body):
        return Response(status_code=401)

    payload = json.loads(body)

    # 1) Event Subscriptions 최초 등록 시 URL 검증
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # 2) Slack 재시도(중복 전달)는 무시 - 대화가 중복 생성되지 않도록
    if request.headers.get("x-slack-retry-num"):
        return Response(status_code=200)

    event = payload.get("event", {})
    # 봇 자신이 올린 메시지에는 반응하지 않음
    if event.get("type") == "app_mention" and not event.get("bot_id"):
        topic = _MENTION_RE.sub("", event.get("text", "")).strip()
        channel = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]
        # 3초 제한 안에 200을 돌려주고, 실제 작업은 백그라운드로
        asyncio.create_task(_run_and_post(topic, channel, thread_ts))

    return Response(status_code=200)
