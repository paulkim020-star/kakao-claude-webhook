"""PDF -> EPUB 변환 (PyMuPDF + EbookLib, 오프라인).

간단한 규칙 기반 변환기:
  - 본문 글자 크기(중앙값)보다 크고 짧은 줄은 제목으로 본다.
  - 챕터 경계는 PDF 목차(1단계)가 있으면 그것을, 없으면 큰 제목(h1)을 쓴다.
  - 쪽 번호처럼 숫자만 있는 줄은 버리고, 작은 이미지는 건너뛴다.
  - 글자가 없는 스캔본은 변환하지 않는다 (OCR 미지원).
"""

import html
import re
import statistics
import uuid
from pathlib import Path

import pymupdf
from ebooklib import epub

from ebook.meta import PdfError

H1_RATIO = 1.5
H2_RATIO = 1.2
MAX_HEADING_CHARS = 80
MIN_IMAGE_PX = 80

CSS = """
body { line-height: 1.7; }
h1 { font-size: 1.5em; margin: 1.2em 0 0.8em; }
h2 { font-size: 1.2em; margin: 1.1em 0 0.6em; }
p { margin: 0 0 0.9em; text-indent: 0; }
img { max-width: 100%; height: auto; }
"""


def _is_hangul_text(sample: str) -> bool:
    hangul = len(re.findall(r"[가-힣]", sample))
    return hangul > len(sample) * 0.1


def _body_size(doc: pymupdf.Document) -> float:
    sizes = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    sizes.extend([span["size"]] * len(span["text"].strip()))
    return statistics.median(sizes) if sizes else 0.0


def _block_text(block: dict) -> tuple[str, float]:
    lines, size = [], 0.0
    for line in block["lines"]:
        text = "".join(span["text"] for span in line["spans"]).strip()
        if text:
            lines.append(text)
        size = max([size] + [span["size"] for span in line["spans"]])
    joined = ""
    for text in lines:
        joined = joined[:-1] + text if joined.endswith("-") else (joined + " " + text).strip()
    return joined, size


def pdf_to_epub(pdf_path: Path, epub_path: Path, title: str, author: str,
                cover_path: Path | None = None) -> int:
    """변환하고 챕터 수를 돌려준다. 변환할 수 없으면 PdfError."""
    doc = pymupdf.open(pdf_path)
    with doc:
        body = _body_size(doc)
        if body == 0:
            raise PdfError("글자가 없는 스캔 PDF라서 EPUB으로 바꿀 수 없습니다. (OCR 미지원)")

        toc_starts = {}
        for level, toc_title, page_no in doc.get_toc():
            if level == 1:
                toc_starts.setdefault(page_no - 1, toc_title.strip() or "제목 없음")

        chapters: list[dict] = [{"title": "시작", "parts": []}]
        images: list[tuple[str, bytes]] = []
        sample = []

        for page_idx, page in enumerate(doc):
            if page_idx in toc_starts:
                chapters.append({"title": toc_starts[page_idx], "parts": []})
            for block in page.get_text("dict")["blocks"]:
                current = chapters[-1]["parts"]
                if block["type"] == 1:
                    if min(block["width"], block["height"]) < MIN_IMAGE_PX:
                        continue
                    name = f"img_{len(images) + 1}.{block['ext']}"
                    images.append((name, block["image"]))
                    current.append(f'<p><img src="images/{name}" alt=""/></p>')
                    continue
                text, size = _block_text(block)
                if not text or text.isdigit():
                    continue
                sample.append(text)
                escaped = html.escape(text)
                is_short = len(text) <= MAX_HEADING_CHARS
                if is_short and size >= body * H1_RATIO:
                    if not toc_starts:
                        chapters.append({"title": text, "parts": []})
                        current = chapters[-1]["parts"]
                    current.append(f"<h1>{escaped}</h1>")
                elif is_short and size >= body * H2_RATIO:
                    current.append(f"<h2>{escaped}</h2>")
                else:
                    current.append(f"<p>{escaped}</p>")

        chapters = [c for c in chapters if c["parts"]]
        if not chapters:
            raise PdfError("본문 글자를 찾지 못했습니다.")

        book = epub.EpubBook()
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(title)
        book.set_language("ko" if _is_hangul_text(" ".join(sample)[:5000]) else "en")
        if author:
            book.add_author(author)
        if cover_path and cover_path.exists():
            book.set_cover("cover.png", cover_path.read_bytes())

        style = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css",
                              content=CSS.encode())
        book.add_item(style)
        for name, data in images:
            ext = name.rsplit(".", 1)[-1].lower()
            media = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            book.add_item(epub.EpubItem(uid=name, file_name=f"images/{name}", media_type=media,
                                        content=data))

        items = []
        for number, chapter in enumerate(chapters, 1):
            item = epub.EpubHtml(title=chapter["title"], file_name=f"chap_{number:03d}.xhtml",
                                 lang=book.language)
            item.content = "".join(chapter["parts"])
            item.add_item(style)
            book.add_item(item)
            items.append(item)

        book.toc = items
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", *items]
        epub.write_epub(str(epub_path), book)
        return len(items)
