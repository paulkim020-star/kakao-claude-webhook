"""올라온 파일의 종류 판별, 속성(메타데이터)·목차 추출, 표지 이미지 만들기."""

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pymupdf
from PIL import Image, ImageOps

COVER_WIDTH = 600
UPLOAD_COVER_MAX_WIDTH = 900


class SourceError(Exception):
    """사용자에게 그대로 보여줄 수 있는 파일 처리 오류."""


# ---------------------------------------------------------------- 종류 판별

def sniff(path: Path) -> str | None:
    """파일 내용으로 종류를 판별: pdf / docx / hwpx / image / hwp(미지원) / None."""
    with open(path, "rb") as f:
        head = f.read(8)
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "hwp"  # 옛 한글(.hwp)과 옛 워드(.doc)는 같은 OLE 형식이다
    if head.startswith(b"PK"):
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                if "word/document.xml" in names:
                    return "docx"
                if "Contents/content.hpf" in names or any(n.startswith("Contents/section") for n in names):
                    return "hwpx"
        except zipfile.BadZipFile:
            return None
        return None
    try:
        with Image.open(path) as img:
            img.verify()
        return "image"
    except Exception:
        return None


# ---------------------------------------------------------------- 표지

def cover_from_upload(src: Path, kind: str, out: Path) -> None:
    """별도로 받은 표지(이미지 또는 PDF)를 서재용 PNG로 정리한다."""
    try:
        if kind == "pdf":
            with pymupdf.open(src) as doc:
                if doc.needs_pass or doc.page_count == 0:
                    raise SourceError("표지 PDF를 열 수 없습니다.")
                _render_first_page(doc, out)
        elif kind == "image":
            with Image.open(src) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                if img.width > UPLOAD_COVER_MAX_WIDTH:
                    img = img.resize((UPLOAD_COVER_MAX_WIDTH,
                                      round(img.height * UPLOAD_COVER_MAX_WIDTH / img.width)))
                img.save(out, "PNG")
        else:
            raise SourceError("표지는 이미지(PNG, JPG, WEBP 등)나 PDF만 쓸 수 있습니다.")
    except SourceError:
        raise
    except Exception as exc:
        raise SourceError("표지 파일을 열 수 없습니다.") from exc


def _render_first_page(doc: pymupdf.Document, out: Path) -> None:
    page = doc[0]
    zoom = COVER_WIDTH / page.rect.width
    page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).save(out)


# ---------------------------------------------------------------- 속성

def parse_pdf_date(value: str) -> str:
    """'D:20230415093000+09'00'' -> '2023-04-15'. 해석 못 하면 빈 문자열."""
    match = re.match(r"D:(\d{4})(\d{2})(\d{2})", value or "")
    return "-".join(match.groups()) if match else ""


def clean_title(raw: str, fallback: str) -> str:
    title = re.sub(r"^Microsoft Word - ", "", (raw or "").strip())
    return title or fallback


def _blank_info(title: str) -> dict:
    return {"title": title, "author": "", "subject": "", "keywords": "", "creator": "",
            "producer": "", "pdf_version": "", "created": "", "modified": "",
            "pages": 0, "toc": [], "has_cover": False}


def extract(path: Path, kind: str, fallback_title: str, cover_path: Path | None = None) -> dict:
    """내지의 속성을 읽는다. PDF이고 cover_path가 있으면 첫 쪽을 표지로 저장한다.
    읽을 수 없으면 SourceError."""
    if kind == "pdf":
        return _extract_pdf(path, fallback_title, cover_path)
    if kind == "docx":
        return _extract_docx(path, fallback_title)
    if kind == "hwpx":
        return _extract_hwpx(path, fallback_title)
    raise SourceError("지원하지 않는 내지 형식입니다.")


def _extract_pdf(pdf_path: Path, fallback_title: str, cover_path: Path | None) -> dict:
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:
        raise SourceError("PDF 파일을 열 수 없습니다. 손상된 파일일 수 있습니다.") from exc
    with doc:
        if doc.needs_pass:
            raise SourceError("암호가 걸린 PDF는 올릴 수 없습니다.")
        if doc.page_count == 0:
            raise SourceError("쪽이 없는 PDF입니다.")
        md = doc.metadata or {}
        info = _blank_info(clean_title(md.get("title"), fallback_title))
        info.update({
            "author": (md.get("author") or "").strip(),
            "subject": (md.get("subject") or "").strip(),
            "keywords": (md.get("keywords") or "").strip(),
            "creator": (md.get("creator") or "").strip(),
            "producer": (md.get("producer") or "").strip(),
            "pdf_version": (md.get("format") or "").strip(),
            "created": parse_pdf_date(md.get("creationDate")),
            "modified": parse_pdf_date(md.get("modDate")),
            "pages": doc.page_count,
            "toc": [[lvl, title, page] for lvl, title, page in doc.get_toc()][:200],
        })
        if cover_path:
            try:
                _render_first_page(doc, cover_path)
                info["has_cover"] = True
            except Exception:
                pass  # 표지 없이도 서재에는 꽂힌다 (화면에서 제목 표지를 그린다)
        return info


def _local_values(xml_bytes: bytes) -> dict:
    """XML의 '로컬 태그 이름 -> 글자' (네임스페이스 접두어 무시, 첫 값 우선)."""
    values = {}
    try:
        for el in ElementTree.fromstring(xml_bytes).iter():
            name = el.tag.rsplit("}", 1)[-1]
            if (el.text or "").strip():
                values.setdefault(name, el.text.strip())
    except ElementTree.ParseError:
        pass
    return values


def _extract_docx(path: Path, fallback_title: str) -> dict:
    try:
        with zipfile.ZipFile(path) as zf:
            core = _local_values(zf.read("docProps/core.xml")) if "docProps/core.xml" in zf.namelist() else {}
            app = _local_values(zf.read("docProps/app.xml")) if "docProps/app.xml" in zf.namelist() else {}
    except zipfile.BadZipFile as exc:
        raise SourceError("DOCX 파일을 열 수 없습니다. 손상된 파일일 수 있습니다.") from exc
    info = _blank_info(clean_title(core.get("title"), fallback_title))
    info.update({
        "author": core.get("creator", ""),
        "subject": core.get("subject", ""),
        "keywords": core.get("keywords", ""),
        "creator": app.get("Application", ""),
        "created": core.get("created", "")[:10],
        "modified": core.get("modified", "")[:10],
        "pages": int(app["Pages"]) if app.get("Pages", "").isdigit() else 0,
    })
    return info


def _extract_hwpx(path: Path, fallback_title: str) -> dict:
    from ebook import hwpx  # hwpx가 이 모듈의 SourceError를 쓰므로 늦게 가져온다
    try:
        raw = hwpx.read_meta(path)
    except zipfile.BadZipFile as exc:
        raise SourceError("HWPX 파일을 열 수 없습니다. 손상된 파일일 수 있습니다.") from exc
    info = _blank_info(clean_title(raw["title"], fallback_title))
    info.update({k: raw[k] for k in ("author", "subject", "keywords", "created", "modified")})
    info["creator"] = "한글"
    return info
