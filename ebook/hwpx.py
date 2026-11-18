"""한글(.hwpx) 내지 읽기: ZIP 안의 XML에서 제목/문단/표/그림을 뽑는다.

HWPX는 OWPML(XML) 기반이라 외부 프로그램 없이 읽을 수 있다. 옛 .hwp(바이너리)는
지원하지 않는다 (한글에서 HWPX나 PDF로 저장).

제목 판단: 문단 스타일 이름(개요 N / 제목 N), 문단 모양의 개요 수준, 그리고
본문보다 확연히 큰 글자 크기 순서로 본다. 네임스페이스 접두어는 파일마다 달라서
태그의 로컬 이름만 비교한다.
"""

import html
import io
import re
import statistics
import zipfile

from lxml import etree

from ebook.meta import SourceError

HEADING_STYLE_RE = re.compile(r"^(개요|제목|Outline|Heading)\s*(\d+)?$", re.I)
H1_RATIO = 1.5
H2_RATIO = 1.2
MAX_HEADING_CHARS = 80
KEEP_IMAGE_EXT = {"png", "jpg", "jpeg", "gif"}


def local(el) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def children(el, name: str) -> list:
    return [c for c in el if local(c) == name]


def _parse(zf: zipfile.ZipFile, name: str):
    try:
        return etree.fromstring(zf.read(name))
    except (KeyError, etree.XMLSyntaxError):
        return None


class _Header:
    """header.xml: 스타일 이름, 개요 수준, 글자 크기."""

    def __init__(self, root):
        self.styles, self.outline, self.heights = {}, {}, {}
        if root is None:
            return
        for el in root.iter():
            name = local(el)
            if name == "style":
                self.styles[el.get("id")] = el.get("name", "")
            elif name == "paraPr":
                for h in children(el, "heading"):
                    if h.get("type") == "OUTLINE":
                        self.outline[el.get("id")] = int(h.get("level", 0)) + 1
            elif name == "charPr" and el.get("height"):
                self.heights[el.get("id")] = int(el.get("height"))

    def level(self, p) -> int:
        """스타일/문단 모양으로 정해진 제목 수준 (없으면 0)."""
        match = HEADING_STYLE_RE.match(self.styles.get(p.get("styleIDRef"), "").strip())
        if match:
            return int(match.group(2) or 1)
        return self.outline.get(p.get("paraPrIDRef"), 0)

    def height(self, p) -> int:
        for run in children(p, "run"):
            return self.heights.get(run.get("charPrIDRef"), 0)
        return 0


def _t_text(t) -> str:
    parts = [t.text or ""]
    for child in t:
        if local(child) in ("tab", "lineBreak"):
            parts.append(" ")
        parts.append(child.tail or "")
    return "".join(parts)


def para_text(p) -> str:
    """문단 안의 글자 (표·그림 안쪽 문단은 제외)."""
    return "".join(_t_text(t) for run in children(p, "run") for t in children(run, "t")).strip()


