"""커맨드라인 진입점.

    python -m transcriber.cli song.mp3 --stem vocals --out out/
"""
from __future__ import annotations

import argparse
import sys

from . import pipeline
from .separate import STEMS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="transcriber",
        description="오디오(mp3/mp4) 를 악보(PDF/MusicXML) 로 자동 채보합니다.",
    )
    p.add_argument("input", help="입력 오디오/영상 파일 (mp3, mp4, m4a, wav ...)")
    p.add_argument("-o", "--out", default="out", help="결과 폴더 (기본: out)")
    p.add_argument(
        "-s", "--stem",
        choices=[*STEMS, "none"],
        default="vocals",
        help="채보할 분리 파트 (기본: vocals). 'none' 이면 원본 통째로 채보.",
    )
    p.add_argument(
        "--no-pdf",
        action="store_true",
        help="PDF 렌더링을 건너뛰고 MusicXML 까지만 생성 (MuseScore 불필요).",
    )
    p.add_argument(
        "-c", "--chords",
        action="store_true",
        help="마디별 코드 심볼(C, Am, G7...)을 추정해 악보에 표기. 반주가 포함된 파트에 유효.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stem = None if args.stem == "none" else args.stem

    try:
        result = pipeline.run(
            args.input, out_dir=args.out, stem=stem,
            make_pdf=not args.no_pdf, chords=args.chords,
        )
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        print(f"[에러] {e}", file=sys.stderr)
        return 1

    print("채보 완료:")
    print(f"  MIDI     : {result.midi}")
    print(f"  MusicXML : {result.musicxml}")
    if result.pdf:
        print(f"  PDF      : {result.pdf}")
    else:
        print("  PDF      : (건너뜀 - MusicXML 을 MuseScore 로 열어 확인하세요)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
