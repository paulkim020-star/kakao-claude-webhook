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
) -> Result:
    """`src` 오디오를 채보한다.

    Args:
        src: 입력 오디오/영상 (mp3, mp4, m4a, wav ...).
        out_dir: 중간 산출물과 결과가 쌓이는 폴더.
        stem: 분리해서 채보할 파트("vocals" 등). None 이면 원본 통째로 채보.
        make_pdf: True 면 MuseScore 로 PDF 까지 렌더링(없으면 MusicXML 까지만).
    """
    out_dir = Path(out_dir)

    wav = audio.to_wav(src, out_dir)

    stem_wav = None
    audio_for_transcribe = wav
    if stem:
        stem_wav = separate.separate(wav, out_dir / "stems", stem=stem)
        audio_for_transcribe = stem_wav

    midi = transcribe.to_midi(audio_for_transcribe, out_dir)
    musicxml = notation.midi_to_musicxml(midi, out_dir)

    pdf = None
    if make_pdf:
        pdf = notation.musicxml_to_pdf(musicxml, out_dir)

    return Result(wav=wav, stem_wav=stem_wav, midi=midi, musicxml=musicxml, pdf=pdf)
