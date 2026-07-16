"""오디오 → MIDI 채보. 백엔드 엔진을 선택할 수 있다.

- ``basic-pitch`` (기본): Spotify 의 가벼운 악기 무관 다성 채보 모델
  (Bittner 외, *A Lightweight Instrument-Agnostic Model for Polyphonic Note
  Transcription*, ICASSP 2022). 특정 파트/멜로디를 MIDI 로 뽑는 데 적합.
- ``pop2piano``: 대중가요 오디오를 곧바로 피아노 커버로 생성하는 T5 기반
  Transformer (Choi & Lee, *Pop2Piano: Pop Audio-based Piano Cover
  Generation*, arXiv:2211.00895). 멜로디/코드 추출 없이 풀 믹스에서 직접
  피아노 MIDI 를 만든다 → "대중가요 → 피아노 악보" 케이스에 정통 경로.
- ``piano``: 피아노 연주 녹음을 고해상도로 채보하는 Onsets&Frames 계열 모델
  (Kong 외, *High-resolution Piano Transcription with Pedals by Regressing
  Onset and Offset Times*, 2021). **솔로 피아노 오디오**에 적합(풀 믹스가 아님).
"""
from __future__ import annotations

from pathlib import Path

BASIC_PITCH = "basic-pitch"
POP2PIANO = "pop2piano"
PIANO = "piano"
ENGINES = (BASIC_PITCH, POP2PIANO, PIANO)

# 오디오를 그대로 받아 피아노 MIDI 를 만드는 엔진(스템 분리 불필요).
DIRECT_AUDIO_ENGINES = (POP2PIANO, PIANO)

# Pop2Piano 는 44100Hz 오디오를 입력으로 쓴다.
POP2PIANO_SR = 44100


def to_midi(
    audio_path: str | Path,
    dst_dir: str | Path,
    *,
    engine: str = BASIC_PITCH,
    composer: str = "composer1",
) -> Path:
    """`audio_path` 를 채보해 MIDI 파일 경로를 돌려준다.

    Args:
        engine: ``basic-pitch`` 또는 ``pop2piano``.
        composer: pop2piano 스타일 프리셋(``composer1``..``composer21``). 그 외
            엔진에서는 무시된다.
    """
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    if engine == BASIC_PITCH:
        return _basic_pitch(Path(audio_path), dst_dir)
    if engine == POP2PIANO:
        return _pop2piano(Path(audio_path), dst_dir, composer=composer)
    if engine == PIANO:
        return _piano(Path(audio_path), dst_dir)
    raise ValueError(f"알 수 없는 엔진: {engine!r} (가능: {ENGINES})")


def _basic_pitch(audio_path: Path, dst_dir: Path) -> Path:
    try:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import predict
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


def _pop2piano(audio_path: Path, dst_dir: Path, *, composer: str = "composer1") -> Path:
    try:
        import librosa
        from transformers import (
            Pop2PianoForConditionalGeneration,
            Pop2PianoProcessor,
        )
    except ImportError as e:  # pragma: no cover - 설치 안내용
        raise RuntimeError(
            "Pop2Piano 엔진에는 transformers · librosa · torch 가 필요합니다: "
            "`pip install -r requirements-pop2piano.txt`."
        ) from e

    audio, sr = librosa.load(str(audio_path), sr=POP2PIANO_SR)
    model = Pop2PianoForConditionalGeneration.from_pretrained("sweetcocoa/pop2piano")
    processor = Pop2PianoProcessor.from_pretrained("sweetcocoa/pop2piano")

    inputs = processor(audio=audio, sampling_rate=sr, return_tensors="pt")
    model_output = model.generate(
        input_features=inputs["input_features"], composer=composer
    )
    midi_obj = processor.batch_decode(
        token_ids=model_output, feature_extractor_output=inputs
    )["pretty_midi_objects"][0]

    dst = dst_dir / f"{audio_path.stem}.mid"
    midi_obj.write(str(dst))
    return dst


def _piano(audio_path: Path, dst_dir: Path) -> Path:
    try:
        from piano_transcription_inference import (
            PianoTranscription,
            load_audio,
            sample_rate,
        )
    except ImportError as e:  # pragma: no cover - 설치 안내용
        raise RuntimeError(
            "피아노 엔진에는 piano_transcription_inference 가 필요합니다: "
            "`pip install -r requirements-piano.txt`."
        ) from e

    audio, _ = load_audio(str(audio_path), sr=sample_rate, mono=True)
    dst = dst_dir / f"{audio_path.stem}.mid"
    PianoTranscription(device="cpu").transcribe(audio, str(dst))
    return dst
