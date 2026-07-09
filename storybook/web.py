"""동화책 생성/열람 웹 (/storybook).

작가 에이전트로 페이지별 글+장면을 만들고, 화가 에이전트로 각 장면을
그림(또는 플레이스홀더)으로 바꿔 페이지 넘김 HTML 동화책으로 보여준다.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.templating import Jinja2Templates

from .painter import active_provider, paint
from .writer import write_story

router = APIRouter(prefix="/storybook")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("")
def home(request: Request):
    return templates.TemplateResponse(
        request, "home.html", {"provider": active_provider()}
    )


@router.post("/create")
def create(request: Request, topic: str = Form(...), pages: int = Form(6)):
    story = write_story(topic, pages)
    for page in story["pages"]:
        page["image"] = paint(page["scene"])
    return templates.TemplateResponse(
        request,
        "book.html",
        {
            "title": story.get("title", f"{topic} 이야기"),
            "pages": story["pages"],
            "provider": active_provider(),
            "fallback": story.get("fallback", False),
        },
    )
