"""내지(PDF / DOCX / HWP / HWPX) -> EPUB 변환 (오프라인).

추출(extract_*)과 EPUB 조립(write_epub)을 나눠서, 내지 형식이 늘어도 조립부는 하나다.

  PDF  : 본문 글자 크기(중앙값)보다 크고 짧은 줄을 제목으로 본다. 챕터 경계는 PDF
         목차(1단계)가 있으면 그것을, 없으면 큰 제목(h1)을 쓴다. 쪽 번호는 버린다.
  DOCX : mammoth로 HTML(제목/표/목록/그림)을 만들고 h1(없으면 h2)에서 챕터를 나눈다.
  HWPX : ebook/hwpx.py가 뽑은 블록을 같은 방식으로 나눈다.
  HWP  : ebook/hwp5.py(옛 한글 바이너리)가 뽑은 블록을 같은 방식으로 나눈다.

글자가 없는 스캔 PDF는 변환하지 않는다 (OCR 미지원).
"""

import html
import re
import statistics
import uuid
from dataclasses import dataclass
from pathlib import Path

import mammoth
import pymupdf
from ebooklib import epub
from lxml import etree
from lxml import html as lxml_html

from ebook import hwp5, hwpx
from ebook.meta import SourceError

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
table { border-collapse: collapse; margin: 0 0 1em; }
td, th { border: 1px solid #999; padding: 0.3em 0.5em; }
"""

# 한글에서 워드로 저장한 문서는 제목 스타일 이름이 "개요 N" / "제목 N"인 경우가 많다
DOCX_STYLE_MAP = "\n".join(
    f"p[style-name='{name} {n}'] => h{n}:fresh" for name in ("개요", "제목") for n in (1, 2, 3)
)


@dataclass
class Book:
    chapters: list  # [{"title": str, "parts": [html, ...]}]
    images: list    # [(파일명, bytes)]
    sample: str     # 언어 판별용 본문 일부


def _is_hangul_text(sample: str) -> bool:
    return len(re.findall(r"[가-힣]", sample)) > len(sample) * 0.1


# ---------------------------------------------------------------- PDF

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


def extract_pdf(pdf_path: Path) -> Book:
    doc = pymupdf.open(pdf_path)
    with doc:
        body = _body_size(doc)
        if body == 0:
            raise SourceError("글자가 없는 스캔 PDF라서 EPUB으로 바꿀 수 없습니다. (OCR 미지원)")

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
        return Book(chapters, images, " ".join(sample)[:5000])


# ---------------------------------------------------------------- 블록 -> 챕터 (DOCX/HWPX 공통)

def split_chapters(blocks: list[tuple[str, str, str]], default_title: str) -> list[dict]:
    """h1(없으면 h2)에서 챕터를 나눈다. blocks: [(kind, html, text)]."""
    break_kind = "h1" if any(k == "h1" for k, _, _ in blocks) else "h2"
    chapters = [{"title": "시작", "parts": []}]
    for kind, part, text in blocks:
        if kind == break_kind:
            chapters.append({"title": text or "제목 없음", "parts": []})
        chapters[-1]["parts"].append(part)
    if len(chapters) == 1:
        chapters[0]["title"] = default_title
    return chapters


def _sample(blocks) -> str:
    return " ".join(text for _, _, text in blocks if text)[:5000]


def _book_from_blocks(blocks, images, title: str) -> Book:
    if not any(text for _, _, text in blocks):
        raise SourceError("본문 글자를 찾지 못했습니다.")
    return Book(split_chapters(blocks, title), images, _sample(blocks))


def extract_hwpx(path: Path, title: str) -> Book:
    return _book_from_blocks(*hwpx.read_blocks(path), title)


def extract_hwp(path: Path, title: str) -> Book:
    return _book_from_blocks(*hwp5.read_blocks(path), title)


def extract_docx(path: Path, title: str) -> Book:
    images: list[tuple[str, bytes]] = []

    def keep_image(image):
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif"}.get(image.content_type)
        if ext is None:
            return {"src": ""}  # EMF/WMF 등은 건너뛴다 (아래에서 <img> 제거)
        with image.open() as f:
            images.append((f"img_{len(images) + 1}.{ext}", f.read()))
        return {"src": f"images/{images[-1][0]}", "alt": ""}

    try:
        with open(path, "rb") as f:
            result = mammoth.convert_to_html(f, style_map=DOCX_STYLE_MAP,
                                             convert_image=mammoth.images.img_element(keep_image))
    except Exception as exc:
        raise SourceError("DOCX 파일을 열 수 없습니다. 손상된 파일일 수 있습니다.") from exc

    root = lxml_html.fromstring(f"<div>{result.value}</div>")
    blocks = []
    for el in root:
        text = el.text_content().strip()
        serialized = etree.tostring(el, encoding="unicode", method="xml", with_tail=False)
        serialized = re.sub(r'<img[^>]*src=""[^>]*/>', "", serialized)
        if not text and "<img" not in serialized:
            continue
        kind = el.tag if el.tag in ("h1", "h2") else "body"
        blocks.append((kind, serialized, text))
    if not any(text for _, _, text in blocks):
        raise SourceError("본문 글자를 찾지 못했습니다.")
    return Book(split_chapters(blocks, title), images, _sample(blocks))


# ---------------------------------------------------------------- EPUB 조립

def write_epub(book: Book, epub_path: Path, title: str, author: str,
               cover_path: Path | None = None) -> int:
    chapters = [c for c in book.chapters if c["parts"]]
    if not chapters:
        raise SourceError("본문 글자를 찾지 못했습니다.")

    out = epub.EpubBook()
    out.set_identifier(str(uuid.uuid4()))
    out.set_title(title)
    out.set_language("ko" if _is_hangul_text(book.sample) else "en")
    if author:
        out.add_author(author)
    if cover_path and cover_path.exists():
        out.set_cover("cover.png", cover_path.read_bytes())

    style = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css",
                          content=CSS.encode())
    out.add_item(style)
    for name, data in book.images:
        ext = name.rsplit(".", 1)[-1].lower()
        media = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        out.add_item(epub.EpubItem(uid=name, file_name=f"images/{name}", media_type=media,
                                   content=data))

    items = []
    for number, chapter in enumerate(chapters, 1):
        item = epub.EpubHtml(title=chapter["title"], file_name=f"chap_{number:03d}.xhtml",
                             lang=out.language)
        item.content = "".join(chapter["parts"])
        item.add_item(style)
        out.add_item(item)
        items.append(item)

    out.toc = items
    out.add_item(epub.EpubNcx())
    out.add_item(epub.EpubNav())
    out.spine = ["nav", *items]
    epub.write_epub(str(epub_path), out)
    return len(items)


def to_epub(source: Path, epub_path: Path, kind: str, title: str, author: str,
            cover_path: Path | None = None) -> int:
    """내지 파일(kind: pdf/docx/hwpx)을 EPUB으로 만들고 챕터 수를 돌려준다."""
    if kind == "pdf":
        book = extract_pdf(source)
    elif kind == "docx":
        book = extract_docx(source, title)
    elif kind == "hwpx":
        book = extract_hwpx(source, title)
    elif kind == "hwp":
        book = extract_hwp(source, title)
    else:
        raise SourceError("지원하지 않는 내지 형식입니다.")
    return write_epub(book, epub_path, title, author, cover_path)