class _Reader:
    def __init__(self, zf: zipfile.ZipFile):
        self.zf = zf
        self.header = _Header(_parse(zf, "Contents/header.xml"))
        self.manifest = {}
        hpf = _parse(zf, "Contents/content.hpf")
        if hpf is not None:
            for item in hpf.iter():
                if local(item) == "item" and item.get("id"):
                    self.manifest[item.get("id")] = item.get("href", "")
        self.images: list[tuple[str, bytes]] = []

    def image_html(self, pic) -> str:
        ref = next((el.get("binaryItemIDRef") for el in pic.iter()
                    if local(el) == "img" and el.get("binaryItemIDRef")), None)
        if not ref:
            return ""
        names = [n for n in self.zf.namelist() if n.startswith("BinData/")]
        href = self.manifest.get(ref)
        path = next((n for n in names if href and n.endswith(href.split("/")[-1])), None) \
            or next((n for n in names if n.rsplit("/", 1)[-1].rsplit(".", 1)[0] == ref), None)
        if not path:
            return ""
        ext = path.rsplit(".", 1)[-1].lower()
        data = self.zf.read(path)
        if ext not in KEEP_IMAGE_EXT:  # bmp 등은 PNG로 바꿔 넣는다
            try:
                from PIL import Image
                buf = io.BytesIO()
                Image.open(io.BytesIO(data)).convert("RGB").save(buf, "PNG")
                data, ext = buf.getvalue(), "png"
            except Exception:
                return ""
        name = f"img_{len(self.images) + 1}.{'jpg' if ext == 'jpeg' else ext}"
        self.images.append((name, data))
        return f'<p><img src="images/{name}" alt=""/></p>'

    def table_html(self, tbl) -> str:
        rows = []
        for tr in children(tbl, "tr"):
            cells = []
            for tc in children(tr, "tc"):
                span = next(iter(children(tc, "cellSpan")), None)
                attrs = ""
                if span is not None:
                    attrs = "".join(f' {a.lower()}="{span.get(a)}"' for a in ("colSpan", "rowSpan")
                                    if span.get(a, "1") != "1")
                paras = [para_text(p) for sub in children(tc, "subList") for p in children(sub, "p")]
                cells.append(f"<td{attrs}>{'<br/>'.join(html.escape(t) for t in paras if t)}</td>")
            rows.append(f"<tr>{''.join(cells)}</tr>")
        return f'<table border="1">{"".join(rows)}</table>'

    def blocks(self, p, body_height: float) -> list[tuple[str, str, str]]:
        """문단 하나 -> [(kind, html, text)]. kind: h1 / h2 / body."""
        out = []
        text = para_text(p)
        if text:
            level = self.header.level(p)
            height = self.header.height(p)
            short = len(text) <= MAX_HEADING_CHARS
            if not level and short and body_height:
                level = 1 if height >= body_height * H1_RATIO else 2 if height >= body_height * H2_RATIO else 0
            tag = f"h{level}" if 0 < level <= 3 else "p"
            kind = tag if tag in ("h1", "h2") else "body"
            out.append((kind, f"<{tag}>{html.escape(text)}</{tag}>", text))
        for run in children(p, "run"):
            for child in run:
                if local(child) == "tbl":
                    out.append(("body", self.table_html(child), ""))
                elif local(child) == "pic":
                    img = self.image_html(child)
                    if img:
                        out.append(("body", img, ""))
        return out


def _section_names(zf: zipfile.ZipFile) -> list[str]:
    names = [n for n in zf.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)]
    return sorted(names, key=lambda n: int(re.findall(r"\d+", n)[-1]))


def read_blocks(path) -> tuple[list[tuple[str, str, str]], list[tuple[str, bytes]]]:
    """(블록 목록, 이미지 목록). 글이 없으면 SourceError."""
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise SourceError("HWPX 파일을 열 수 없습니다. 손상된 파일일 수 있습니다.") from exc
    with zf:
        reader = _Reader(zf)
        paragraphs = []
        for name in _section_names(zf):
            root = _parse(zf, name)
            if root is not None:
                paragraphs += children(root, "p")
        sizes = []
        for p in paragraphs:
            text = para_text(p)
            sizes += [reader.header.height(p)] * len(text)
        body = statistics.median([s for s in sizes if s]) if any(sizes) else 0
        blocks = [b for p in paragraphs for b in reader.blocks(p, body)]
        return blocks, reader.images


def read_meta(path) -> dict:
    """content.hpf의 제목/작성자 등 (best effort)."""
    info = {"title": "", "author": "", "subject": "", "keywords": "", "created": "", "modified": ""}
    with zipfile.ZipFile(path) as zf:
        root = _parse(zf, "Contents/content.hpf")
    if root is None:
        return info
    for el in root.iter():
        name = local(el)
        value = (el.text or "").strip()
        if name == "title":
            info["title"] = value
        elif name == "meta":
            key = (el.get("name") or "").lower()
            target = {"creator": "author", "subject": "subject", "keyword": "keywords",
                      "keywords": "keywords", "createddate": "created",
                      "modifieddate": "modified"}.get(key)
            if target:
                info[target] = value[:10] if target in ("created", "modified") else value
    return info
