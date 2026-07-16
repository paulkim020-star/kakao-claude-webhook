"""오디오 → MIDI 채보: Spotify 의 basic-pitch 사용.

basic-pitch 는 다성(polyphonic) 채보를 지원하는 가벼운 신경망 모델이다.
음원의 음정/온셋을 추정해 MIDI 로 뽑아준다. 완벽하진 않으므로 이후 표기
단계에서 양자화/정리를 거친다.
"""
from __future__ import annotations

from pathlib import Path


def to_midi(audio_path: str | Path, dst_dir: str | Path) -> Path:
    """`audio_path` 를 채보해 MIDI 파일 경로를 돌려준다."""
    audio_path = Path(audio_path)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    try:
        from basic_pitch.inference import predict
        from basic_pitch import ICASSP_2022_MODEL_PATH
    except ImportError as e:  # pragma: no cover - 설치 안내용
        raise RuntimeError(
            "basic-pitch 가 설치되어 있지 않습니다: `pip install basic-pitch`."
        ) from e

    _model_output, midi_data, _note_events = predict(
        str(audio_path), ICASSP_2022_MODEL_PATH
    )

    dst = dst_dir / f"{audio_path.stem}.mid"
    midi_data.write(str(dst))
    return dst
