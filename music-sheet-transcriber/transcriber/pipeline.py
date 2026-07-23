"""전체 채보 파이프라인 오케스트레이션.

    mp3/mp4 ─▶ WAV ─▶ (선택) 스템 분리 ─▶ MIDI ─▶ MusicXML ─▶ PDF
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import audio, beats, notation, separate, transcribe


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
    tidy: bool | None = None,
    merge_repeats: bool = False,
    beat_align: bool = False,
) -> Result:
    """`src` 오디오를 채보한다.

    Args:
        src: 입력 오디오/영상 (mp3, mp4, m4a, wav ...).
        out_dir: 중간 산출물과 결과가 쌓이는 폴더.
        stem: 분리해서 채보할 파트("vocals" 등). None 이면 원본 통째로 채보.
        make_pdf: True 면 MuseScore 로 PDF 까지 렌더링(없으면 MusicXML 까지만).
        chords: True 면 코드 심볼을 악보 위에 표기. 보컬 스템이면 분리된 반주
            (no_vocals)의 화음에서 코드를 뽑아 멜로디 위에 얹는다.
        engine: 채보 백엔드. ``basic-pitch``(파트/멜로디용) 또는
            ``pop2piano``(대중가요 → 피아노 커버).
        composer: pop2piano 스타일 프리셋. 그 외 엔진에서는 무시.
        time_signature: ``"auto"`` 면 MIDI 의 박자표를 존중, ``"4/4"`` 등이면 강제.
        transpose: ``"easy"`` 면 읽기 쉬운 조(장조→C, 단조→a단조)로 전조, ``"off"``=원조.
        tidy: basic-pitch 보컬 정리(음역대 제한/잔음 제거). None 이면 보컬 스템일
            때 자동 적용.
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

    # 보컬 멜로디를 basic-pitch 로 딸 땐 기본적으로 정리(tidy)한다.
    if tidy is None:
        tidy = stem == "vocals" and engine == transcribe.BASIC_PITCH

    wav = audio.to_wav(src, out_dir, sample_rate=sample_rate)

    stem_wav = None
    audio_for_transcribe = wav
    if stem:
        stem_wav = separate.separate(wav, out_dir / "stems", stem=stem)
        audio_for_transcribe = stem_wav

    midi = transcribe.to_midi(
        audio_for_transcribe, out_dir, engine=engine, composer=composer, tidy=tidy
    )

    # 코드: 멜로디 스템을 뽑았으면 분리된 반주(no_<stem>)에서 코드를 추출한다.
    chord_source_midi = None
    if chords and stem_wav is not None:
        accompaniment = stem_wav.parent / f"no_{stem}.wav"
        if accompaniment.exists():
            chord_source_midi = transcribe.to_midi(
                accompaniment, out_dir, engine=transcribe.BASIC_PITCH
            )

    # 보컬 멜로디 스템은 단선율(최고음 한 줄)로 축약해 멜로디 악보로 만든다.
    melody_only = stem == "vocals"

    # 박자 정렬: 원본 믹스(드럼/베이스 있음)에서 박을 검출해 멜로디를 그 그리드에
    # 맞춘다. 실패해도 일반 경로로 진행.
    beat_times = None
    if beat_align:
        try:
            _tempo, beat_times = beats.detect_beats(wav)
        except Exception:
            beat_times = None

    musicxml = notation.midi_to_musicxml(
        midi, out_dir, with_chords=chords, chord_source_midi=chord_source_midi,
        time_signature=time_signature, transpose=transpose,
        merge_repeats=merge_repeats, melody_only=melody_only, beat_times=beat_times,
    )

    pdf = None
    if make_pdf:
        pdf = notation.musicxml_to_pdf(musicxml, out_dir)

    return Result(wav=wav, stem_wav=stem_wav, midi=midi, musicxml=musicxml, pdf=pdf)
