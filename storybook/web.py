"""동화책 생성/열람 웹 (/storybook). 서버 렌더링 페이지."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from storybook import painter, writer
from storybook.db import get_conn, now_kst_str

router = APIRouter(prefix="/storybook")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("")
def storybook_home(request: Request):
    conn = get_conn()
    try:
        books = conn.execute(
            "SELECT * FROM storybook ORDER BY id DESC"
        ).fetchall()
        return templates.TemplateResponse(request, "index.html", {"books": books})
    finally:
        conn.close()


@router.post("/create")
def create_book(request: Request, topic: str = Form(...), pages: int = Form(6)):
    pages = max(3, min(10, pages))
    conn = get_conn()
    try:
        try:
            story = writer.write_story(topic, pages)
        except RuntimeError as exc:
            books = conn.execute(
                "SELECT * FROM storybook ORDER BY id DESC"
            ).fetchall()
            return templates.TemplateResponse(
                request, "index.html", {"books": books, "error": str(exc)}
            )

        cur = conn.execute(
            "INSERT INTO storybook (title, topic, created_at) VALUES (?, ?, ?)",
            (story["title"], topic, now_kst_str()),
        )
        book_id = cur.lastrowid
        for i, page in enumerate(story["pages"], start=1):
            image = painter.paint(page["scene"])
            conn.execute(
                "INSERT INTO storybook_page (book_id, page_no, text, scene, image)"
                " VALUES (?, ?, ?, ?, ?)",
                (book_id, i, page["text"], page["scene"], image),
            )
        return RedirectResponse(url=f"/storybook/book/{book_id}", status_code=303)
    finally:
        conn.close()


@router.get("/book/{book_id}")
def view_book(request: Request, book_id: int):
    conn = get_conn()
    try:
        book = conn.execute(
            "SELECT * FROM storybook WHERE id = ?", (book_id,)
        ).fetchone()
        if book is None:
            return templates.TemplateResponse(
                request, "index.html",
                {"books": conn.execute(
                    "SELECT * FROM storybook ORDER BY id DESC").fetchall(),
                 "error": "동화책을 찾지 못했어요."},
                status_code=404,
            )
        pages = conn.execute(
            "SELECT * FROM storybook_page WHERE book_id = ? ORDER BY page_no",
            (book_id,),
        ).fetchall()
        return templates.TemplateResponse(
            request, "book.html", {"book": book, "pages": pages}
        )
    finally:
        conn.close()
