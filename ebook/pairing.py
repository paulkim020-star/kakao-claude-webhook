"""파일 이름의 '표지' / '내지'로 한 권을 묶는 규칙.

  나의책_표지.png + 나의책_내지.docx  ->  "나의책" 한 권 (표지 이미지 + 내지)
  표지.pdf + 내지.hwpx                 ->  이름 없이 한 권 (제목은 파일 속성에서)
  이름에 표지/내지가 없는 파일         ->  그 파일 하나가 한 권 (PDF/DOCX/HWPX만)

같은 이름(나의책)의 표지가 둘 이상이거나 내지가 둘 이상이면 첫 번째 짝만 묶고
나머지 내지는 각각 한 권이 된다. 짝 없는 표지, 이미지·표지가 아닌 표지는 거절한다.
"""

import re
from dataclasses import dataclass
from pathlib import Path

ROLE_RE = re.compile(r"표지|내지")
SEPARATORS = " _-.()[]"
BOOK_KINDS = {"pdf", "docx", "hwp", "hwpx"}
COVER_KINDS = {"image", "pdf"}


@dataclass
class Staged:
    """저장 폴더에 임시로 받아 둔 업로드 파일."""
    name: str   # 원래 파일명
    path: Path  # 임시 저장 경로
    kind: str | None  # meta.sniff() 결과


@dataclass
class Plan:
    interior: Staged
    cover: Staged | None
    key: str  # 이름에서 뽑은 제목 후보 (없으면 "")


def split_role(stem: str) -> tuple[str | None, str]:
    """'나의책_표지' -> ('표지', '나의책')"""
    match = ROLE_RE.search(stem)
    if not match:
        return None, stem
    key = (stem[:match.start()] + stem[match.end():]).strip(SEPARATORS)
    return match.group(), key


def make_plans(files: list[Staged]) -> tuple[list[Plan], list[tuple[Staged, str]]]:
    """(만들 책 목록, 거절된 파일과 사유 코드). 사유: doc / bad / lone_cover / bad_cover"""
    plans, rejected = [], []
    covers: dict[str, Staged] = {}
    interiors: dict[str, list[Staged]] = {}

    for f in files:
        if f.kind == "doc":
            rejected.append((f, "doc"))
            continue
        role, key = split_role(Path(f.name).stem)
        if role == "표지":
            if f.kind in COVER_KINDS:
                covers.setdefault(key, f)
            else:
                rejected.append((f, "bad_cover"))
        elif f.kind not in BOOK_KINDS:
            rejected.append((f, "bad"))  # 이미지인데 이름에 표지가 없는 경우 등
        elif role == "내지":
            interiors.setdefault(key, []).append(f)
        else:
            plans.append(Plan(f, None, ""))  # 역할 없는 파일은 그 자체로 한 권

    for key, group in interiors.items():
        for i, interior in enumerate(group):
            plans.append(Plan(interior, covers.pop(key, None) if i == 0 else None, key))
    rejected += [(c, "lone_cover") for c in covers.values()]
    return plans, rejected
