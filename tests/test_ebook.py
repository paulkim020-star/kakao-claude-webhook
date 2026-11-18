"""PDF 서재 테스트: 속성 추출, EPUB 변환, 계정별 서재 격리, 웹 플로우."""

import io
import zipfile

import pymupdf
import pytest
from fastapi.testclient import TestClient

from ebook import auth, convert, db, meta, pairing, reader
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
    ole.write_bytes(b"\xd0\xcf\x11\xe0" + b"0" * 100)  # 머리만 OLE인 깨진 파일
    assert meta.sniff(ole) is None
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
             staged("낡은.doc", "doc"), staged("사진.png", "image"), staged("메모_표지.docx", "docx"),
             staged("한글_내지.hwp", "hwp")]
    plans, rejected = pairing.make_plans(files)
    by_key = {p.key: p for p in plans}
    assert by_key["나의책"].cover.name == "나의책_표지.png"
    assert by_key["둘째"].cover.name == "둘째_표지.pdf"
    assert by_key[""].cover is None and by_key[""].interior.name == "그냥.pdf"
    assert dict((f.name, why) for f, why in rejected) == {
        "낡은.doc": "doc", "사진.png": "bad", "메모_표지.docx": "bad_cover", "짝없음_표지.png": "lone_cover"}
    assert by_key["한글"].interior.kind == "hwp" and by_key["한글"].cover is None


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
    assert res.headers["location"] == "/library?added=0&why=bad,lone_cover"  # 깨진 파일은 형식을 알 수 없다
    page = client.get(res.headers["location"]).text
    assert "HWP, HWPX가 아니거나" in page and "짝이 되는 내지가 없는 표지" in page


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
    assert res.status_code == 400 and "내지는 PDF, DOCX, HWP, HWPX만" in res.text
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


# ================================================================ 웹 EPUB 리더

def test_reader_sanitizer_strips_scripts_events_and_unsafe_links():
    from lxml import html as lxml_html
    body = lxml_html.document_fromstring(
        '<html><body>앞글<script>alert(1)</script><p onclick="x()" style="color:red">안녕'
        '<a href="javascript:alert(1)">나쁜 링크</a><a href="https://example.com">좋은 링크</a></p>'
        '<iframe src="//evil"></iframe><custom-tag>글자만 남음</custom-tag>'
        '<img src="../../etc/passwd" onerror="x()"><!-- 주석 --></body></html>').body
    out = reader._clean(body, "EPUB/chap_001.xhtml", {"EPUB/images/a.png"}, 1)
    assert "<script" not in out and "alert(1)</" not in out and "onclick" not in out and "style=" not in out
    assert "javascript:" not in out and "iframe" not in out and "<img" not in out and "주석" not in out
    assert 'href="https://example.com"' in out and "글자만 남음" in out and "앞글" in out


def test_reader_weights_follow_text_length():
    chapters = [reader.Chapter("a", "", 100), reader.Chapter("b", "", 300)]
    assert reader._weights(chapters) == [(0.0, 25.0), (25.0, 75.0)]


def test_reader_reads_chapters_and_resumes(tmp_path):
    client = signup()
    upload(client, make_pdf(tmp_path / "a.pdf"))

    res = client.get("/book/1/read", follow_redirects=False)  # 처음엔 첫 장으로
    assert res.status_code == 303 and res.headers["location"] == "/book/1/read?c=0"
    page = client.get("/book/1/read?c=0").text
    assert "Body line 0 of chapter 1." in page and "1 / 2" in page and "다음 장" in page
    assert "이전 장" not in page and "<script>alert" not in page
    assert "Body line 0 of chapter 2." in client.get("/book/1/read?c=1").text
    assert "다 읽었습니다" in client.get("/book/1/read?c=1").text
    assert "Body line 0 of chapter 2." in client.get("/book/1/read?c=99").text  # 범위 밖은 마지막 장

    saved = client.post("/book/1/progress", json={"chapter": 1, "ratio": 0.5, "percent": 75})
    assert saved.status_code == 204
    assert client.get("/book/1/read", follow_redirects=False).headers["location"] == "/book/1/read?c=1"
    assert 'data-resume="0.5"' in client.get("/book/1/read?c=1").text
    assert 'data-resume="0"' in client.get("/book/1/read?c=0").text  # 다른 장은 처음부터

    assert "75% 읽음" in client.get("/library").text
    assert "이어 읽기 · 75%" in client.get("/book/1").text
    client.post("/book/1/progress", json={"chapter": 0, "ratio": 0.1, "percent": 5})  # 덮어쓰기
    assert "5% 읽음" in client.get("/library").text


