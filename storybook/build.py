"""동화책 조립 - 작가 에이전트 -> 화가 에이전트 -> 자체 완결형 HTML 동화책 출력."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import painter, writer

logger = logging.getLogger(__name__)

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]),
)


def build_storybook(
    topic: str,
    pages: int = 5,
    out_path: str | Path = "storybook.html",
    *,
    client=None,
) -> Path:
    """주제로 동화책 HTML을 만들어 out_path에 저장하고 경로를 반환."""
    story = writer.write_story(topic, pages, client=client)
    logger.info("작가 완료: '%s' (%d페이지)", story["title"], len(story["pages"]))

    rendered = []
    total = len(story["pages"])
    for i, page in enumerate(story["pages"], 1):
        image_b64 = painter.paint(page["image_prompt"])
        logger.info("화가 %d/%d: %s", i, total, "그림 생성" if image_b64 else "프롬프트 대체")
        rendered.append(
            {
                "text": page.get("text", ""),
                "image_prompt": page.get("image_prompt", ""),
                "image_b64": image_b64,
            }
        )

    html = _env.get_template("book.html").render(
        title=story["title"],
        pages=rendered,
        image_enabled=painter.image_enabled(),
    )
    out_path = Path(out_path)
    out_path.write_text(html, encoding="utf-8")
    logger.info("동화책 저장: %s", out_path)
    return out_path
