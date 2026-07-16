"""MIDI → 악보(MusicXML, PDF).

music21 로 MIDI 를 읽어 가독성을 높인 뒤(양자화 + 조성/박자 삽입) MusicXML 로
저장하고, MuseScore(또는 LilyPond) CLI 로 PDF 를 렌더링한다. 자동 채보 결과는
잡음이 많으므로 이 단계의 정리가 최종 악보 품질을 크게 좌우한다.
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


def midi_to_score(
    midi_path: str | Path,
    *,
    detect_key: bool = True,
    time_signature: str | None = "4/4",
):
    """MIDI 를 읽어 가독성을 높인 music21 Score 를 돌려준다.

    - 양자화: 자동 채보로 어긋난 음길이를 16분음표 그리드에 맞춘다.
    - 박자표: `time_signature` 를 첫 마디에 넣는다(None 이면 생략).
    - 조성: `detect_key` 면 조성을 추정해 조표를 넣는다(안 되면 조용히 건너뜀).
    """
    try:
        from music21 import converter, meter
    except ImportError as e:  # pragma: no cover - 설치 안내용
        raise RuntimeError("music21 이 설치되어 있지 않습니다: `pip install music21`.") from e

    score = converter.parse(str(midi_path))
    score.quantize(inPlace=True)

    part = score.parts[0] if score.parts else score
    if time_signature:
        part.insert(0, meter.TimeSignature(time_signature))
    if detect_key:
        try:
            part.insert(0, score.analyze("key"))
        except Exception:
            pass  # 조성 추정 실패는 치명적이지 않음

    return score


def write_musicxml(score, dst_dir: str | Path, stem_name: str) -> Path:
    """music21 Score 를 MusicXML 파일로 저장한다."""
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{stem_name}.musicxml"
    score.write("musicxml", fp=str(dst))
    return dst


def midi_to_musicxml(
    midi_path: str | Path,
    dst_dir: str | Path,
    *,
    detect_key: bool = True,
    time_signature: str | None = "4/4",
    with_chords: bool = False,
) -> Path:
    """MIDI 를 정리(+선택적 코드 심볼)해 MusicXML 로 저장하고 경로를 돌려준다."""
    midi_path = Path(midi_path)
    score = midi_to_score(
        midi_path, detect_key=detect_key, time_signature=time_signature
    )
    if with_chords:
        from . import chords

        chords.annotate(score)
    return write_musicxml(score, dst_dir, midi_path.stem)


def musicxml_to_svg(musicxml_path: str | Path) -> list[str]:
    """MusicXML 을 페이지별 SVG 마크업 리스트로 렌더링한다(verovio).

    MuseScore 없이 순수 파이썬으로 동작해 웹 인라인 미리보기에 쓴다.
    """
    try:
        import verovio
    except ImportError as e:  # pragma: no cover - 설치 안내용
        raise RuntimeError("verovio 가 설치되어 있지 않습니다: `pip install verovio`.") from e

    # 폰트/리소스 경로를 명시적으로 지정한다. 자동 탐지는 실행 컨텍스트
    # (예: 웹 워커 스레드)에 따라 실패해 폰트 로딩 에러가 날 수 있다.
    import os

    toolkit = verovio.toolkit(False)
    toolkit.setResourcePath(os.path.join(os.path.dirname(verovio.__file__), "data"))
    toolkit.setOptions({"adjustPageHeight": True, "scale": 40, "pageWidth": 2100})
    if not toolkit.loadFile(str(musicxml_path)):
        raise RuntimeError("verovio 가 MusicXML 을 불러오지 못했습니다.")
    return [toolkit.renderToSVG(i) for i in range(1, toolkit.getPageCount() + 1)]


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
