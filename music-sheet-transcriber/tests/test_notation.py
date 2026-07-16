"""표기 단계 테스트: MIDI → MusicXML 변환이 실제로 동작하는지 검증.

무거운 AI 모델(basic-pitch/demucs) 없이도 돌 수 있는 부분만 확인한다.
music21 이 없으면 skip.
"""
from pathlib import Path

import pytest

music21 = pytest.importorskip("music21")

from transcriber import notation


def _make_scale_midi(path: Path) -> Path:
    """C 장음계 한 마디짜리 MIDI 를 합성해 저장."""
    from music21 import stream, note

    s = stream.Stream()
    for name in ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]:
        s.append(note.Note(name, quarterLength=0.5))
    s.write("midi", fp=str(path))
    return path


def test_midi_to_musicxml_roundtrip(tmp_path):
    midi = _make_scale_midi(tmp_path / "scale.mid")

    xml = notation.midi_to_musicxml(midi, tmp_path)

    assert xml.exists()
    assert xml.suffix == ".musicxml"
    text = xml.read_text(encoding="utf-8")
    # MusicXML 골격과 실제 음표가 담겼는지 확인
    assert "<score-partwise" in text
    assert "<step>C</step>" in text
    assert "<step>G</step>" in text
