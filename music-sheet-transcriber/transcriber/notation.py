"""MIDI → 악보(MusicXML, PDF).

music21 로 MIDI 를 읽어 박자/음정을 정리한 뒤 MusicXML 로 저장하고,
MuseScore(또는 LilyPond) CLI 로 PDF 를 렌더링한다. 자동 채보 결과는
잡음이 많으므로 여기서 양자화(quantize)로 최소한의 정리를 한다.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# PDF 렌더러 후보 (있는 것을 자동으로 사용)
_MUSESCORE_BINARIES = ("mscore", "musescore", "musescore4", "mscore4", "musescore3")


def _find_musescore() -> str | None:
    for name in _MUSESCORE_BINARIES:
        found = shutil.which(name)
        if found:
            return found
    return None


def midi_to_musicxml(midi_path: str | Path, dst_dir: str | Path) -> Path:
    """MIDI 를 정리해 MusicXML 로 저장하고 경로를 돌려준다."""
    midi_path = Path(midi_path)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    try:
        from music21 import converter
    except ImportError as e:  # pragma: no cover - 설치 안내용
        raise RuntimeError("music21 이 설치되어 있지 않습니다: `pip install music21`.") from e

    score = converter.parse(str(midi_path))
    # 자동 채보 노트 길이는 어긋나기 마련 -> 16분음표 그리드로 양자화
    score.quantize(inPlace=True)

    dst = dst_dir / f"{midi_path.stem}.musicxml"
    score.write("musicxml", fp=str(dst))
    return dst


def musicxml_to_pdf(musicxml_path: str | Path, dst_dir: str | Path) -> Path:
    """MusicXML 을 PDF 로 렌더링한다. MuseScore CLI 필요."""
    musicxml_path = Path(musicxml_path)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    mscore = _find_musescore()
    if not mscore:
        raise RuntimeError(
            "MuseScore 를 찾을 수 없어 PDF 를 만들 수 없습니다. MusicXML 은 생성되었으니 "
            "MuseScore 로 열어 PDF 로 내보내거나, MuseScore 설치 후 다시 실행하세요."
        )

    dst = dst_dir / f"{musicxml_path.stem}.pdf"
    # MuseScore 는 헤드리스 렌더링 시 가상 디스플레이가 필요할 수 있음(xvfb-run).
    cmd = [mscore, "-o", str(dst), str(musicxml_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"MuseScore PDF 렌더링 실패:\n{proc.stderr.strip()}")
    return dst
