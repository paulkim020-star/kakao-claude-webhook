"""작가 에이전트: Claude로 페이지별 이야기 + 삽화 프롬프트를 생성."""

import json
import logging
import os

import anthropic

logger = logging.getLogger("storybook.writer")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

WRITER_SYSTEM = (
    "당신은 어린이 그림책 작가입니다. 3~7세 아이가 부모와 함께 읽는 따뜻하고 "
    "상상력 넘치는 동화를 씁니다. 문장은 쉽고 리듬감 있게, 페이지마다 하나의 "
    "장면이 그려지도록 씁니다. 폭력적이거나 무서운 내용은 넣지 않습니다."
)


def write_story(topic: str, num_pages: int = 6) -> dict:
    """주제로 동화를 생성. {"title": str, "pages": [{"text", "scene"}, ...]} 반환."""
    if _client is None:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    prompt = (
        f'"{topic}"을(를) 주제로 {num_pages}페이지 분량의 한국어 어린이 동화를 써 주세요.\n'
        "반드시 아래 형식의 JSON만 출력하세요 (다른 말은 절대 붙이지 마세요):\n"
        '{"title": "동화 제목", "pages": [\n'
        '  {"text": "한 페이지 분량의 이야기(2~4문장, 한국어)",'
        ' "scene": "this page\'s illustration prompt in English,'
        ' describe characters/background/mood"}\n'
        "]}\n"
        f'"pages" 배열은 정확히 {num_pages}개여야 합니다. "text"는 한국어 이야기, '
        '"scene"은 이미지 생성 모델용 영어 프롬프트입니다(영어가 결과가 더 좋습니다).'
    )

    response = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=WRITER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    # ```json 코드펜스가 붙어오면 벗겨냄
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("작가 응답 JSON 파싱 실패: %s", raw[:200])
        raise RuntimeError("동화 생성 응답을 해석하지 못했어요. 다시 시도해 주세요.")

    title = data.get("title")
    pages = data.get("pages")
    if not isinstance(title, str) or not title.strip():
        raise RuntimeError("동화 생성 응답에 제목이 없습니다. 다시 시도해 주세요.")
    if not isinstance(pages, list) or not pages:
        raise RuntimeError("동화 생성 응답에 페이지가 없습니다. 다시 시도해 주세요.")

    clean_pages = []
    for p in pages:
        if not isinstance(p, dict):
            continue
        text = str(p.get("text", "")).strip()
        scene = str(p.get("scene", "")).strip()
        if text and scene:
            clean_pages.append({"text": text, "scene": scene})
    if not clean_pages:
        raise RuntimeError("동화 생성 응답이 비어 있습니다. 다시 시도해 주세요.")

    return {"title": title.strip(), "pages": clean_pages}
