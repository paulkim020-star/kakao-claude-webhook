"""옛 한글(.hwp, HWP 5.x) 내지 읽기: OLE 안의 BodyText 레코드에서 글, 표, 제목을 뽑는다.

HWP 5.x는 OLE 컨테이너 안에 압축된 레코드 열(BodyText/SectionN)이 들어 있는 바이너리 형식이다.
레코드 헤더는 32비트: 태그(10비트) | 수준(10비트) | 크기(12비트, 0xFFF면 다음 4바이트가 크기).
암호가 걸린 문서와 배포용 문서(본문이 암호화됨)는 읽지 않는다. 그림은 아직 옮기지 않는다.
"""

import html
import re
import statistics
import struct
import zlib

import olefile

from ebook.meta import SourceError

TAG_STYLE, TAG_CHAR_SHAPE = 26, 21            # DocInfo
TAG_PARA_HEADER, TAG_PARA_TEXT, TAG_PARA_CHAR_SHAPE = 66, 67, 68
TAG_CTRL_HEADER, TAG_LIST_HEADER, TAG_TABLE = 71, 72, 77

HEADING_STYLE_RE = re.compile(r"^(개요|제목|Outline|Heading)\s*(\d+)?$", re.I)
H1_RATIO, H2_RATIO, MAX_HEADING_CHARS = 1.5, 1.2, 80
SKIP_CONTROLS = {b"daeh", b"toof"}            # 머리말 / 꼬리말: 본문이 아니다
TABLE_CONTROL = b" lbt"
# 글자 코드 중 뒤에 14바이트가 더 붙는 컨트롤 (총 8글자 폭)
WIDE_CODES = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}


def is_hwp(ole: olefile.OleFileIO) -> bool:
    return ole.exists("FileHeader") and ole.openstream("FileHeader").read(17) == b"HWP Document File"


def _header(ole):
    data = ole.openstream("FileHeader").read()
    return struct.unpack("<I", data[32:36])[0], struct.unpack("<I", data[36:40])[0]  # (version, flags)


def _stream(ole, name: str, compressed: bool) -> bytes:
    raw = ole.openstream(name).read()
    return zlib.decompress(raw, -15) if compressed else raw


def records(data: bytes):
    """(태그, 수준, 내용) 열."""
    pos = 0
    while pos + 4 <= len(data):
        value = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        tag, level, size = value & 0x3FF, (value >> 10) & 0x3FF, value >> 20
        if size == 0xFFF:
            size = struct.unpack_from("<I", data, pos)[0]
            pos += 4
        yield tag, level, data[pos:pos + size]
        pos += size


def _escape(text: str) -> str:
    return html.escape(text).replace("\n", "<br/>")  # 문단 안의 줄바꿈은 그대로 보여준다


def para_text(data: bytes) -> str:
    """PARA_TEXT 내용(UTF-16LE + 컨트롤 글자)에서 보이는 글자만 뽑는다."""
    out, i = [], 0
    while i + 2 <= len(data):
        code = struct.unpack_from("<H", data, i)[0]
        if code in WIDE_CODES:
            if code == 9:
                out.append(" ")
            i += 16
        elif code < 32:
            if code == 10:
                out.append("\n")
            elif code == 24:
                out.append("-")
            elif code in (30, 31):
                out.append(" ")
            i += 2
        else:
            out.append(chr(code))
            i += 2
    return "".join(out).strip()


def _doc_info(ole, compressed: bool):
    styles, sizes = [], []
    for tag, _, body in records(_stream(ole, "DocInfo", compressed)):
        if tag == TAG_STYLE:
            n = struct.unpack_from("<H", body, 0)[0]
            styles.append(body[2:2 + 2 * n].decode("utf-16le", "replace"))
        elif tag == TAG_CHAR_SHAPE and len(body) >= 46:
            sizes.append(struct.unpack_from("<i", body, 42)[0])
    return styles, sizes


class _Para:
    def __init__(self, header: bytes):
        self.style = header[10] if len(header) > 10 else 0
        self.text = ""
        self.size = 0


