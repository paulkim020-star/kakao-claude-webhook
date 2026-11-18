"""PDF 서재 웹 화면: 로그인, 서재(표지 진열), 책 상세, 업로드/다운로드/삭제."""

import json
import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ebook import auth, convert, meta, pairing
from ebook.db import book_dir, data_dir, get_conn
from ebook.pairing import Staged

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

USERNAME_RE = re.compile(r"^[A-Za-z0-9가-힣_.-]{2,20}$")
MIN_PASSWORD = 6
SORTS = {
    "recent": ("최근 순", "added_at DESC, id DESC"),
    "title": ("제목 순", "title COLLATE NOCASE ASC"),
    "author": ("저자 순", "author COLLATE NOCASE ASC, title COLLATE NOCASE ASC"),
}
templates.env.globals["fmt_size"] = lambda n: (
    f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{max(n // 1024, 1)} KB"
)


# ------------------------------------------------------------------ 공통

def current_user(request: Request):
    user_id = auth.read_session(request.cookies.get(auth.SESSION_COOKIE))
    if user_id is None:
        return None
    with get_conn() as conn:
        return conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()


def _login_redirect() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def _start_session(user_id: int) -> RedirectResponse:
    response = RedirectResponse("/library", status_code=303)
    response.set_cookie(auth.SESSION_COOKIE, auth.make_session(user_id),
                        max_age=auth.SESSION_MAX_AGE, httponly=True, samesite="lax")
    return response


def _own_book(conn, user_id: int, book_id: int):
    book = conn.execute("SELECT * FROM books WHERE id = ? AND user_id = ?",
                        (book_id, user_id)).fetchone()
    if book is None:
        raise HTTPException(404, "책을 찾을 수 없습니다.")
    return book


# ------------------------------------------------------------------ 로그인

@router.get("/")
def index(request: Request):
    return RedirectResponse("/library" if current_user(request) else "/login", status_code=303)


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"mode": "login", "error": ""})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with get_conn() as conn:
        row = conn.execute("SELECT id, pw_hash FROM users WHERE username = ?",
                           (username.strip(),)).fetchone()
    if row is None or not auth.verify_password(password, row["pw_hash"]):
        return templates.TemplateResponse(
            request, "login.html",
            {"mode": "login", "error": "아이디나 비밀번호가 맞지 않습니다."}, status_code=401)
    return _start_session(row["id"])


@router.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"mode": "register", "error": ""})


@router.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    error = ""
    if not USERNAME_RE.match(username):
        error = "아이디는 2~20자의 한글, 영문, 숫자, _ . - 만 쓸 수 있습니다."
    elif len(password) < MIN_PASSWORD:
        error = f"비밀번호는 {MIN_PASSWORD}자 이상으로 정해 주세요."
    if not error:
        with get_conn() as conn:
            if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                error = "이미 쓰고 있는 아이디입니다."
            else:
                cur = conn.execute("INSERT INTO users (username, pw_hash) VALUES (?, ?)",
                                   (username, auth.hash_password(password)))
                return _start_session(cur.lastrowid)
    return templates.TemplateResponse(request, "login.html",
                                      {"mode": "register", "error": error}, status_code=400)


@router.post("/logout")
def logout():
    response = _login_redirect()
    response.delete_cookie(auth.SESSION_COOKIE)
    return response


# ------------------------------------------------------------------ 서재

REASONS = {
    "hwp": "옛 한글(.hwp)·워드(.doc) 파일은 열 수 없습니다. 한글에서 ‘다른 이름으로 저장’으로 "
           "HWPX나 PDF로 저장해서 올려 주세요.",
    "bad": "PDF, DOCX, HWPX가 아니거나 열 수 없는 파일은 넣지 못했습니다.",
    "lone_cover": "짝이 되는 내지가 없는 표지는 넣지 못했습니다. 파일 이름을 맞춰 주세요. "
                  "(예: 나의책_표지.png, 나의책_내지.docx)",
    "bad_cover": "표지는 이미지나 PDF만 쓸 수 있습니다.",
}


