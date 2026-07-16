"""스템 분리: Demucs 로 풀 믹스를 vocals/drums/bass/other 로 나눈다.

풀 믹스 대중가요를 통째로 채보하면 결과가 엉망이 된다. 원하는 파트(보통
보컬 멜로디)만 뽑아서 채보하면 훨씬 쓸 만하다. Demucs 는 무겁고(torch 필요)
GPU 가 없으면 곡당 수십 초~수 분 걸린다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

STEMS = ("vocals", "drums", "bass", "other")


def separate(src_wav: str | Path, dst_dir: str | Path, stem: str = "vocals") -> Path:
    """`src_wav` 에서 `stem` 파트만 분리해 WAV 경로를 돌려준다.

    Demucs 를 서브프로세스로 호출한다(패키지 API 가 버전마다 달라 CLI 가 안정적).
    """
    if stem not in STEMS:
        raise ValueError(f"stem 은 {STEMS} 중 하나여야 합니다: {stem!r}")

    src_wav = Path(src_wav)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    # demucs --two-stems 로 대상 파트 vs 나머지 로만 분리 (빠르고 충분)
    cmd = [
        sys.executable, "-m", "demucs",
        "--two-stems", stem,
        "-o", str(dst_dir),
        str(src_wav),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Demucs 실행 실패 (설치 확인: `pip install demucs`):\n"
            + proc.stderr.strip()
        )

    # demucs 출력 구조: <dst>/<model>/<track>/<stem>.wav
    matches = list(dst_dir.rglob(f"{stem}.wav"))
    if not matches:
        raise RuntimeError("Demucs 출력에서 분리된 스템을 찾지 못했습니다.")
    return matches[0]
