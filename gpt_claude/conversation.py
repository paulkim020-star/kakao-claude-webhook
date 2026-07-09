"""
GPT <-> Claude 대화 엔진
========================
OpenAI GPT와 Anthropic Claude가 주어진 주제로 서로 여러 턴 대화하게 만든다.
각 턴마다 지금까지의 대화 내용을 상대 모델에 넘겨 "다음 한 마디"를 생성한다.
두 모델 모두 각자의 공식 SDK(openai / anthropic)로 호출한다.

[필요한 환경변수] (사용자가 직접 발급해서 넣어야 하는 것)
- OPENAI_API_KEY    : https://platform.openai.com/api-keys 에서 발급
- ANTHROPIC_API_KEY : https://console.anthropic.com 에서 발급
- OPENAI_MODEL      : 선택, 기본 gpt-4o
- GPT_CLAUDE_MODEL  : 선택, 기본 claude-opus-4-8
"""
import os
from dataclasses import dataclass
from typing import Callable, Optional

from openai import OpenAI
import anthropic

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
CLAUDE_MODEL = os.environ.get("GPT_CLAUDE_MODEL", "claude-opus-4-8")

# 한 턴에서 각 모델이 생성할 최대 토큰 (짧은 대화용)
_MAX_TOKENS = 400

# SDK 클라이언트는 처음 호출될 때 한 번만 만든다 (키가 없으면 그때 에러가 나도록).
_openai_client: Optional[OpenAI] = None
_anthropic_client: Optional[anthropic.Anthropic] = None


def _openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()  # OPENAI_API_KEY 환경변수 사용
    return _openai_client


def _anthropic() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수 사용
    return _anthropic_client


@dataclass
class Turn:
    speaker: str  # "GPT" 또는 "Claude"
    text: str


def _system_prompt(speaker: str, other: str, topic: str) -> str:
    return (
        f"당신은 '{speaker}'입니다. '{other}'와 '{topic}'에 대해 대화하고 있습니다. "
        f"상대의 말에 반응하며 자신의 생각을 덧붙이세요. "
        f"다음 한 마디만, 2~4문장으로 간결하게 출력하세요."
    )


def _user_prompt(transcript: list[Turn], speaker: str, topic: str) -> str:
    if transcript:
        body = "\n".join(f"{t.speaker}: {t.text}" for t in transcript)
    else:
        body = "(아직 아무도 말하지 않았습니다. 당신이 먼저 대화를 시작하세요.)"
    return (
        f"주제: {topic}\n\n"
        f"지금까지의 대화:\n{body}\n\n"
        f"이제 '{speaker}' 입장에서 다음 한 마디를 하세요."
    )


def _gpt_turn(topic: str, transcript: list[Turn]) -> str:
    resp = _openai().chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[
            {"role": "system", "content": _system_prompt("GPT", "Claude", topic)},
            {"role": "user", "content": _user_prompt(transcript, "GPT", topic)},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _claude_turn(topic: str, transcript: list[Turn]) -> str:
    resp = _anthropic().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_system_prompt("Claude", "GPT", topic),
        messages=[{"role": "user", "content": _user_prompt(transcript, "Claude", topic)}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def run_dialogue(
    topic: str,
    rounds: int = 3,
    first: str = "GPT",
    on_turn: Optional[Callable[[Turn], None]] = None,
) -> list[Turn]:
    """GPT와 Claude가 `rounds`번씩 번갈아 대화한다 (총 rounds*2 턴).

    on_turn 콜백이 있으면 각 턴이 생성될 때마다 즉시 호출한다(실시간 출력/전송용).
    """
    transcript: list[Turn] = []
    order = ["GPT", "Claude"] if first == "GPT" else ["Claude", "GPT"]
    for i in range(rounds * 2):
        speaker = order[i % 2]
        text = _gpt_turn(topic, transcript) if speaker == "GPT" else _claude_turn(topic, transcript)
        turn = Turn(speaker, text)
        transcript.append(turn)
        if on_turn is not None:
            on_turn(turn)
    return transcript