@router.get("/library")
def library(request: Request, q: str = "", sort: str = "recent", added: int = 0, why: str = ""):
    user = current_user(request)
    if user is None:
        return _login_redirect()
    sort = sort if sort in SORTS else "recent"
    sql = "SELECT * FROM books WHERE user_id = ?"
    params: list = [user["id"]]
    if q.strip():
        sql += " AND (title LIKE ? OR author LIKE ?)"
        params += [f"%{q.strip()}%"] * 2
    with get_conn() as conn:
        books = conn.execute(f"{sql} ORDER BY {SORTS[sort][1]}", params).fetchall()
    return templates.TemplateResponse(request, "shelf.html", {
        "user": user, "books": books, "q": q.strip(), "sort": sort, "sorts": SORTS,
        "added": added, "reasons": [REASONS[c] for c in dict.fromkeys(why.split(",")) if c in REASONS],
        "converting": any(b["status"] == "converting" for b in books),
    })


def run_conversion(user_id: int, book_id: int) -> None:
    folder = book_dir(user_id, book_id)
    with get_conn() as conn:
        book = conn.execute("SELECT title, author, has_cover, source_type FROM books WHERE id = ?",
                            (book_id,)).fetchone()
    try:
        convert.to_epub(folder / f"original.{book['source_type']}", folder / "book.epub",
                        book["source_type"], book["title"], book["author"],
                        folder / "cover.png" if book["has_cover"] else None)
        status, error = "ready", ""
    except meta.SourceError as exc:
        status, error = "failed", str(exc)
    except Exception:
        status, error = "failed", "변환 중 알 수 없는 오류가 났습니다. 원본 파일은 보관되어 있습니다."
    with get_conn() as conn:
        conn.execute("UPDATE books SET status = ?, error = ? WHERE id = ?",
                     (status, error, book_id))


def _stage(files: list[UploadFile], folder: Path) -> list[Staged]:
    """받은 파일을 임시 폴더에 저장하고 내용으로 종류를 판별한다 (파일명은 믿지 않는다)."""
    staged = []
    for upload_file in files:
        if upload_file is None or not upload_file.filename:  # 비워 둔 파일 칸
            continue
        dest = folder / uuid.uuid4().hex
        with open(dest, "wb") as out:
            shutil.copyfileobj(upload_file.file, out)
        staged.append(Staged(upload_file.filename, dest, meta.sniff(dest)))
    return staged


def create_book(user_id: int, interior: Staged, cover: Staged | None,
                title: str = "", author: str = "") -> int:
    """내지(+별도 표지)를 아카이브에 넣고 DB에 등록한다. 실패하면 흔적을 지우고 SourceError."""
    stem = Path(interior.name).stem
    with get_conn() as conn:
        book_id = conn.execute(
            "INSERT INTO books (user_id, title, orig_name, source_type) VALUES (?, ?, ?, ?)",
            (user_id, stem, interior.name, interior.kind)).lastrowid
    folder = book_dir(user_id, book_id)
    try:
        source = folder / f"original.{interior.kind}"
        shutil.move(interior.path, source)
        cover_png = folder / "cover.png"
        info = meta.extract(source, interior.kind, stem, None if cover else cover_png)
        if cover:
            meta.cover_from_upload(cover.path, cover.kind, cover_png)
            suffix = re.sub(r"[^a-z0-9]", "", Path(cover.name).suffix.lower()) or cover.kind
            shutil.move(cover.path, folder / f"cover_original.{suffix}")
            info["has_cover"], cover_source = True, cover.kind
        else:
            cover_source = "page1" if info["has_cover"] else "none"
        info["title"] = title or info["title"]
        info["author"] = author or info["author"]
    except meta.SourceError:
        shutil.rmtree(folder, ignore_errors=True)
        with get_conn() as conn:
            conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        raise
    (folder / "meta.json").write_text(json.dumps(info, ensure_ascii=False, indent=2))
    with get_conn() as conn:
        conn.execute(
            "UPDATE books SET title = ?, author = ?, pages = ?, file_size = ?, has_cover = ?,"
            " cover_source = ?, meta_json = ? WHERE id = ?",
            (info["title"], info["author"], info["pages"], source.stat().st_size,
             int(info["has_cover"]), cover_source, json.dumps(info, ensure_ascii=False), book_id))
    return book_id


