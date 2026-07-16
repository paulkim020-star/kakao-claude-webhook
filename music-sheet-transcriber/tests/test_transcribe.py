"""엔진 선택 및 파이프라인 라우팅 검증.

무거운 모델(basic-pitch/pop2piano) 을 실제로 돌리지 않고, 엔진 디스패치와
pop2piano 분기(스템 분리 생략 + 44100Hz)를 monkeypatch 로 확인한다.
"""
from pathlib import Path

import pytest

from transcriber import audio, notation, pipeline, separate, transcribe


def test_unknown_engine_raises():
    with pytest.raises(ValueError):
        transcribe.to_midi("x.wav", "out", engine="does-not-exist")


def _patch_pipeline(monkeypatch, calls, tmp_path):
    def fake_to_wav(src, dst, sample_rate=audio.TARGET_SR):
        calls["sr"] = sample_rate
        p = Path(dst) / "a.wav"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        return p

    def fake_separate(src, dst, stem="vocals"):
        calls["separated"] = stem
        p = Path(dst) / f"{stem}.wav"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        return p

    def fake_to_midi(audio_path, dst, engine="basic-pitch", composer="composer1"):
        calls["engine"] = engine
        p = Path(dst) / "a.mid"
        p.write_bytes(b"")
        return p

    def fake_xml(midi, dst, with_chords=False):
        p = Path(dst) / "a.musicxml"
        p.write_text("x")
        return p

    monkeypatch.setattr(audio, "to_wav", fake_to_wav)
    monkeypatch.setattr(separate, "separate", fake_separate)
    monkeypatch.setattr(transcribe, "to_midi", fake_to_midi)
    monkeypatch.setattr(notation, "midi_to_musicxml", fake_xml)


def test_pop2piano_skips_separation_and_uses_44100(monkeypatch, tmp_path):
    calls: dict = {}
    _patch_pipeline(monkeypatch, calls, tmp_path)

    pipeline.run(
        "song.mp3", out_dir=tmp_path, engine="pop2piano",
        stem="vocals", make_pdf=False,
    )

    assert "separated" not in calls  # 스템 분리 생략
    assert calls["sr"] == transcribe.POP2PIANO_SR  # 44100Hz
    assert calls["engine"] == "pop2piano"


def test_basic_pitch_separates_and_uses_default_sr(monkeypatch, tmp_path):
    calls: dict = {}
    _patch_pipeline(monkeypatch, calls, tmp_path)

    pipeline.run(
        "song.mp3", out_dir=tmp_path, engine="basic-pitch",
        stem="vocals", make_pdf=False,
    )

    assert calls["separated"] == "vocals"  # 스템 분리 수행
    assert calls["sr"] == audio.TARGET_SR
    assert calls["engine"] == "basic-pitch"