def test_reader_progress_validation_and_isolation(tmp_path):
    alice = signup("alice")
    upload(alice, make_pdf(tmp_path / "a.pdf"))
    assert alice.post("/book/1/progress", json={"chapter": 0, "ratio": 2, "percent": 10}).status_code == 422
    assert alice.post("/book/1/progress", json={"chapter": -1, "ratio": 0, "percent": 10}).status_code == 422
    bob = signup("bob")
    assert bob.post("/book/1/progress", json={"chapter": 0, "ratio": 0, "percent": 1}).status_code == 404
    assert bob.get("/book/1/read?c=0").status_code == 404
    assert TestClient(app).post("/book/1/progress", json={"chapter": 0, "ratio": 0, "percent": 1}).status_code == 401
    assert TestClient(app).get("/book/1/read", follow_redirects=False).headers["location"] == "/login"


def test_reader_serves_images_only_from_own_epub(tmp_path):
    alice = signup("alice")
    upload_many(alice, [("b.docx", make_docx(tmp_path / "b.docx"))])
    page = alice.get("/book/1/read?c=0").text  # 그림은 첫 장에 있다
    assert "/book/1/asset/EPUB/images/img_1.png" in page
    img = alice.get("/book/1/asset/EPUB/images/img_1.png")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content[:4] == b"\x89PNG"
    assert alice.get("/book/1/asset/EPUB/chap_001.xhtml").status_code == 404  # 그림이 아닌 파일
    assert alice.get("/book/1/asset/EPUB/images/../../../../etc/passwd").status_code == 404
    assert signup("bob").get("/book/1/asset/EPUB/images/img_1.png").status_code == 404