def _read_section(data: bytes, styles: list[str], sizes: list[int]):
    """한 섹션 -> 블록 목록 [(kind, html, text)]와 글자 크기 표본."""
    blocks, samples = [], []
    paras: list[_Para] = []      # 지금 모으는 문단들 (표 밖이면 하나씩 블록으로 낸다)
    skip_level = None            # 머리말/꼬리말 안쪽은 건너뛴다
    table = None                 # {"level", "rows", "cells": [...]}
    cell = None

    def flush_para(para):
        text = para.text.strip()
        if not text:
            return
        samples.append((para.size, len(text)))
        title = styles[para.style] if para.style < len(styles) else ""
        match = HEADING_STYLE_RE.match(title.strip())
        level = int(match.group(2) or 1) if match else 0
        blocks.append(("para", para, level, text))

    def close_table():
        nonlocal table, cell
        if table and table["cells"]:
            rows: dict[int, list] = {}
            for c in table["cells"]:
                rows.setdefault(c["row"], []).append(c)
            body = ""
            for r in sorted(rows):
                tds = ""
                for c in sorted(rows[r], key=lambda c: c["col"]):
                    attrs = "".join(f' {name}="{c[name]}"' for name in ("colspan", "rowspan") if c[name] > 1)
                    # 좁은 칸의 짧은 라벨(예: "종 이")은 공백에서 줄바꿈되지 않게 한다
                    content = "<br/>".join(_escape(t.replace(" ", "\u00a0") if len(t) <= 8 else t)
                                           for t in c["texts"] if t)
                    tds += f"<td{attrs}>{content}</td>"
                body += f"<tr>{tds}</tr>"
            blocks.append(("table", f'<table border="1">{body}</table>',
                           " ".join(t for c in table["cells"] for t in c["texts"])))
        table = cell = None

    current: _Para | None = None
    for tag, level, body in records(data):
        if skip_level is not None:
            if level > skip_level:
                continue
            skip_level = None
        if table and level <= table["level"]:
            close_table()
        if tag == TAG_CTRL_HEADER:
            ctrl = body[:4]
            if ctrl in SKIP_CONTROLS:
                skip_level = level
            elif ctrl == TABLE_CONTROL and table is None:
                table = {"level": level, "cells": []}
        elif tag == TAG_LIST_HEADER and table and level == table["level"] + 1:
            col, row, colspan, rowspan = struct.unpack_from("<4H", body, 8)
            cell = {"col": col, "row": row, "colspan": colspan or 1, "rowspan": rowspan or 1, "texts": []}
            table["cells"].append(cell)
        elif tag == TAG_PARA_HEADER:
            if current is not None and not table:
                flush_para(current)
            current = _Para(body)
            if table and cell is not None:
                cell["texts"].append("")
        elif tag == TAG_PARA_TEXT and current is not None:
            text = para_text(body)
            if table and cell is not None:
                cell["texts"][-1] = (cell["texts"][-1] + " " + text).strip()
            else:
                current.text = text
        elif tag == TAG_PARA_CHAR_SHAPE and current is not None and len(body) >= 8:
            shape = struct.unpack_from("<I", body, 4)[0]
            current.size = sizes[shape] if shape < len(sizes) else 0
    if current is not None and not table:
        flush_para(current)
    close_table()
    return blocks, samples


def read_blocks(path):
    """(블록 목록, 이미지 목록). 암호/배포용 문서와 글이 없는 문서는 SourceError."""
    try:
        ole = olefile.OleFileIO(path)
    except OSError as exc:
        raise SourceError("한글 파일을 열 수 없습니다. 손상된 파일일 수 있습니다.") from exc
    with ole:
        if not is_hwp(ole):
            raise SourceError("한글(.hwp) 문서가 아닙니다.")
        _, flags = _header(ole)
        if flags & 0b10:
            raise SourceError("암호가 걸린 한글 문서는 읽을 수 없습니다. 암호를 풀고 다시 저장해 주세요.")
        if flags & 0b100:
            raise SourceError("배포용 한글 문서는 읽을 수 없습니다. 한글에서 일반 문서로 저장해 주세요.")
        compressed = bool(flags & 1)
        styles, sizes = _doc_info(ole, compressed)
        sections = sorted((s for s in ole.listdir() if len(s) == 2 and s[0] == "BodyText"),
                          key=lambda s: int(re.sub(r"\D", "", s[1]) or 0))
        raw_blocks, samples = [], []
        for section in sections:
            blocks, got = _read_section(_stream(ole, "/".join(section), compressed), styles, sizes)
            raw_blocks += blocks
            samples += got
        weighted = [size for size, n in samples for _ in range(min(n, 50)) if size]
        body = statistics.median(weighted) if weighted else 0
        out = []
        for item in raw_blocks:
            if item[0] == "table":
                out.append(("body", item[1], item[2]))
                continue
            _, para, level, text = item
            if not level and body and len(text) <= MAX_HEADING_CHARS:
                level = 1 if para.size >= body * H1_RATIO else 2 if para.size >= body * H2_RATIO else 0
            tag = f"h{level}" if 0 < level <= 3 else "p"
            out.append((f"h{level}" if tag != "p" and level <= 2 else "body",
                        f"<{tag}>{_escape(text)}</{tag}>", text))
        return out, []


def read_meta(path) -> dict:
    """HwpSummaryInformation(OLE 속성 집합)의 제목/작성자 등 (best effort)."""
    info = {"title": "", "author": "", "subject": "", "keywords": "", "created": "", "modified": ""}
    try:
        with olefile.OleFileIO(path) as ole:
            data = ole.openstream("\x05HwpSummaryInformation").read()
        offset = struct.unpack_from("<I", data, 44)[0]
        count = struct.unpack_from("<I", data, offset + 4)[0]
        names = {2: "title", 3: "subject", 4: "author", 5: "keywords"}
        for i in range(count):
            pid, off = struct.unpack_from("<II", data, offset + 8 + 8 * i)
            if pid in names:
                kind = struct.unpack_from("<I", data, offset + off)[0]
                n = struct.unpack_from("<I", data, offset + off + 4)[0]
                start = offset + off + 8
                if kind == 0x1F:
                    info[names[pid]] = data[start:start + 2 * n].decode("utf-16le", "replace").strip("\x00 ")
                elif kind == 0x1E:
                    info[names[pid]] = data[start:start + n].decode("cp949", "replace").strip("\x00 ")
    except Exception:
        pass
    return info
