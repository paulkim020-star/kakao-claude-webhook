"""코드 인식 테스트: 블록 화음 스코어에서 코드 심볼이 제대로 나오는지 검증."""
import pytest

pytest.importorskip("music21")

from music21 import stream, chord as m21chord

from transcriber import chords


def _block_chords_score():
    """C - F - G - Am - G7 순서의 온음표 화음 스코어."""
    s = stream.Stream()
    for pcs in [
        ["C4", "E4", "G4"],   # C
        ["F4", "A4", "C5"],   # F
        ["G4", "B4", "D5"],   # G
        ["A4", "C5", "E5"],   # Am
        ["G4", "B4", "D5", "F5"],  # G7
    ]:
        s.append(m21chord.Chord(pcs, quarterLength=4))
    return s.makeMeasures()


def test_detect_returns_clean_symbols():
    events = chords.detect(_block_chords_score())
    figures = [fig for _off, fig in events]
    assert figures == ["C", "F", "G", "Am", "G7"]


def test_annotate_inserts_chord_symbols():
    from music21 import harmony

    score = _block_chords_score()
    events = chords.annotate(score)

    assert len(events) == 5
    inserted = list(score.recurse().getElementsByClass(harmony.ChordSymbol))
    assert len(inserted) == 5
