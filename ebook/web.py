"""PDF 서재 웹 화면: 로그인, 서재(표지 진열), 책 상세, 업로드/다운로드/삭제."""

import json
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ebook import auth, convert, meta
from ebook.db import book_dir, get_conn

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

@router.get("/library")
def library(request: Request, q: str = "", sort: str = "recent", added: int = 0, skipped: int = 0):
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
        "added": added, "skipped": skipped,
        "converting": any(b["status"] == "converting" for b in books),
    })


def run_conversion(user_id: int, book_id: int) -> None:
    folder = book_dir(user_id, book_id)
    with get_conn() as conn:
        book = conn.execute("SELECT title, author, has_cover FROM books WHERE id = ?",
                            (book_id,)).fetchone()
    try:
        convert.pdf_to_epub(folder / "original.pdf", folder / "book.epub", book["title"],
                            book["author"], folder / "cover.png" if book["has_cover"] else None)
        status, error = "ready", ""
    except meta.PdfError as exc:
        status, error = "failed", str(exc)
    except Exception:
        status, error = "failed", "변환 중 알 수 없는 오류가 났습니다. 원본 PDF는 보관되어 있습니다."
    with get_conn() as conn:
        conn.execute("UPDATE books SET status = ?, error = ? WHERE id = ?",
                     (status, error, book_id))


@router.post("/upload")
async def upload(request: Request, background: BackgroundTasks, files: list[UploadFile]):
    user = current_user(request)
    if user is None:
        return _login_redirect()
    added = skipped = 0
    for upload_file in files:
        head = await upload_file.read(5)
        await upload_file.seek(0)
        if head != b"%PDF-":
            skipped += 1
            continue
        stem = Path(upload_file.filename or "책").stem
        with get_conn() as conn:
            cur = conn.execute("INSERT INTO books (user_id, title, orig_name) VALUES (?, ?, ?)",
                               (user["id"], stem, upload_file.filename or "책.pdf"))
            book_id = cur.lastrowid
        folder = book_dir(user["id"], book_id)
        with open(folder / "original.pdf", "wb") as out:
            shutil.copyfileobj(upload_file.file, out)
        try:
            info = meta.extract(folder / "original.pdf", folder / "cover.png", stem)
        except meta.PdfError:
            shutil.rmtree(folder, ignore_errors=True)
            with get_conn() as conn:
                conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            skipped += 1
            continue
        (folder / "meta.json").write_text(json.dumps(info, ensure_ascii=False, indent=2))
        with get_conn() as conn:
            conn.execute(
                "UPDATE books SET title = ?, author = ?, pages = ?, file_size = ?, has_cover = ?,"
                " meta_json = ? WHERE id = ?",
                (info["title"], info["author"], info["pages"],
                 (folder / "original.pdf").stat().st_size, int(info["has_cover"]),
                 json.dumps(info, ensure_ascii=False), book_id))
        background.add_task(run_conversion, user["id"], book_id)
        added += 1
    return RedirectResponse(f"/library?added={added}&skipped={skipped}", status_code=303)


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


@router.get("/book/{book_id}/pdf")
def book_pdf(request: Request, book_id: int):
    with get_conn() as conn:
        user = current_user(request)
        name = (_own_book(conn, user["id"], book_id)["orig_name"] if user else "book.pdf")
    return _book_file(request, book_id, "original.pdf", "application/pdf", name)


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
