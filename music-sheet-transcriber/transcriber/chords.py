"""코드(반주) 인식: 스코어에서 마디별 코드 심볼을 추정한다.

music21 로 여러 성부를 세로로 합친(chordify) 뒤, 마디마다 울리는 음들을
모아 루트+성질로 코드 심볼(C, Am, G7 ...)을 뽑는다. 슬래시(자리바꿈) 표기
대신 리드시트에 쓰는 깔끔한 심볼을 목표로 한다.

주의: 단선율(보컬 멜로디만) MIDI 에서는 화성 정보가 부족해 코드 추정이
부정확하다. 반주가 포함된 다성 MIDI(예: 'other' 스템, 원본 통짜)에서 잘 된다.
"""
from __future__ import annotations

_QUALITY_SUFFIX = {"major": "", "minor": "m", "diminished": "dim", "augmented": "+"}


def _clean_symbol(pitch_names: list[str]) -> str | None:
    """음 이름 목록에서 루트+성질 기반의 코드 심볼 문자열을 만든다."""
    from music21 import chord

    uniq = list(dict.fromkeys(pitch_names))
    if len(uniq) < 3:  # 3음 미만은 코드로 보지 않음
        return None

    c = chord.Chord(uniq)
    try:
        root = c.root().name.replace("-", "b")  # E- -> Eb
    except Exception:
        return None

    suffix = _QUALITY_SUFFIX.get(c.quality, "")
    if c.isSeventh():
        seventh = c.seventh
        is_major_seventh = (
            c.quality == "major"
            and seventh is not None
            and seventh.name == c.root().transpose("M7").name
        )
        suffix = "maj7" if is_major_seventh else suffix + "7"
    return root + suffix


def detect(score) -> list[tuple[float, str]]:
    """마디별 코드 심볼 목록 `[(offset, figure), ...]` 을 돌려준다."""
    chordified = score.chordify()
    events: list[tuple[float, str]] = []
    for measure in chordified.getElementsByClass("Measure"):
        names: list[str] = []
        for c in measure.getElementsByClass("Chord"):
            names += [p.name for p in c.pitches]
        figure = _clean_symbol(names)
        if figure:
            events.append((float(measure.offset), figure))
    return events


def _measure_figures(score) -> dict[int, str]:
    """마디 번호 -> 코드 심볼 문자열. 각 마디의 울리는 음을 모아 하나로 판정한다."""
    figures: dict[int, str] = {}
    for measure in score.chordify().getElementsByClass("Measure"):
        names: list[str] = []
        for c in measure.getElementsByClass("Chord"):
            names += [p.name for p in c.pitches]
        figure = _clean_symbol(names)
        if figure:
            figures[measure.number] = figure
    return figures


def _insert(target_score, figures: dict[int, str]) -> list[tuple[int, str]]:
    """`figures`(마디→코드)를 target_score 각 마디 위에 코드 심볼로 얹는다.

    코드 심볼은 오선 위에 텍스트(C, Am, G7...)로만 표기되고 음표(오선)에는
    반영되지 않는다 - 기타 반주용 리드시트 방식. 삽입된 목록을 돌려준다.
    """
    from music21 import harmony

    parts = getattr(target_score, "parts", None)
    target = parts[0] if parts is not None and len(parts) else target_score
    measures = {m.number: m for m in target.getElementsByClass("Measure")}

    inserted: list[tuple[int, str]] = []
    for number, figure in sorted(figures.items()):
        dest = measures.get(number)
        if dest is None:
            continue
        try:
            symbol = harmony.ChordSymbol(figure)
            symbol.writeAsChord = False  # 오선 위 심볼로만, 음표로는 넣지 않음
        except Exception:
            continue  # 표기 불가한 심볼은 건너뜀
        dest.insert(0, symbol)
        inserted.append((number, figure))
    return inserted


def annotate(score) -> list[tuple[int, str]]:
    """`score` 자체의 화음에서 코드를 뽑아 그 위에 표기한다(in place)."""
    return _insert(score, _measure_figures(score))


def annotate_from(target_score, source_score) -> list[tuple[int, str]]:
    """`source_score`(반주)의 화음에서 코드를 뽑아 `target_score`(멜로디) 위에 얹는다.

    보컬 멜로디는 단선율이라 코드가 안 나오므로, 분리된 반주에서 코드를 뽑아
    같은 마디 번호의 멜로디 위에 표기한다(오선엔 반영 안 함).
    """
    return _insert(target_score, _measure_figures(source_score))
