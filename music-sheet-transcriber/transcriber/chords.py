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


def annotate(score) -> list[tuple[float, str]]:
    """`score` 에 코드 심볼을 삽입해 악보 위에 표기되게 한다(in place).

    코드 심볼은 마디 안에 넣어야 악보에 렌더링되므로, 마디 번호를 맞춰
    대상 파트의 각 마디 시작 지점에 삽입한다. 삽입된 이벤트 목록을 돌려준다.
    """
    from music21 import harmony

    parts = getattr(score, "parts", None)
    target = parts[0] if parts is not None and len(parts) else score
    target_measures = {m.number: m for m in target.getElementsByClass("Measure")}

    events: list[tuple[float, str]] = []
    for measure in score.chordify().getElementsByClass("Measure"):
        names: list[str] = []
        for c in measure.getElementsByClass("Chord"):
            names += [p.name for p in c.pitches]
        figure = _clean_symbol(names)
        if not figure:
            continue
        events.append((float(measure.offset), figure))
        try:
            symbol = harmony.ChordSymbol(figure)
        except Exception:
            continue  # 표기 불가한 심볼은 건너뜀
        dest = target_measures.get(measure.number)
        if dest is not None:
            dest.insert(0, symbol)
        else:
            target.insert(measure.offset, symbol)
    return events
