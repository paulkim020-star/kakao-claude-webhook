"""PDF 서재 테스트: 속성 추출, EPUB 변환, 계정별 서재 격리, 웹 플로우."""

import io
import zipfile

import pymupdf
import pytest
from fastapi.testclient import TestClient

from ebook import auth, convert, db, meta, pairing
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
    info = meta.extract(pdf, "pdf", "fallback", tmp_path / "cover.png")
    assert info["title"] == "Sample Book"
    assert info["author"] == "Kim"
    assert info["created"] == "2023-04-15"
    assert info["pages"] == 2
    assert info["has_cover"] and (tmp_path / "cover.png").stat().st_size > 0
    assert info["toc"][0][1] == "Chapter One"


def test_extract_falls_back_to_filename_when_title_empty(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", title="")
    assert meta.extract(pdf, "pdf", "내 책", tmp_path / "c.png")["title"] == "내 책"


def test_extract_rejects_encrypted_pdf(tmp_path):
    src = make_pdf(tmp_path / "a.pdf")
    enc = tmp_path / "enc.pdf"
    pymupdf.open(src).save(enc, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                           user_pw="pw", owner_pw="pw")
    with pytest.raises(meta.SourceError, match="암호"):
        meta.extract(enc, "pdf", "x", tmp_path / "c.png")


# ---------------------------------------------------------------- 변환

def test_convert_uses_toc_for_chapters_and_drops_page_numbers(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    out = tmp_path / "a.epub"
    assert convert.to_epub(pdf, out, "pdf", "Sample Book", "Kim") == 2
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        chap1 = z.read("EPUB/chap_001.xhtml").decode()
    assert "mimetype" in names and "EPUB/chap_002.xhtml" in names
    assert "Body line 0 of chapter 1." in chap1
    assert "<p>1</p>" not in chap1


def test_convert_splits_on_big_headings_without_toc(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", with_toc=False)
    assert convert.to_epub(pdf, tmp_path / "a.epub", "pdf", "T", "") == 2


def test_convert_refuses_scanned_pdf(tmp_path):
    pdf = make_pdf(tmp_path / "scan.pdf", scanned=True)
    with pytest.raises(meta.SourceError, match="스캔"):
        convert.to_epub(pdf, tmp_path / "s.epub", "pdf", "T", "")


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
    assert res.headers["location"] == "/library?added=1&why="

    shelf = client.get("/library").text
    assert "Sample Book" in shelf and "/book/1/cover" in shelf

    detail = client.get("/book/1").text
    assert "2쪽" in detail and "Testing" in detail and "2023-04-15" in detail
    assert "Chapter One" in detail  # 목차

    assert client.get("/book/1/epub").headers["content-type"] == "application/epub+zip"
    assert client.get("/book/1/source").content.startswith(b"%PDF-")
    assert client.get("/book/1/cover").content.startswith(b"\x89PNG")

    client.post("/book/1/delete")
    assert client.get("/book/1").status_code == 404
    assert "Sample Book" not in client.get("/library").text


def test_scanned_pdf_stays_on_shelf_without_epub(tmp_path):
    client = signup()
    upload(client, make_pdf(tmp_path / "s.pdf", scanned=True))
    detail = client.get("/book/1").text
    assert "스캔 PDF" in detail and "EPUB 받기" not in detail
    assert client.get("/book/1/source").status_code == 200


def test_non_pdf_and_broken_pdf_are_skipped(tmp_path):
    client = signup()
    fake = tmp_path / "x.pdf"
    fake.write_bytes(b"not a pdf")
    assert upload(client, fake).headers["location"] == "/library?added=0&why=bad"
    broken = tmp_path / "b.pdf"
    broken.write_bytes(b"%PDF-1.4 broken")
    assert upload(client, broken).headers["location"] == "/library?added=0&why=bad"
    assert "0권" in client.get("/library").text


def test_each_user_has_own_shelf(tmp_path):
    alice = signup("alice")
    upload(alice, make_pdf(tmp_path / "a.pdf"))
    bob = signup("bob")
    assert "Sample Book" not in bob.get("/library").text
    for path in ("/book/1", "/book/1/source", "/book/1/epub", "/book/1/cover"):
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


# ================================================================ 표지 + 내지 (이미지 / DOCX / HWPX)

def make_png(path, color=(200, 60, 60), size=(300, 450)):
    from PIL import Image
    Image.new("RGB", size, color).save(path)
    return path


def make_docx(path, title="Word Book", author="Park", korean_outline=False):
    import docx
    from docx.enum.style import WD_STYLE_TYPE
    doc = docx.Document()
    doc.core_properties.title, doc.core_properties.author = title, author
    if korean_outline:
        doc.styles.add_style("개요 1", WD_STYLE_TYPE.PARAGRAPH)
    heading = (lambda text: doc.add_paragraph(text, style="개요 1")) if korean_outline \
        else (lambda text: doc.add_heading(text, 1))
    heading("First Chapter")
    doc.add_paragraph("Hello from word.")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "cellA", "cellB"
    make_png(path.parent / "pic.png", size=(120, 120))
    doc.add_picture(str(path.parent / "pic.png"))
    heading("Second Chapter")
    doc.add_paragraph("Second body.")
    doc.save(path)
    return path


HWPX_NS = ('xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
           'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
           'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
           'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core"')


def make_hwpx(path, title="한글 책", author="김한글"):
    """한컴 구조를 흉내 낸 최소 HWPX: 개요 스타일 제목, 글자 크기 제목, 표, 그림."""
    header = f"""<hh:head {HWPX_NS}><hh:refList>
      <hh:charProperties><hh:charPr id="0" height="1000"/><hh:charPr id="1" height="1800"/></hh:charProperties>
      <hh:styles><hh:style id="0" name="바탕글"/><hh:style id="1" name="개요 1"/></hh:styles>
    </hh:refList></hh:head>"""
    def para(text, style=0, char=0):
        return (f'<hp:p styleIDRef="{style}" paraPrIDRef="0"><hp:run charPrIDRef="{char}">'
                f"<hp:t>{text}</hp:t></hp:run></hp:p>")
    table = ('<hp:p styleIDRef="0"><hp:run charPrIDRef="0"><hp:tbl><hp:tr>'
             '<hp:tc><hp:subList><hp:p><hp:run><hp:t>셀가</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
             '<hp:tc><hp:subList><hp:p><hp:run><hp:t>셀나</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
             '</hp:tr></hp:tbl></hp:run></hp:p>')
    picture = ('<hp:p styleIDRef="0"><hp:run charPrIDRef="0"><hp:pic>'
               '<hc:img binaryItemIDRef="image1"/></hp:pic></hp:run></hp:p>')
    section = (f"<hs:sec {HWPX_NS}>" + para("첫째 장", style=1) + para("본문 한 줄입니다.")
               + table + picture + para("둘째 장", char=1) + para("둘째 본문입니다.") + "</hs:sec>")
    hpf = f"""<opf:package xmlns:opf="http://www.idpf.org/2007/opf/"><opf:metadata>
      <opf:title>{title}</opf:title><opf:meta name="creator" content="text">{author}</opf:meta>
      <opf:meta name="CreatedDate" content="text">2024-05-06T01:02:03Z</opf:meta></opf:metadata>
      <opf:manifest><opf:item id="image1" href="BinData/image1.png" media-type="image/png"/></opf:manifest>
    </opf:package>"""
    png = io.BytesIO()
    from PIL import Image
    Image.new("RGB", (120, 120), (30, 90, 160)).save(png, "PNG")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/hwp+zip")
        z.writestr("Contents/content.hpf", hpf)
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section)
        z.writestr("BinData/image1.png", png.getvalue())
    return path


def epub_names(path):
    with zipfile.ZipFile(path) as z:
        return z.namelist(), {n: z.read(n).decode("utf-8", "ignore") for n in z.namelist()
                              if n.endswith(".xhtml")}


def test_sniff_by_content_not_name(tmp_path):
    assert meta.sniff(make_pdf(tmp_path / "x.dat")) == "pdf"
    assert meta.sniff(make_docx(tmp_path / "x.bin")) == "docx"
    assert meta.sniff(make_hwpx(tmp_path / "x.txt")) == "hwpx"
    assert meta.sniff(make_png(tmp_path / "x.jpg")) == "image"
    ole = tmp_path / "old.hwp"
    ole.write_bytes(b"\xd0\xcf\x11\xe0" + b"0" * 100)
    assert meta.sniff(ole) == "hwp"
    junk = tmp_path / "junk"
    junk.write_bytes(b"hello")
    assert meta.sniff(junk) is None


def test_docx_chapters_table_image_and_properties(tmp_path):
    path = make_docx(tmp_path / "a.docx")
    info = meta.extract(path, "docx", "fb")
    assert (info["title"], info["author"]) == ("Word Book", "Park")

    out = tmp_path / "a.epub"
    assert convert.to_epub(path, out, "docx", "Word Book", "Park") == 2
    names, pages = epub_names(out)
    assert any(n.startswith("EPUB/images/img_1") for n in names)
    chap1 = pages["EPUB/chap_001.xhtml"]
    assert "First Chapter" in chap1 and "cellA" in chap1 and "<table" in chap1 and "images/img_1" in chap1
    assert "Second body." in pages["EPUB/chap_002.xhtml"]


def test_docx_korean_outline_style_splits_chapters(tmp_path):
    path = make_docx(tmp_path / "k.docx", korean_outline=True)
    assert convert.to_epub(path, tmp_path / "k.epub", "docx", "T", "") == 2


def test_hwpx_headings_table_image_and_properties(tmp_path):
    path = make_hwpx(tmp_path / "a.hwpx")
    info = meta.extract(path, "hwpx", "fb")
    assert (info["title"], info["author"], info["created"]) == ("한글 책", "김한글", "2024-05-06")

    out = tmp_path / "a.epub"
    # 개요 스타일("첫째 장")과 큰 글자("둘째 장") 두 가지 제목이 모두 챕터 경계가 된다
    assert convert.to_epub(path, out, "hwpx", "한글 책", "김한글") == 2
    names, pages = epub_names(out)
    assert any(n.startswith("EPUB/images/img_1") for n in names)
    chap1 = pages["EPUB/chap_001.xhtml"]
    assert "<h1>첫째 장</h1>" in chap1 and "셀가" in chap1 and "<table" in chap1 and "img_1.png" in chap1
    assert "둘째 본문입니다." in pages["EPUB/chap_002.xhtml"]


def test_hwpx_without_text_is_refused(tmp_path):
    path = tmp_path / "empty.hwpx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Contents/section0.xml", f"<hs:sec {HWPX_NS}/>")
    with pytest.raises(meta.SourceError):
        convert.to_epub(path, tmp_path / "e.epub", "hwpx", "T", "")


# ---------------------------------------------------------------- 표지/내지 이름 짝 맞추기

def staged(name, kind):
    return pairing.Staged(name, None, kind)


def test_split_role():
    assert pairing.split_role("나의책_표지") == ("표지", "나의책")
    assert pairing.split_role("내지 - 나의책") == ("내지", "나의책")
    assert pairing.split_role("표지") == ("표지", "")
    assert pairing.split_role("평범한책") == (None, "평범한책")


def test_make_plans_pairs_by_name_and_rejects_strays():
    files = [staged("나의책_표지.png", "image"), staged("나의책_내지.docx", "docx"),
             staged("둘째_내지.hwpx", "hwpx"), staged("둘째_표지.pdf", "pdf"),
             staged("그냥.pdf", "pdf"), staged("짝없음_표지.png", "image"),
             staged("낡은.hwp", "hwp"), staged("사진.png", "image"), staged("메모_표지.docx", "docx")]
    plans, rejected = pairing.make_plans(files)
    by_key = {p.key: p for p in plans}
    assert by_key["나의책"].cover.name == "나의책_표지.png"
    assert by_key["둘째"].cover.name == "둘째_표지.pdf"
    assert by_key[""].cover is None and by_key[""].interior.name == "그냥.pdf"
    assert dict((f.name, why) for f, why in rejected) == {
        "낡은.hwp": "hwp", "사진.png": "bad", "메모_표지.docx": "bad_cover", "짝없음_표지.png": "lone_cover"}


def test_make_plans_unnamed_pair():
    plans, rejected = pairing.make_plans([staged("표지.png", "image"), staged("내지.docx", "docx")])
    assert not rejected and plans[0].cover.name == "표지.png" and plans[0].key == ""


# ---------------------------------------------------------------- 웹: 표지 + 내지

def upload_many(client, items):
    files = [("files", (name, open(path, "rb"), "application/octet-stream")) for name, path in items]
    return client.post("/upload", files=files, follow_redirects=False)


def test_upload_pairs_named_cover_and_interior(tmp_path):
    client = signup()
    cover = make_png(tmp_path / "c.png", color=(10, 120, 60))
    body = make_docx(tmp_path / "b.docx", title="Ignored Title")
    res = upload_many(client, [("나의책_표지.png", cover), ("나의책_내지.docx", body)])
    assert res.headers["location"] == "/library?added=1&why="

    detail = client.get("/book/1").text
    assert "나의책" in detail and "따로 올린 이미지" in detail and "DOCX" in detail
    assert "EPUB 받기" in detail
    from PIL import Image
    shown = Image.open(io.BytesIO(client.get("/book/1/cover").content)).convert("RGB")
    assert shown.getpixel((5, 5)) == (10, 120, 60)  # 내지 첫 쪽이 아니라 올린 표지
    with zipfile.ZipFile(io.BytesIO(client.get("/book/1/epub").content)) as z:
        assert any("cover" in n for n in z.namelist())
    assert client.get("/book/1/source").content[:2] == b"PK"


def test_upload_reports_hwp_and_lone_cover(tmp_path):
    client = signup()
    old = tmp_path / "old.hwp"
    old.write_bytes(b"\xd0\xcf\x11\xe0" + b"0" * 64)
    cover = make_png(tmp_path / "c.png")
    res = upload_many(client, [("낡은.hwp", old), ("혼자_표지.png", cover)])
    assert res.headers["location"] == "/library?added=0&why=hwp,lone_cover"
    page = client.get(res.headers["location"]).text
    assert "HWPX나 PDF로 저장" in page and "짝이 되는 내지가 없는 표지" in page


def test_new_form_builds_book_from_cover_pdf_and_hwpx(tmp_path):
    client = signup()
    cover_pdf = make_pdf(tmp_path / "cover.pdf", title="cover only")
    body = make_hwpx(tmp_path / "body.hwpx")
    with open(cover_pdf, "rb") as c, open(body, "rb") as b:
        res = client.post("/new", data={"title": "내가 정한 제목", "author": ""},
                          files={"cover": ("c.pdf", c), "interior": ("b.hwpx", b)},
                          follow_redirects=False)
    assert res.headers["location"] == "/library?added=1"
    detail = client.get("/book/1").text
    assert "내가 정한 제목" in detail and "김한글" in detail and "따로 올린 PDF" in detail
    assert "EPUB 받기" in detail and "HWPX" in detail


def test_new_form_without_cover_for_docx_leaves_cover_empty(tmp_path):
    client = signup()
    with open(make_docx(tmp_path / "b.docx"), "rb") as b:
        client.post("/new", files={"interior": ("b.docx", b)}, follow_redirects=False)
    assert "없음" in client.get("/book/1").text
    assert client.get("/book/1/cover").status_code == 404
    assert "Word Book" in client.get("/library").text  # 제목은 문서 속성에서


def test_new_form_errors(tmp_path):
    client = signup()
    old = tmp_path / "old.hwp"
    old.write_bytes(b"\xd0\xcf\x11\xe0" + b"0" * 64)
    with open(old, "rb") as f:
        res = client.post("/new", files={"interior": ("x.hwp", f)})
    assert res.status_code == 400 and "HWPX나 PDF로 저장" in res.text
    with open(make_docx(tmp_path / "b.docx"), "rb") as b, open(make_docx(tmp_path / "w.docx"), "rb") as w:
        res = client.post("/new", files={"interior": ("b.docx", b), "cover": ("w.docx", w)})
    assert res.status_code == 400 and "표지는 이미지(PNG" in res.text
    assert "0권" in client.get("/library").text
    assert not list((db.data_dir() / "archive").glob("*/*"))  # 실패한 책의 흔적이 남지 않는다


def test_old_database_gets_new_columns(tmp_path):
    import sqlite3
    path = db.data_dir() / "library.db"
    conn = sqlite3.connect(path)
    conn.executescript("""CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, pw_hash TEXT, created_at TEXT);
        CREATE TABLE books (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, author TEXT, orig_name TEXT,
        pages INTEGER, file_size INTEGER, has_cover INTEGER, status TEXT, error TEXT, meta_json TEXT, added_at TEXT);""")
    conn.close()
    cols = {r["name"] for r in db.get_conn().execute("PRAGMA table_info(books)")}
    assert {"source_type", "cover_source"} <= cols
