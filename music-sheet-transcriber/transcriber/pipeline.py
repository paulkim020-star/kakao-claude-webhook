"""전체 채보 파이프라인 오케스트레이션.

    mp3/mp4 ─▶ WAV ─▶ (선택) 스템 분리 ─▶ MIDI ─▶ MusicXML ─▶ PDF
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import audio, notation, separate, transcribe


@dataclass
class Result:
    wav: Path
    stem_wav: Path | None
    midi: Path
    musicxml: Path
    pdf: Path | None


def run(
    src: str | Path,
    out_dir: str | Path = "out",
    stem: str | None = "vocals",
    make_pdf: bool = True,
    chords: bool = False,
    engine: str = transcribe.BASIC_PITCH,
    composer: str = "composer1",
    time_signature: str = "auto",
    transpose: str = "off",
) -> Result:
    """`src` 오디오를 채보한다.

    Args:
        src: 입력 오디오/영상 (mp3, mp4, m4a, wav ...).
        out_dir: 중간 산출물과 결과가 쌓이는 폴더.
        stem: 분리해서 채보할 파트("vocals" 등). None 이면 원본 통째로 채보.
        make_pdf: True 면 MuseScore 로 PDF 까지 렌더링(없으면 MusicXML 까지만).
        chords: True 면 마디별 코드 심볼을 추정해 악보에 표기(다성 MIDI 에서 유효).
        engine: 채보 백엔드. ``basic-pitch``(파트/멜로디용) 또는
            ``pop2piano``(대중가요 → 피아노 커버).
        composer: pop2piano 스타일 프리셋. 그 외 엔진에서는 무시.
        time_signature: ``"auto"`` 면 MIDI 의 박자표를 존중, ``"4/4"`` 등이면 강제.
        transpose: ``"easy"`` 면 읽기 쉬운 조(장조→C, 단조→a단조)로 전조, ``"off"``=원조.
    """
    out_dir = Path(out_dir)

    # pop2piano/piano 는 오디오를 그대로 받아 피아노 MIDI 를 만든다 -> 스템
    # 분리는 의미가 없다. Pop2Piano 는 44100Hz 입력을 쓴다.
    if engine in transcribe.DIRECT_AUDIO_ENGINES:
        stem = None
    sample_rate = (
        transcribe.POP2PIANO_SR
        if engine == transcribe.POP2PIANO
        else audio.TARGET_SR
    )

    wav = audio.to_wav(src, out_dir, sample_rate=sample_rate)

    stem_wav = None
    audio_for_transcribe = wav
    if stem:
        stem_wav = separate.separate(wav, out_dir / "stems", stem=stem)
        audio_for_transcribe = stem_wav

    midi = transcribe.to_midi(
        audio_for_transcribe, out_dir, engine=engine, composer=composer
    )
    musicxml = notation.midi_to_musicxml(
        midi, out_dir, with_chords=chords,
        time_signature=time_signature, transpose=transpose,
    )

    pdf = None
    if make_pdf:
        pdf = notation.musicxml_to_pdf(musicxml, out_dir)

    return Result(wav=wav, stem_wav=stem_wav, midi=midi, musicxml=musicxml, pdf=pdf)
