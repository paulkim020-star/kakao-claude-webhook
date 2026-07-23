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


def test_readability_adds_key_and_time_signature(tmp_path):
    midi = _make_scale_midi(tmp_path / "scale.mid")

    xml = notation.midi_to_musicxml(
        midi, tmp_path, detect_key=True, time_signature="4/4"
    )

    text = xml.read_text(encoding="utf-8")
    assert "<key>" in text   # 조표 삽입됨
    assert "<time>" in text  # 박자표 삽입됨
    assert "<beats>4</beats>" in text


def _make_waltz_midi(path):
    """3/4 박자표가 심긴 MIDI 를 만든다."""
    from music21 import stream, note, meter

    s = stream.Stream()
    s.append(meter.TimeSignature("3/4"))
    for _ in range(4):
        for name in ["C4", "E4", "G4"]:
            s.append(note.Note(name, quarterLength=1))
    s.write("midi", fp=str(path))
    return path


def test_time_signature_auto_respects_embedded_meter(tmp_path):
    midi = _make_waltz_midi(tmp_path / "waltz.mid")

    xml = notation.midi_to_musicxml(midi, tmp_path, time_signature="auto")

    text = xml.read_text(encoding="utf-8")
    assert "<beats>3</beats>" in text  # MIDI 의 3/4 가 보존됨


def test_time_signature_explicit_overrides(tmp_path):
    midi = _make_waltz_midi(tmp_path / "waltz.mid")

    xml = notation.midi_to_musicxml(midi, tmp_path, time_signature="4/4")

    text = xml.read_text(encoding="utf-8")
    assert "<beats>4</beats>" in text  # 강제 지정이 3/4 를 덮어씀
    assert "<beats>3</beats>" not in text


def _make_d_major_midi(path):
    """D 장조(♯2개) 음계 MIDI 를 만든다."""
    from music21 import stream, note

    s = stream.Stream()
    for _ in range(2):
        for name in ["D4", "E4", "F#4", "G4", "A4", "B4", "C#5", "D5"]:
            s.append(note.Note(name, quarterLength=0.5))
    s.write("midi", fp=str(path))
    return path


def test_transpose_easy_moves_to_c_major(tmp_path):
    midi = _make_d_major_midi(tmp_path / "dmaj.mid")

    xml = notation.midi_to_musicxml(midi, tmp_path, transpose="easy")

    text = xml.read_text(encoding="utf-8")
    # D 장조(♯2) → C 장조(♯♭ 0): 조표가 0 으로, F# 이 사라져야 함
    assert "<fifths>0</fifths>" in text
    assert "alter" not in text  # 임시표/조표 변화음이 없음(전부 흰건반)


def test_transpose_off_keeps_original_key(tmp_path):
    midi = _make_d_major_midi(tmp_path / "dmaj.mid")

    xml = notation.midi_to_musicxml(midi, tmp_path, transpose="off")

    text = xml.read_text(encoding="utf-8")
    assert "<fifths>2</fifths>" in text  # D 장조 조표(♯2) 유지


def test_transpose_semitones_up(tmp_path):
    # C 조에서 +2 반음(키 올림) -> ♯2 (D 조 축)
    midi = _make_scale_midi(tmp_path / "c.mid")

    xml = notation.midi_to_musicxml(midi, tmp_path, transpose="+2")

    assert "<fifths>2</fifths>" in xml.read_text(encoding="utf-8")


def test_transpose_semitones_down(tmp_path):
    # C 조에서 -2 반음(키 내림) -> ♭2 (Bb 조 축)
    midi = _make_scale_midi(tmp_path / "c.mid")

    xml = notation.midi_to_musicxml(midi, tmp_path, transpose="-2")

    assert "<fifths>-2</fifths>" in xml.read_text(encoding="utf-8")


def test_with_chords_adds_harmony(tmp_path):
    from music21 import stream, chord as m21chord

    s = stream.Stream()
    for pcs in [["C4", "E4", "G4"], ["G4", "B4", "D5"]]:
        s.append(m21chord.Chord(pcs, quarterLength=4))
    midi = tmp_path / "prog.mid"
    s.write("midi", fp=str(midi))

    xml = notation.midi_to_musicxml(midi, tmp_path, with_chords=True)

    text = xml.read_text(encoding="utf-8")
    assert "<harmony" in text  # 코드 심볼이 harmony 요소로 렌더링됨


def test_chords_from_separate_source_midi(tmp_path):
    """멜로디는 단선율이라 코드가 안 나오지만, 반주 MIDI 를 주면 그 코드가 얹힌다."""
    from music21 import stream, note, chord as m21chord

    # 멜로디: 단선율 (코드 정보 없음)
    mel = stream.Stream()
    for name in ["C5", "E5", "G5", "C6"]:
        mel.append(note.Note(name, quarterLength=4))
    melody_midi = tmp_path / "vocals.mid"
    mel.write("midi", fp=str(melody_midi))

    # 반주: 화음 (여기서 코드가 나옴)
    acc = stream.Stream()
    for pcs in [["C4", "E4", "G4"], ["G4", "B4", "D5"]]:
        acc.append(m21chord.Chord(pcs, quarterLength=4))
    acc_midi = tmp_path / "no_vocals.mid"
    acc.write("midi", fp=str(acc_midi))

    xml = notation.midi_to_musicxml(
        melody_midi, tmp_path, with_chords=True, chord_source_midi=acc_midi
    )

    text = xml.read_text(encoding="utf-8")
    assert "<harmony" in text  # 반주에서 뽑은 코드가 멜로디 악보에 얹힘
    assert "<root-step>C</root-step>" in text


def test_musicxml_to_svg_renders():
    verovio = pytest.importorskip("verovio")  # noqa: F841

    import tempfile
    from music21 import stream, note

    with tempfile.TemporaryDirectory() as d:
        s = stream.Stream()
        for name in ["C4", "E4", "G4", "C5"]:
            s.append(note.Note(name, quarterLength=1))
        xml = f"{d}/mel.musicxml"
        s.write("musicxml", fp=xml)

        pages = notation.musicxml_to_svg(xml)

    assert len(pages) >= 1
    assert "<svg" in pages[0]