def test_reader_unavailable_without_epub(tmp_path):
    client = signup()
    upload(client, make_pdf(tmp_path / "s.pdf", scanned=True))
    res = client.get("/book/1/read?c=0", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/book/1"
    assert "읽기" not in client.get("/book/1").text.split("파일 속성")[0].replace("서재에서", "")


def test_reader_shows_hwpx_and_docx_books(tmp_path):
    client = signup()
    upload_many(client, [("h.hwpx", make_hwpx(tmp_path / "h.hwpx"))])
    page = client.get("/book/1/read?c=0").text
    assert "<h1>첫째 장</h1>" in page and "본문 한 줄입니다." in page and "셀가" in page
    assert "/book/1/asset/EPUB/images/img_1.png" in page
    assert "둘째 본문입니다." in client.get("/book/1/read?c=1").text


def test_reader_page_mode_controls_and_explicit_position(tmp_path):
    client = signup()
    upload(client, make_pdf(tmp_path / "a.pdf"))
    page = client.get("/book/1/read?c=0").text
    assert 'data-set="mode" data-value="page"' in page and 'id="stage"' in page and 'id="pageno"' in page
    # r: 이전 장 끝이나 책갈피로 열 때 지정하는 위치 (0~1로 보정)
    assert 'data-resume="1"' in client.get("/book/1/read?c=0&r=1").text or 'data-resume="1.0"' in client.get("/book/1/read?c=0&r=1").text
    assert 'data-resume="0.25"' in client.get("/book/1/read?c=0&r=0.25").text
    assert 'data-resume="0"' in client.get("/book/1/read?c=0&r=-5").text or 'data-resume="0.0"' in client.get("/book/1/read?c=0&r=-5").text
    client.post("/book/1/progress", json={"chapter": 0, "ratio": 0.6, "percent": 30})
    assert 'data-resume="0.25"' in client.get("/book/1/read?c=0&r=0.25").text  # 지정이 저장 위치보다 우선


# ================================================================ 책갈피 / 밑줄 / 메모

def test_notes_crud_and_summary(tmp_path):
    client = signup()
    upload(client, make_pdf(tmp_path / "a.pdf"))
    assert client.get("/book/1/notes").json() == []

    hl = client.post("/book/1/notes", json={"kind": "highlight", "chapter": 0, "start": 5, "end": 20,
                                             "text": "고른 글", "color": "pink"})
    assert hl.status_code == 201 and hl.json()["color"] == "pink" and hl.json()["note"] == ""
    bm = client.post("/book/1/notes", json={"kind": "bookmark", "chapter": 1, "ratio": 0.4, "text": "여기"}).json()
    assert bm["kind"] == "bookmark" and bm["ratio"] == 0.4

    edited = client.patch(f"/book/1/notes/{hl.json()['id']}", json={"note": "나중에 다시 보기", "color": "green"}).json()
    assert (edited["note"], edited["color"]) == ("나중에 다시 보기", "green")
    only_color = client.patch(f"/book/1/notes/{hl.json()['id']}", json={"color": "yellow"}).json()
    assert only_color["note"] == "나중에 다시 보기" and only_color["color"] == "yellow"

    listed = client.get("/book/1/notes").json()
    assert [n["kind"] for n in listed] == ["highlight", "bookmark"]  # 장 순서
    assert "책갈피 1개 · 밑줄 1개 · 메모 1개" in client.get("/book/1").text

    assert client.delete(f"/book/1/notes/{bm['id']}").status_code == 204
    assert [n["kind"] for n in client.get("/book/1/notes").json()] == ["highlight"]
    assert client.delete(f"/book/1/notes/{bm['id']}").status_code == 404


def test_notes_validation(tmp_path):
    client = signup()
    upload(client, make_pdf(tmp_path / "a.pdf"))
    bad = [
        {"kind": "highlight", "chapter": 0, "start": 5, "end": 5, "text": "x"},          # 빈 범위
        {"kind": "highlight", "chapter": 0, "start": 1, "end": 9, "text": "   "},        # 빈 글
        {"kind": "highlight", "chapter": 0, "start": 1, "end": 9, "text": "x", "color": "purple"},
        {"kind": "bookmark", "chapter": 0, "ratio": 3},
        {"kind": "other", "chapter": 0},
        {"kind": "highlight", "chapter": -1, "start": 1, "end": 2, "text": "x"},
        {"kind": "highlight", "chapter": 0, "start": 1, "end": 9, "text": "x" * 2001},
    ]
    for payload in bad:
        assert client.post("/book/1/notes", json=payload).status_code == 422, payload
    assert client.get("/book/1/notes").json() == []


def test_notes_are_private_and_text_is_data_only(tmp_path):
    alice = signup("alice")
    upload(alice, make_pdf(tmp_path / "a.pdf"))
    evil = "<script>alert(1)</script>"
    note = alice.post("/book/1/notes", json={"kind": "highlight", "chapter": 0, "start": 0, "end": 3,
                                              "text": evil, "note": evil}).json()
    assert alice.get("/book/1/notes").json()[0]["note"] == evil  # JSON으로만 돌려준다 (HTML에 끼워 넣지 않는다)
    assert evil not in alice.get("/book/1/read?c=0").text         # 리더 HTML에는 메모 내용이 없다

    bob = signup("bob")
    assert bob.get("/book/1/notes").status_code == 404
    assert bob.post("/book/1/notes", json={"kind": "bookmark", "chapter": 0}).status_code == 404
    assert bob.patch(f"/book/1/notes/{note['id']}", json={"note": "x"}).status_code == 404
    assert bob.delete(f"/book/1/notes/{note['id']}").status_code == 404
    anon = TestClient(app)
    assert anon.get("/book/1/notes").status_code == 401
    assert alice.get("/book/1/notes").json()[0]["id"] == note["id"]  # 남이 건드리지 못했다


def test_notes_removed_with_book(tmp_path):
    client = signup()
    upload(client, make_pdf(tmp_path / "a.pdf"))
    client.post("/book/1/notes", json={"kind": "bookmark", "chapter": 0, "ratio": 0.1})
    client.post("/book/1/delete")
    with db.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


# ================================================================ 옛 한글(.hwp) 레코드 해석 / 펼침면 표지

def rec(tag, level, body=b""):
    import struct
    head = tag | (level << 10) | (min(len(body), 0xFFF) << 20)
    return struct.pack("<I", head) + (struct.pack("<I", len(body)) if len(body) >= 0xFFF else b"") + body


def hwp_para(level, text, style=0, shape=0):
    import struct
    header = struct.pack("<IIHB", len(text), 0, 0, style) + b"\x00" * 13   # 스타일 번호는 10번째 바이트
    body = text.encode("utf-16le") + b"\r\x00"
    return (rec(66, level, header) + rec(67, level + 1, body)
            + rec(68, level + 1, struct.pack("<II", 0, shape)))


def hwp_cell(level, col, row, text, colspan=1, rowspan=1):
    import struct
    return rec(72, level, struct.pack("<8H", 1, 0, 0, 0, col, row, colspan, rowspan) + b"\x00" * 31) + hwp_para(level, text)


def test_hwp5_text_extraction_skips_controls():
    from ebook import hwp5
    wide = b"\x0b\x00" + b"\x00" * 14                      # 표/그림 자리 표시 컨트롤은 16바이트
    tab = b"\x09\x00" + b"\x00" * 14                       # 탭도 16바이트 컨트롤이다
    raw = "앞 글".encode("utf-16le") + wide + tab + "뒤 글".encode("utf-16le") + b"\x0a\x00" + "줄".encode("utf-16le") + b"\r\x00"
    assert hwp5.para_text(raw) == "앞 글 뒤 글\n줄"


def test_hwp5_section_headings_tables_and_header_footer():
    from ebook import hwp5
    data = (
        hwp_para(0, "서문", style=1)
        + hwp_para(0, "본문 한 줄")
        + rec(66, 0, b"\x00" * 24) + rec(71, 1, b"daeh" + b"\x00" * 8)        # 머리말 안쪽은 본문이 아니다
        + hwp_para(2, "쪽 머리말") + rec(72, 2, b"\x00" * 30)
        + rec(66, 0, b"\x00" * 24) + rec(71, 1, b" lbt" + b"\x00" * 40) + rec(77, 2, b"\x00" * 14)
        + hwp_cell(2, 0, 0, "칸 가", colspan=2) + hwp_cell(2, 0, 1, "칸 나") + hwp_cell(2, 1, 1, "칸 다")
        + hwp_para(0, "표 다음 글")
    )
    blocks, _ = hwp5._read_section(data, ["바탕글", "개요 1"], [1000])
    kinds = [b[0] for b in blocks]
    assert kinds == ["para", "para", "table", "para"]
    assert (blocks[0][2], blocks[0][3]) == (1, "서문") and blocks[1][2] == 0   # 개요 스타일만 제목
    table = blocks[2][1]
    assert 'colspan="2"' in table and table.count("<tr>") == 2 and "칸 다" in table
    assert "머리말" not in str(blocks) and blocks[3][3] == "표 다음 글"


def test_hwp5_rejects_non_hwp_and_missing_file(tmp_path):
    from ebook import hwp5
    junk = tmp_path / "x.hwp"
    junk.write_bytes(b"\xd0\xcf\x11\xe0" + b"0" * 64)
    with pytest.raises(meta.SourceError):
        hwp5.read_blocks(junk)


def make_spread_cover(path):
    doc = pymupdf.open()
    page = doc.new_page(width=1130, height=802)
    page.draw_rect(pymupdf.Rect(0, 0, 565, 802), color=None, fill=(1, 0, 0))     # 뒤표지 쪽: 빨강
    page.draw_rect(pymupdf.Rect(565, 0, 1130, 802), color=None, fill=(0, 0, 1))  # 앞표지 쪽: 파랑
    page.draw_rect(pymupdf.Rect(0, 0, 30, 30), color=None, fill=(0, 0, 0))        # 재단선 밖 표식
    page.set_trimbox(pymupdf.Rect(37, 37, 1093, 765))
    doc.save(path)
    return path


def test_spread_cover_pdf_keeps_only_front_cover(tmp_path):
    from PIL import Image
    out = tmp_path / "c.png"
    meta.cover_from_upload(make_spread_cover(tmp_path / "spread.pdf"), "pdf", out)
    with Image.open(out) as img:
        img = img.convert("RGB")
        assert abs(img.width / img.height - meta.FRONT_COVER_RATIO) < 0.01
        assert img.getpixel((5, 5)) == (0, 0, 255) and img.getpixel((img.width - 5, img.height // 2)) == (0, 0, 255)
        assert all(img.getpixel((x, y)) == (0, 0, 255) for x in (5, img.width // 2) for y in (5, img.height - 5))


def test_single_page_cover_pdf_is_not_cropped(tmp_path):
    from PIL import Image
    out = tmp_path / "c.png"
    meta.cover_from_upload(make_pdf(tmp_path / "plain.pdf"), "pdf", out)   # 세로 A4
    with Image.open(out) as img:
        assert abs(img.width / img.height - 595 / 842) < 0.01
