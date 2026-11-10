"""박자 추적 기반 리듬 정렬.

자동 채보가 "기계적"으로 보이는 큰 이유는 음표가 노래의 실제 박(beat)과
어긋나 있어서다. librosa 로 곡의 템포·박 위치를 찾아 음표를 그 박 그리드에
스냅하면, 마디선과 리듬이 노래 흐름대로 읽혀 훨씬 악보다워진다.

- `detect_beats`  : 오디오에서 (템포, 박 시각들) 검출 (librosa).
- `beat_aligned_score`: 멜로디 MIDI 를 박 그리드에 맞춘 music21 Score 로 변환.
"""
from __future__ import annotations

import bisect
from pathlib import Path


def detect_beats(audio_path: str | Path) -> tuple[float, list[float]]:
    """오디오에서 (템포 BPM, 박 시각 목록[초])을 검출한다.

    드럼/베이스가 있는 원본 믹스에서 가장 잘 잡히므로 그쪽을 넣는 게 좋다.
    """
    try:
        import librosa
        import numpy as np
    except ImportError as e:  # pragma: no cover - 설치 안내용
        raise RuntimeError("박자 추적에는 librosa 가 필요합니다: `pip install librosa`.") from e

    y, sr = librosa.load(str(audio_path), mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    tempo_bpm = float(np.atleast_1d(tempo)[0])
    return tempo_bpm, [float(t) for t in beat_times]


def _events_to_score(
    events: list[tuple[float, float, int]],
    beat_times: list[float],
    *,
    subdivisions: int = 4,
    time_signature: str = "4/4",
    tempo_bpm: float | None = None,
):
    """(start, end, midi_pitch) 이벤트들을 박 그리드에 맞춘 단선율 Score 로.

    각 음의 초 단위 시각을 "박 좌표"(몇 번째 박의 어디쯤)로 바꾼 뒤
    `subdivisions`(박당 분할 수) 그리드로 양자화한다. 1박 = 4분음표로 본다.
    """
    from music21 import meter, note, stream
    from music21 import tempo as m21tempo

    if len(beat_times) < 2:
        raise ValueError("박자 정보가 부족합니다(최소 2개 필요).")

    # 단선율화: 앞 음과 겹치면 더 높은 음을 우선한다.
    mono: list[list[float]] = []
    for start, end, pitch in sorted(events):
        if mono and start < mono[-1][1] - 1e-3:  # 앞 음과 겹침
            if pitch > mono[-1][2]:
                mono[-1][1] = start  # 앞 음을 여기서 끊고
                mono.append([start, end, pitch])
            # 낮은 음은 무시
        else:
            mono.append([start, end, pitch])

    def to_beat(t: float) -> float:
        i = bisect.bisect_right(beat_times, t) - 1
        i = max(0, min(i, len(beat_times) - 2))
        span = beat_times[i + 1] - beat_times[i]
        return i + (t - beat_times[i]) / span if span > 0 else float(i)

    def quantize(beat: float) -> float:
        return round(beat * subdivisions) / subdivisions

    part = stream.Part()
    part.partName = "Melody"
    if tempo_bpm:
        part.append(m21tempo.MetronomeMark(number=round(tempo_bpm)))
    part.append(meter.TimeSignature(time_signature))

    cursor = 0.0  # 현재까지 채운 위치(4분음표 단위)
    for start, end, pitch in mono:
        start_beat = quantize(to_beat(start))
        end_beat = quantize(to_beat(end))
        if end_beat <= start_beat:
            end_beat = start_beat + 1.0 / subdivisions
        if start_beat < cursor:
            start_beat = cursor  # 겹침 방지
        if start_beat > cursor + 1e-6:
            part.append(note.Rest(quarterLength=start_beat - cursor))
        n = note.Note()
        n.pitch.midi = int(pitch)
        n.quarterLength = end_beat - start_beat
        part.append(n)
        cursor = end_beat

    part.makeNotation(inPlace=True)  # 마디 구성 + 바 걸침 타이
    score = stream.Score()
    score.append(part)
    return score


def beat_aligned_score(
    midi_path: str | Path,
    beat_times: list[float],
    *,
    subdivisions: int = 4,
    tempo_bpm: float | None = None,
):
    """멜로디 MIDI 를 박 그리드에 맞춘 music21 Score 로 변환한다."""
    try:
        import pretty_midi
    except ImportError as e:  # pragma: no cover - 설치 안내용
        raise RuntimeError(
            "박자 정렬에는 pretty_midi 가 필요합니다: `pip install pretty_midi`."
        ) from e

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    events = [
        (float(n.start), float(n.end), int(n.pitch))
        for inst in pm.instruments
        for n in inst.notes
    ]
    if not events:
        raise ValueError("MIDI 에 음표가 없습니다.")
    return _events_to_score(
        events, beat_times, subdivisions=subdivisions, tempo_bpm=tempo_bpm
    )
