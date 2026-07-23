"""오디오 입력 처리: mp3/mp4 등 → 채보용 WAV 로 변환.

basic-pitch 는 22050Hz 모노 WAV 를 가장 잘 처리한다. ffmpeg 에 의존하므로
시스템에 ffmpeg 가 설치되어 있어야 한다.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# basic-pitch 가 학습된 샘플레이트. 굳이 바꿀 이유 없음.
TARGET_SR = 22050


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def to_wav(src: str | Path, dst_dir: str | Path, sample_rate: int = TARGET_SR) -> Path:
    """`src`(mp3/mp4/m4a/...) 를 모노 WAV 로 변환해 경로를 돌려준다.

    mp4 같은 영상 컨테이너면 오디오 트랙만 뽑는다.
    """
    src = Path(src)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {src}")
    if not ffmpeg_available():
        raise RuntimeError(
            "ffmpeg 를 찾을 수 없습니다. 설치 후 다시 실행하세요 "
            "(예: `apt-get install ffmpeg` 또는 `brew install ffmpeg`)."
        )

    dst = dst_dir / f"{src.stem}.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vn",              # 영상 트랙 무시 (mp4 대응)
        "-ac", "1",         # 모노
        "-ar", str(sample_rate),
        str(dst),
    ]
    # 한국어 Windows(cp949)에서도 ffmpeg 의 UTF-8 출력을 깨짐 없이 읽도록 지정
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 변환 실패:\n{(proc.stderr or '').strip()}")
    return dst
