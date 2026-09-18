"""박자 정렬 테스트: 어긋난 음 시각이 박 그리드에 스냅되는지 검증.

librosa/pretty_midi 없이 순수 로직(_events_to_score)만 확인한다.
"""
import pytest

pytest.importorskip("music21")

from music21 import note

from transcriber import beats

# 120 BPM: 0.5초 간격의 박
BEATS = [i * 0.5 for i in range(9)]  # 0.0 ~ 4.0


def test_off_grid_notes_snap_to_beats():
    # 살짝 어긋난(±0.03초) 음들이 정확한 박 길이로 스냅돼야
    events = [
        (0.02, 0.48, 60),   # 1박
        (0.51, 0.97, 62),   # 1박
        (1.03, 1.98, 64),   # 2박
        (2.02, 2.49, 65),   # 1박
    ]
    score = beats._events_to_score(events, BEATS, subdivisions=4, tempo_bpm=120)

    notes = list(score.recurse().getElementsByClass(note.Note))
    assert [n.nameWithOctave for n in notes] == ["C4", "D4", "E4", "F4"]
    assert [float(n.quarterLength) for n in notes] == [1.0, 1.0, 2.0, 1.0]


def test_overlapping_notes_reduced_to_higher():
    # 겹치는 두 음 -> 더 높은 음이 우선
    events = [(0.0, 1.0, 60), (0.0, 1.0, 67)]
    score = beats._events_to_score(events, BEATS, subdivisions=4)

    names = [n.nameWithOctave for n in score.recurse().getElementsByClass(note.Note)]
    assert "G4" in names  # 높은 음
    # 단선율이므로 화음이 남지 않음
    from music21 import chord as m21chord
    assert list(score.recurse().getElementsByClass(m21chord.Chord)) == []


def test_too_few_beats_raises():
    with pytest.raises(ValueError):
        beats._events_to_score([(0.0, 1.0, 60)], [0.0], subdivisions=4)
