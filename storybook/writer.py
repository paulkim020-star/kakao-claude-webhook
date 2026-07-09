"""작가 에이전트 - Claude로 동화 페이지(텍스트 + 장면 묘사)를 생성한다.

ANTHROPIC_API_KEY가 없거나 호출에 실패하면, 주제를 그대로 활용한
플레이스홀더 스토리를 돌려줘서 키 없이도 전체 파이프라인이 동작하게 한다.
"""
from __future__ import annotations

import json
import logging
import os

import anthropic

logger = logging.getLogger("storybook.writer")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

_SYSTEM = (
    "너는 어린이 그림 동화책 작가야. 주어진 주제로 따뜻하고 상상력 넘치는 "
    "동화를 만든다. 반드시 JSON만 출력해. 형식:\n"
    '{"title": "제목", "pages": [{"text": "이 페이지의 동화 문장(2~4문장)", '
    '"scene": "이 장면을 그림으로 그리기 위한 영어 묘사"}]}\n'
    "pages 길이는 요청한 페이지 수와 정확히 같아야 하고, scene은 이미지 생성 "
    "API에 넣을 영어 프롬프트(children's storybook illustration, ...)로 쓴다."
)


def _fallback_story(topic: str, pages: int) -> dict:
    """키가 없을 때 쓰는 임시 스토리 - 파이프라인 전체를 돌게 한다."""
    result = []
    for i in range(pages):
        result.append(
            {
                "text": f"({i + 1}쪽) '{topic}'에 대한 동화가 여기에 담깁니다. "
                "Anthropic 키를 넣으면 진짜 이야기가 채워져요.",
                "scene": f"children's storybook illustration about {topic}, "
                f"scene {i + 1}, soft watercolor, warm colors",
            }
        )
    return {"title": f"{topic} 이야기", "pages": result, "fallback": True}


def write_story(topic: str, pages: int = 6) -> dict:
    """주제로 동화책 데이터를 만든다. 반환: {title, pages:[{text, scene}], fallback?}"""
    pages = max(1, min(pages, 12))
    if _client is None:
        return _fallback_story(topic, pages)
    prompt = f"주제: {topic}\n페이지 수: {pages}\n이 주제로 {pages}쪽짜리 동화를 만들어줘."
    try:
        response = _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in response.content if b.type == "text").strip()
        data = _parse(raw)
        if not data.get("pages"):
            raise ValueError("빈 pages")
        return data
    except Exception:
        logger.exception("작가 에이전트 호출 실패 - 플레이스홀더로 대체")
        return _fallback_story(topic, pages)


def _parse(raw: str) -> dict:
    """모델 응답에서 JSON 블록을 추출해 파싱한다."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)
