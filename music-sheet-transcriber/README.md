# music-sheet-transcriber

오디오 파일(mp3 / mp4)을 **악보(PDF)** 로 자동 채보(採譜)하는 파이프라인.

```
mp3/mp4 ─▶ WAV ─▶ (선택) 스템 분리 ─▶ MIDI ─▶ MusicXML ─▶ PDF
        ffmpeg        Demucs        basic-pitch   music21   MuseScore
```

## ⚠️ 먼저 알아둘 것 (현실적인 기대치)

자동 채보는 음악 종류에 따라 품질이 크게 다릅니다.

| 입력 | 품질 |
|------|------|
| 단선율(허밍/솔로 악기), 피아노 솔로 | 실용적, 약간의 후보정으로 사용 가능 |
| **풀 믹스 대중가요** | 통째로는 잡음 투성이 → **파트 분리 후 특정 스템(보컬 멜로디 등)만 채보** 권장 |

풀 믹스 곡을 "원곡 그대로의 완벽한 총보"로 만드는 것은 현재 기술로 불가능합니다.
이 도구는 **보컬 멜로디 라인** 같은 실용적 채보를 목표로 하며, 결과는 항상
사람의 후보정을 전제로 합니다.

## 설치

```bash
# 1) 시스템 의존성
#    - ffmpeg   : 오디오/영상 디코딩
#    - MuseScore: MusicXML → PDF 렌더링
# 예 (Debian/Ubuntu):
sudo apt-get install -y ffmpeg musescore3
# 예 (macOS):
brew install ffmpeg
brew install --cask musescore

# 2) 파이썬 의존성 (torch/tensorflow 를 끌어와 용량이 큽니다)
pip install -r requirements.txt
```

## 사용법

```bash
# 보컬 멜로디만 뽑아서 채보 (기본값)
python -m transcriber.cli 노래.mp3 --out out/

# 영상(mp4)에서 오디오만 추출해 채보
python -m transcriber.cli 무대영상.mp4

# 원본을 통째로 채보 (분리 없이)
python -m transcriber.cli 피아노솔로.mp3 --stem none

# MuseScore 없이 MusicXML 까지만 (직접 MuseScore 로 열어 확인)
python -m transcriber.cli 노래.mp3 --no-pdf
```

옵션:

| 옵션 | 설명 |
|------|------|
| `-o, --out` | 결과 폴더 (기본 `out/`) |
| `-s, --stem` | 채보할 파트: `vocals`(기본)·`drums`·`bass`·`other`·`none` |
| `--no-pdf` | PDF 렌더링 생략, MusicXML 까지만 생성 |

산출물은 `out/` 에 MIDI, MusicXML, PDF 로 쌓입니다.

## 구조

```
transcriber/
├── audio.py       # ffmpeg: mp3/mp4 → WAV
├── separate.py    # Demucs: 스템 분리
├── transcribe.py  # basic-pitch: 오디오 → MIDI
├── notation.py    # music21 + MuseScore: MIDI → MusicXML → PDF
├── pipeline.py    # 단계 오케스트레이션
└── cli.py         # 커맨드라인 진입점
tests/
└── test_notation.py  # MIDI → MusicXML 변환 검증
```

## 테스트

```bash
pip install -r requirements-dev.txt
pytest
```

무거운 AI 모델 없이 돌 수 있는 표기(notation) 단계를 검증합니다.

## 로드맵 / 개선 여지

- 조성·박자 자동 추정 및 가독성 좋은 조옮김
- 코드(chord) 인식으로 멜로디 + 반주 채보
- 피아노 특화 모델(MT3 / Onsets&Frames) 백엔드 선택 옵션
- 웹 UI (업로드 → 악보 미리보기/다운로드)
