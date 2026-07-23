# Windows 설치 · 실행 가이드 (D:드라이브 정리 포함)

AI 작업(모델·패키지 캐시가 수 GB)을 **D:드라이브에 모아** 관리하는 것을 전제로
정리한 가이드입니다. C: 용량을 아끼려면 폴더뿐 아니라 "숨은 캐시"까지 D:로
옮기는 게 핵심입니다.

> 이 프로젝트도 `pop2piano`/`piano` 엔진이 모델을 수백 MB씩 내려받습니다.
> 아래처럼 캐시 경로를 D:로 지정하지 않으면 기본값(C:\Users\...\.cache)에 쌓입니다.

## 1) D:에 AI 작업 공간 만들기

```
D:\AI\
├── projects\        # 프로젝트 코드 (git clone 위치)
│   └── music-sheet-transcriber\
├── models\          # HuggingFace / torch 모델 캐시
└── pip-cache\       # pip 다운로드 캐시
```

## 2) 큰 캐시들을 D:로 리다이렉트 (제일 중요)

PowerShell에서 **한 번만** 설정하면 계정 전체에 적용됩니다.

```powershell
setx HF_HOME "D:\AI\models\huggingface"
setx HUGGINGFACE_HUB_CACHE "D:\AI\models\huggingface"
setx TORCH_HOME "D:\AI\models\torch"
setx PIP_CACHE_DIR "D:\AI\pip-cache"
```

> `setx` 이후에는 **새 터미널을 열어야** 적용됩니다. 이러면 앞으로 모든 AI
> 프로젝트의 모델·패키지 다운로드가 D:로 갑니다.

## 3) 코드 받기

```powershell
D:
cd \AI\projects
git clone https://github.com/paulkim020-star/kakao-claude-webhook.git
cd kakao-claude-webhook
git checkout claude/project-approach-hrb91d
cd music-sheet-transcriber
```

## 4) 시스템 도구 설치 (ffmpeg, MuseScore)

```powershell
winget install Gyan.FFmpeg
winget install MuseScore.MuseScore
```

> MuseScore 없이도 됩니다 — 그 경우 PDF만 못 만들고 웹 미리보기(SVG)·MusicXML·
> MIDI는 정상 동작합니다.

## 5) 가상환경 + 패키지 설치

프로젝트가 D:에 있으므로 그 안에 만든 `.venv`도 자연히 D:에 생깁니다.

```powershell
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt            # 기본 (basic-pitch 엔진)
pip install -r requirements-pop2piano.txt  # (선택) 대중가요 → 피아노 커버
pip install -r requirements-piano.txt      # (선택) 솔로 피아노 고해상도
```

> `requirements.txt`가 torch/tensorflow를 끌어와 용량이 큽니다(수 GB). 설치에
> 시간이 걸립니다.

## 6) 실행

### 웹 UI

```powershell
uvicorn transcriber.web.app:app --port 8000
```

→ 브라우저에서 **http://localhost:8000** 접속 → 파일 업로드 → 엔진/전조/코드/PDF
선택 → 악보 미리보기 + 다운로드.

### 커맨드라인

```powershell
# 대중가요를 피아노 악보로
python -m transcriber.cli 노래.mp3 --engine pop2piano

# 보컬 멜로디만 뽑고 키 2개 올려서
python -m transcriber.cli 노래.mp3 --stem vocals --transpose +2
```

## 정리

이렇게 해두면 **코드 + 모델 + 패키지 캐시 + 가상환경**이 전부 D:에 모여,
C: 용량 걱정 없이 AI 작업을 관리할 수 있습니다. 새 PC에서도 2)의 환경변수만
다시 설정하면 동일하게 재현됩니다.
