"""PDF 속성(메타데이터), 목차, 표지 이미지 추출."""

import re
from pathlib import Path

import pymupdf

COVER_WIDTH = 400


class PdfError(Exception):
    """사용자에게 그대로 보여줄 수 있는 PDF 처리 오류."""


def parse_pdf_date(value: str) -> str:
    """'D:20230415093000+09'00'' -> '2023-04-15'. 해석 못 하면 빈 문자열."""
    match = re.match(r"D:(\d{4})(\d{2})(\d{2})", value or "")
    return "-".join(match.groups()) if match else ""


def clean_title(raw: str, fallback: str) -> str:
    title = re.sub(r"^Microsoft Word - ", "", (raw or "").strip())
    return title or fallback


def extract(pdf_path: Path, cover_path: Path, fallback_title: str) -> dict:
    """속성을 읽고 첫 쪽을 표지 PNG로 저장한다. 읽을 수 없으면 PdfError."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:
        raise PdfError("PDF 파일을 열 수 없습니다. 손상된 파일일 수 있습니다.") from exc
    with doc:
        if doc.needs_pass:
            raise PdfError("암호가 걸린 PDF는 올릴 수 없습니다.")
        if doc.page_count == 0:
            raise PdfError("쪽이 없는 PDF입니다.")
        md = doc.metadata or {}
        has_cover = False
        try:
            page = doc[0]
            zoom = COVER_WIDTH / page.rect.width
            page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).save(cover_path)
            has_cover = True
        except Exception:
            pass  # 표지 없이도 서재에는 꽂힌다 (화면에서 제목 표지를 그린다)
        return {
            "title": clean_title(md.get("title"), fallback_title),
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
            "has_cover": has_cover,
        }
