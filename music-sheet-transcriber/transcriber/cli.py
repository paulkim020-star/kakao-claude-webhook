"""커맨드라인 진입점.

    python -m transcriber.cli song.mp3 --stem vocals --out out/
"""
from __future__ import annotations

import argparse
import sys

from . import pipeline
from .separate import STEMS
from .transcribe import ENGINES


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="transcriber",
        description="오디오(mp3/mp4) 를 악보(PDF/MusicXML) 로 자동 채보합니다.",
    )
    p.add_argument("input", help="입력 오디오/영상 파일 (mp3, mp4, m4a, wav ...)")
    p.add_argument("-o", "--out", default="out", help="결과 폴더 (기본: out)")
    p.add_argument(
        "-e", "--engine",
        choices=list(ENGINES),
        default="basic-pitch",
        help="채보 엔진 (기본: basic-pitch). 'pop2piano'=대중가요→피아노 커버, "
             "'piano'=솔로 피아노 고해상도 채보 (둘 다 스템 분리 생략).",
    )
    p.add_argument(
        "-s", "--stem",
        choices=[*STEMS, "none"],
        default="vocals",
        help="채보할 분리 파트 (기본: vocals). 'none' 이면 원본 통째로. (pop2piano/piano 엔진에선 무시)",
    )
    p.add_argument(
        "--composer",
        default="composer1",
        help="pop2piano 스타일 프리셋 (composer1..composer21, 기본: composer1). 그 외 엔진에선 무시.",
    )
    p.add_argument(
        "--time",
        default="auto",
        metavar="박자표",
        help="박자표. 'auto'(기본)면 MIDI 의 박자표를 존중, '3/4'·'4/4' 등이면 강제 지정.",
    )
    p.add_argument(
        "--transpose",
        default="off",
        metavar="전조",
        help="전조/키 조정. 'off'(기본)=원조, 'easy'=읽기 쉬운 조(장조→C, 단조→a단조), "
             "'+2'·'-3'=반음 올림/내림(키 조정).",
    )
    p.add_argument(
        "--no-pdf",
        action="store_true",
        help="PDF 렌더링을 건너뛰고 MusicXML 까지만 생성 (MuseScore 불필요).",
    )
    p.add_argument(
        "-c", "--chords",
        action="store_true",
        help="코드 심볼(C, Am, G7...)을 악보 위에 표기(음표엔 반영 안 함). 보컬 스템이면 반주에서 코드를 뽑는다.",
    )
    p.add_argument(
        "--no-tidy",
        action="store_true",
        help="보컬 정리(음역대 제한/짧은 잔음 제거)를 끈다. 기본은 보컬 스템일 때 자동 적용.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stem = None if args.stem == "none" else args.stem

    try:
        result = pipeline.run(
            args.input, out_dir=args.out, stem=stem,
            make_pdf=not args.no_pdf, chords=args.chords,
            engine=args.engine, composer=args.composer,
            time_signature=args.time, transpose=args.transpose,
            tidy=(False if args.no_tidy else None),
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
