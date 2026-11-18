"""웹 EPUB 리더: 서재에 보관된 EPUB을 장 단위로 읽는다.

서버가 EPUB(ZIP)을 읽어 장 HTML을 만들어 주므로 외부 리더 라이브러리가 필요 없다.
EPUB 안의 내용은 올린 문서에서 왔으므로, 허용한 태그/속성만 남기고 나머지
(script, 이벤트 속성, javascript: 링크 등)는 걸러서 보여준다.
"""

import html
import mimetypes
import posixpath
import re
import zipfile
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from lxml import etree
from lxml import html as lxml_html
from pydantic import BaseModel, Field

from ebook.db import book_dir, get_conn
from ebook.web import _login_redirect, _own_book, current_user, templates

router = APIRouter()

ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr", "strong", "b", "em", "i", "u", "sub",
    "sup", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td", "img", "blockquote",
    "span", "div", "a",
}
DROP_WITH_CONTENT = ("script", "style", "iframe", "object", "embed", "form", "input", "button",
                     "textarea", "select", "svg", "math", "link", "meta", "title")
ALLOWED_ATTRS = {"img": {"src", "alt"}, "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"},
                 "a": {"href"}}
SAFE_HREF = re.compile(r"^(https?:|mailto:|#)", re.I)
IMAGE_EXT = {"png", "jpg", "jpeg", "gif"}  # svg는 문서로 열리면 스크립트가 돌 수 있어 제외


@dataclass
class Chapter:
    title: str
    html: str
    chars: int  # 진행률 계산용 글자 수


def _spine_files(zf: zipfile.ZipFile) -> list[str]:
    container = etree.fromstring(zf.read("META-INF/container.xml"))
    opf_path = container.find(".//{*}rootfile").get("full-path")
    opf = etree.fromstring(zf.read(opf_path))
    base = posixpath.dirname(opf_path)
    manifest = {item.get("id"): item for item in opf.iterfind(".//{*}manifest/{*}item")}
    files = []
    for ref in opf.iterfind(".//{*}spine/{*}itemref"):
        item = manifest.get(ref.get("idref"))
        if item is None or "nav" in (item.get("properties") or "").split():
            continue
        files.append(posixpath.normpath(posixpath.join(base, item.get("href"))))
    return files


def _clean(body, chapter_path: str, names: set[str], book_id: int) -> str:
    etree.strip_elements(body, *DROP_WITH_CONTENT, etree.Comment, etree.ProcessingInstruction,
                         with_tail=False)
    unknown = {el.tag for el in body.iterdescendants() if el.tag not in ALLOWED_TAGS}
    etree.strip_tags(body, *unknown)  # 모르는 태그는 벗기고 글자만 남긴다
    for el in list(body.iterdescendants()):
        allowed = ALLOWED_ATTRS.get(el.tag, set())
        for attr in list(el.attrib):
            if attr not in allowed:
                del el.attrib[attr]
        if el.tag == "a" and not SAFE_HREF.match(el.get("href", "")):
            el.attrib.pop("href", None)
        if el.tag == "img":
            target = posixpath.normpath(posixpath.join(posixpath.dirname(chapter_path),
                                                       el.get("src", "")))
            if target in names and target.rsplit(".", 1)[-1].lower() in IMAGE_EXT:
                el.set("src", f"/book/{book_id}/asset/{target}")
                el.set("loading", "lazy")
            else:
                el.drop_tree()
    text = html.escape(body.text) if body.text else ""
    inner = "".join(etree.tostring(child, encoding="unicode", method="html") for child in body)
    return text + inner


def load_chapters(epub_path, book_id: int) -> list[Chapter]:
    with zipfile.ZipFile(epub_path) as zf:
        names = set(zf.namelist())
        chapters = []
        for path in _spine_files(zf):
            doc = lxml_html.document_fromstring(zf.read(path))
            title = (doc.findtext(".//title") or "").strip() or f"{len(chapters) + 1}장"
            chars = len(doc.body.text_content().strip())
            chapters.append(Chapter(title, _clean(doc.body, path, names, book_id), chars))
        return chapters


def _weights(chapters: list[Chapter]) -> list[tuple[float, float]]:
    """장마다 (시작 %, 차지하는 %) - 글자 수 비례."""
    total = sum(c.chars for c in chapters) or 1
    out, start = [], 0.0
    for c in chapters:
        span = 100 * c.chars / total
        out.append((start, span))
        start += span
    return out


def _epub(user_id: int, book) -> str:
    if book["status"] != "ready":
        raise HTTPException(404, "아직 읽을 수 있는 EPUB이 없습니다.")
    return book_dir(user_id, book["id"]) / "book.epub"


@router.get("/book/{book_id}/read")
def read(request: Request, book_id: int, c: int | None = None):
    user = current_user(request)
    if user is None:
        return _login_redirect()
    with get_conn() as conn:
        book = _own_book(conn, user["id"], book_id)
        saved = conn.execute("SELECT chapter, ratio FROM progress WHERE user_id = ? AND book_id = ?",
                             (user["id"], book_id)).fetchone()
    if book["status"] != "ready":
        return RedirectResponse(f"/book/{book_id}", status_code=303)
    if c is None:  # 주소에 장 번호를 항상 남긴다 (이어 읽기)
        return RedirectResponse(f"/book/{book_id}/read?c={saved['chapter'] if saved else 0}",
                                status_code=303)
    chapters = load_chapters(_epub(user["id"], book), book_id)
    if not chapters:
        raise HTTPException(404, "읽을 내용이 없습니다.")
    index = min(max(c, 0), len(chapters) - 1)
    start, span = _weights(chapters)[index]
    return templates.TemplateResponse(request, "reader.html", {
        "book": book, "chapters": [ch.title for ch in chapters], "index": index,
        "chapter": chapters[index], "total": len(chapters), "start": round(start, 3),
        "span": round(span, 3),
        "resume": saved["ratio"] if saved and saved["chapter"] == index else 0,
    })


@router.get("/book/{book_id}/asset/{asset_path:path}")
def asset(request: Request, book_id: int, asset_path: str):
    """EPUB 안의 그림 (본인 책, 이미지 확장자만)."""
    user = current_user(request)
    if user is None:
        raise HTTPException(401)
    with get_conn() as conn:
        book = _own_book(conn, user["id"], book_id)
    with zipfile.ZipFile(_epub(user["id"], book)) as zf:
        if asset_path not in zf.namelist() or asset_path.rsplit(".", 1)[-1].lower() not in IMAGE_EXT:
            raise HTTPException(404)
        data = zf.read(asset_path)
    return Response(data, media_type=mimetypes.guess_type(asset_path)[0] or "image/png",
                    headers={"Cache-Control": "private, max-age=86400"})


class Progress(BaseModel):
    chapter: int = Field(ge=0, le=100000)
    ratio: float = Field(ge=0, le=1)
    percent: float = Field(ge=0, le=100)


@router.post("/book/{book_id}/progress", status_code=204)
def save_progress(request: Request, book_id: int, body: Progress):
    user = current_user(request)
    if user is None:
        raise HTTPException(401)
    with get_conn() as conn:
        _own_book(conn, user["id"], book_id)
        conn.execute(
            "INSERT INTO progress (user_id, book_id, chapter, ratio, percent) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(user_id, book_id) DO UPDATE SET chapter = excluded.chapter,"
            " ratio = excluded.ratio, percent = excluded.percent, updated_at = CURRENT_TIMESTAMP",
            (user["id"], book_id, body.chapter, body.ratio, body.percent))
    return Response(status_code=204)
