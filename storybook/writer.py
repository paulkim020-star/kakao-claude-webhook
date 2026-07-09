"""작가 에이전트 - Claude API로 동화 스토리(페이지별 본문 + 장면 묘사)를 생성한다.

동화책 독립 모듈(storybook)의 첫 단계. 주제를 받아 페이지별로
- text: 이야기 본문 (한국어)
- image_prompt: 화가 에이전트(painter.py)에 넘길 영어 이미지 프롬프트
를 담은 구조화된 결과를 돌려준다.
"""
from __future__ import annotations

import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

MODEL = os.environ.get("STORYBOOK_MODEL", os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"))

_SYSTEM_PROMPT = (
    "당신은 따뜻하고 상상력 넘치는 어린이 동화 작가입니다. "
    "어린이가 이해하기 쉬운 문장으로, 기승전결이 있는 이야기를 씁니다."
)

_USER_TEMPLATE = (
    "다음 주제로 어린이 동화를 만들어 주세요.\n\n"
    "주제: {topic}\n\n"
    "요구사항:\n"
    "- 정확히 {pages}개의 페이지로 구성합니다.\n"
    "- 각 페이지는 3~4문장의 한국어 본문(text)을 담습니다.\n"
    "- 각 페이지에는 그 장면을 그림으로 그리기 위한 영어 이미지 프롬프트(image_prompt)를 함께 만듭니다.\n"
    "- image_prompt는 'children's book illustration' 스타일로, 주인공의 외형과 배경을 "
    "구체적으로 묘사하고, 페이지마다 주인공 외형 묘사를 반복해 그림 일관성을 유지합니다.\n\n"
    "반드시 아래 JSON 형식으로만, 다른 설명 없이 응답하세요:\n"
    '{{"title": "동화 제목", "pages": [{{"text": "본문", "image_prompt": "english prompt"}}]}}'
)


def _default_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 필요합니다.")
    return anthropic.Anthropic(api_key=key)


def _extract_json(text: str) -> dict:
    """Claude 응답에서 JSON 객체를 추출한다(코드펜스/잡텍스트 허용)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"응답에서 JSON을 찾지 못했습니다: {text[:200]!r}")
    return json.loads(text[start : end + 1])


def write_story(topic: str, pages: int = 5, *, client: anthropic.Anthropic | None = None) -> dict:
    """주제로 동화를 생성해 {'title': str, 'pages': [{'text','image_prompt'}]} 반환."""
    client = client or _default_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _USER_TEMPLATE.format(topic=topic, pages=pages)}],
    )
    raw = "".join(block.text for block in response.content if block.type == "text").strip()
    story = _extract_json(raw)
    if not story.get("pages"):
        raise ValueError("생성된 동화에 페이지가 없습니다.")
    story.setdefault("title", topic)
    return story