@router.post("/upload")
def upload(request: Request, background: BackgroundTasks, files: list[UploadFile]):
    """여러 파일을 한꺼번에: 이름의 표지/내지로 짝을 맞추고, 나머지는 파일 하나가 한 권."""
    user = current_user(request)
    if user is None:
        return _login_redirect()
    staging = data_dir() / "tmp" / uuid.uuid4().hex
    staging.mkdir(parents=True)
    try:
        plans, rejected = pairing.make_plans(_stage(files, staging))
        reasons = [reason for _, reason in rejected]
        added = 0
        for plan in plans:
            try:
                book_id = create_book(user["id"], plan.interior, plan.cover, title=plan.key)
            except meta.SourceError:
                reasons.append("bad_cover" if plan.cover else "bad")
                continue
            background.add_task(run_conversion, user["id"], book_id)
            added += 1
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    why = ",".join(dict.fromkeys(reasons))
    return RedirectResponse(f"/library?added={added}&why={why}", status_code=303)


@router.get("/new")
def new_page(request: Request):
    user = current_user(request)
    if user is None:
        return _login_redirect()
    return templates.TemplateResponse(request, "new.html", {"user": user, "error": "", "form": {}})


@router.post("/new")
def new_book(request: Request, background: BackgroundTasks, interior: UploadFile | None = None,
             cover: UploadFile | None = None, title: str = Form(""), author: str = Form("")):
    """표지와 내지를 직접 골라서 한 권 만들기 (파일 이름 규칙 불필요)."""
    user = current_user(request)
    if user is None:
        return _login_redirect()
    staging = data_dir() / "tmp" / uuid.uuid4().hex
    staging.mkdir(parents=True)
    error = ""
    try:
        body = next(iter(_stage([interior], staging)), None)
        cover_file = next(iter(_stage([cover], staging)), None)
        if body is None:
            error = "내지 파일을 골라 주세요."
        elif body.kind == "hwp":
            error = REASONS["hwp"]
        elif body.kind not in pairing.BOOK_KINDS:
            error = "내지는 PDF, DOCX, HWPX만 쓸 수 있습니다."
        else:
            try:
                book_id = create_book(user["id"], body, cover_file, title.strip(), author.strip())
                background.add_task(run_conversion, user["id"], book_id)
            except meta.SourceError as exc:
                error = str(exc)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    if error:
        return templates.TemplateResponse(
            request, "new.html",
            {"user": user, "error": error, "form": {"title": title, "author": author}},
            status_code=400)
    return RedirectResponse("/library?added=1", status_code=303)


# ------------------------------------------------------------------ 책 상세

@router.get("/book/{book_id}")
def book_page(request: Request, book_id: int):
    user = current_user(request)
    if user is None:
        return _login_redirect()
    with get_conn() as conn:
        book = _own_book(conn, user["id"], book_id)
    return templates.TemplateResponse(request, "book.html", {
        "user": user, "book": book, "info": json.loads(book["meta_json"]),
        "converting": book["status"] == "converting",
    })


def _book_file(request: Request, book_id: int, filename: str, media_type: str, download_name: str):
    user = current_user(request)
    if user is None:
        raise HTTPException(401)
    with get_conn() as conn:
        _own_book(conn, user["id"], book_id)
    path = book_dir(user["id"], book_id) / filename
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type=media_type, filename=download_name or None)


@router.get("/book/{book_id}/cover")
def book_cover(request: Request, book_id: int):
    return _book_file(request, book_id, "cover.png", "image/png", "")


@router.get("/book/{book_id}/epub")
def book_epub(request: Request, book_id: int):
    with get_conn() as conn:
        user = current_user(request)
        title = (_own_book(conn, user["id"], book_id)["title"] if user else "book")
    return _book_file(request, book_id, "book.epub", "application/epub+zip", f"{title}.epub")


@router.get("/book/{book_id}/source")
def book_source(request: Request, book_id: int):
    """내지 원본 파일 (PDF / DOCX / HWPX) 내려받기."""
    with get_conn() as conn:
        user = current_user(request)
        book = _own_book(conn, user["id"], book_id) if user else None
    kind = book["source_type"] if book else "pdf"
    return _book_file(request, book_id, f"original.{kind}", "application/octet-stream",
                      book["orig_name"] if book else "book")


@router.post("/book/{book_id}/delete")
def book_delete(request: Request, book_id: int):
    user = current_user(request)
    if user is None:
        return _login_redirect()
    with get_conn() as conn:
        _own_book(conn, user["id"], book_id)
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    shutil.rmtree(book_dir(user["id"], book_id), ignore_errors=True)
    return RedirectResponse("/library", status_code=303)
