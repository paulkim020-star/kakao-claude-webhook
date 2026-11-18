"""PDF 서재 테스트: 속성 추출, EPUB 변환, 계정별 서재 격리, 웹 플로우."""

import zipfile

import pymupdf
import pytest
from fastapi.testclient import TestClient

from ebook import auth, convert, meta
from ebook.app import app


def make_pdf(path, title="Sample Book", author="Kim", with_toc=True, scanned=False):
    doc = pymupdf.open()
    for number, heading in enumerate(["Chapter One", "Chapter Two"], 1):
        page = doc.new_page()
        if not scanned:
            page.insert_text((72, 90), heading, fontsize=26)
            for i in range(6):
                page.insert_text((72, 140 + i * 18), f"Body line {i} of chapter {number}.", fontsize=11)
            page.insert_text((300, 800), str(number), fontsize=11)  # 쪽 번호
    doc.set_metadata({"title": title, "author": author, "subject": "Testing",
                      "creationDate": "D:20230415093000+09'00'"})
    if with_toc and not scanned:
        doc.set_toc([[1, "Chapter One", 1], [1, "Chapter Two", 2]])
    doc.save(path)
    return path


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EBOOK_DATA_DIR", str(tmp_path / "data"))


def signup(name="alice", password="secret1"):
    client = TestClient(app)
    res = client.post("/register", data={"username": name, "password": password},
                      follow_redirects=False)
    assert res.status_code == 303
    return client


def upload(client, pdf_path, filename="book.pdf"):
    with open(pdf_path, "rb") as f:
        return client.post("/upload", files={"files": (filename, f, "application/pdf")},
                           follow_redirects=False)


# ---------------------------------------------------------------- 속성 추출

def test_extract_reads_properties_and_cover(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    info = meta.extract(pdf, tmp_path / "cover.png", "fallback")
    assert info["title"] == "Sample Book"
    assert info["author"] == "Kim"
    assert info["created"] == "2023-04-15"
    assert info["pages"] == 2
    assert info["has_cover"] and (tmp_path / "cover.png").stat().st_size > 0
    assert info["toc"][0][1] == "Chapter One"


def test_extract_falls_back_to_filename_when_title_empty(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", title="")
    assert meta.extract(pdf, tmp_path / "c.png", "내 책")["title"] == "내 책"


def test_extract_rejects_encrypted_pdf(tmp_path):
    src = make_pdf(tmp_path / "a.pdf")
    enc = tmp_path / "enc.pdf"
    pymupdf.open(src).save(enc, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                           user_pw="pw", owner_pw="pw")
    with pytest.raises(meta.PdfError, match="암호"):
        meta.extract(enc, tmp_path / "c.png", "x")


# ---------------------------------------------------------------- 변환

def test_convert_uses_toc_for_chapters_and_drops_page_numbers(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    out = tmp_path / "a.epub"
    assert convert.pdf_to_epub(pdf, out, "Sample Book", "Kim") == 2
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        chap1 = z.read("EPUB/chap_001.xhtml").decode()
    assert "mimetype" in names and "EPUB/chap_002.xhtml" in names
    assert "Body line 0 of chapter 1." in chap1
    assert "<p>1</p>" not in chap1


def test_convert_splits_on_big_headings_without_toc(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", with_toc=False)
    assert convert.pdf_to_epub(pdf, tmp_path / "a.epub", "T", "") == 2


def test_convert_refuses_scanned_pdf(tmp_path):
    pdf = make_pdf(tmp_path / "scan.pdf", scanned=True)
    with pytest.raises(meta.PdfError, match="스캔"):
        convert.pdf_to_epub(pdf, tmp_path / "s.epub", "T", "")


# ---------------------------------------------------------------- 계정

def test_password_hash_roundtrip():
    stored = auth.hash_password("secret1")
    assert auth.verify_password("secret1", stored)
    assert not auth.verify_password("wrong", stored)


def test_session_cookie_rejects_tampering():
    cookie = auth.make_session(7)
    assert auth.read_session(cookie) == 7
    assert auth.read_session(cookie[:-1] + ("0" if cookie[-1] != "0" else "1")) is None
    assert auth.read_session("garbage") is None


def test_register_validation_and_duplicate():
    signup("alice")
    client = TestClient(app)
    assert client.post("/register", data={"username": "alice", "password": "secret1"}).status_code == 400
    assert client.post("/register", data={"username": "bob", "password": "123"}).status_code == 400
    assert client.post("/login", data={"username": "alice", "password": "nope"}).status_code == 401


def test_library_requires_login():
    res = TestClient(app).get("/library", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/login"


# ---------------------------------------------------------------- 웹 플로우

def test_upload_shelf_detail_download_delete(tmp_path):
    client = signup()
    res = upload(client, make_pdf(tmp_path / "a.pdf"))
    assert res.headers["location"] == "/library?added=1&skipped=0"

    shelf = client.get("/library").text
    assert "Sample Book" in shelf and "/book/1/cover" in shelf

    detail = client.get("/book/1").text
    assert "2쪽" in detail and "Testing" in detail and "2023-04-15" in detail
    assert "Chapter One" in detail  # 목차

    assert client.get("/book/1/epub").headers["content-type"] == "application/epub+zip"
    assert client.get("/book/1/pdf").content.startswith(b"%PDF-")
    assert client.get("/book/1/cover").content.startswith(b"\x89PNG")

    client.post("/book/1/delete")
    assert client.get("/book/1").status_code == 404
    assert "Sample Book" not in client.get("/library").text


def test_scanned_pdf_stays_on_shelf_without_epub(tmp_path):
    client = signup()
    upload(client, make_pdf(tmp_path / "s.pdf", scanned=True))
    detail = client.get("/book/1").text
    assert "스캔 PDF" in detail and "EPUB 받기" not in detail
    assert client.get("/book/1/pdf").status_code == 200


def test_non_pdf_and_broken_pdf_are_skipped(tmp_path):
    client = signup()
    fake = tmp_path / "x.pdf"
    fake.write_bytes(b"not a pdf")
    assert upload(client, fake).headers["location"] == "/library?added=0&skipped=1"
    broken = tmp_path / "b.pdf"
    broken.write_bytes(b"%PDF-1.4 broken")
    assert upload(client, broken).headers["location"] == "/library?added=0&skipped=1"
    assert "0권" in client.get("/library").text


def test_each_user_has_own_shelf(tmp_path):
    alice = signup("alice")
    upload(alice, make_pdf(tmp_path / "a.pdf"))
    bob = signup("bob")
    assert "Sample Book" not in bob.get("/library").text
    for path in ("/book/1", "/book/1/pdf", "/book/1/epub", "/book/1/cover"):
        assert bob.get(path).status_code == 404
    assert bob.post("/book/1/delete").status_code == 404
    assert alice.get("/book/1").status_code == 200


def test_search_and_sort(tmp_path):
    client = signup()
    upload(client, make_pdf(tmp_path / "a.pdf", title="Zebra Tales", author="Lee"))
    upload(client, make_pdf(tmp_path / "b.pdf", title="Apple Notes", author="Park"))
    assert "Zebra Tales" not in client.get("/library?q=apple").text
    assert "Apple Notes" in client.get("/library?q=park").text
    page = client.get("/library?sort=title").text
    assert page.index("Apple Notes") < page.index("Zebra Tales")
