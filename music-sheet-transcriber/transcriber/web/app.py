"""웹 업로드 UI: 브라우저에서 오디오를 올리면 채보해 악보를 내려받게 한다.

    uvicorn transcriber.web.app:app --host 0.0.0.0 --port 8000

주의: 실제 채보에는 ffmpeg / basic-pitch / (선택) demucs / MuseScore 가
설치되어 있어야 한다. 미설치 시 결과 화면에 어떤 도구가 필요한지 안내된다.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from ..pipeline import run
from ..separate import STEMS
from ..transcribe import ENGINES

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
OUT_ROOT = Path("web_out")

app = FastAPI(title="music-sheet-transcriber")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"stems": [*STEMS, "none"], "engines": list(ENGINES)}
    )


@app.post("/transcribe", response_class=HTMLResponse)
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
    engine: str = Form("basic-pitch"),
    stem: str = Form("vocals"),
    chords: bool = Form(False),
    pdf: bool = Form(False),
):
    job = uuid.uuid4().hex[:8]
    job_dir = OUT_ROOT / job
    job_dir.mkdir(parents=True, exist_ok=True)

    src = job_dir / Path(file.filename or "upload").name
    with src.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    ctx: dict = {"job": job, "error": None, "files": {}}
    try:
        result = run(
            src,
            out_dir=job_dir,
            stem=None if stem == "none" else stem,
            make_pdf=pdf,
            chords=chords,
            engine=engine,
        )
    except Exception as e:  # 도구 미설치/채보 실패를 화면에 그대로 안내
        ctx["error"] = str(e)
        return templates.TemplateResponse(request, "result.html", ctx)

    for label, p in (("PDF", result.pdf), ("MusicXML", result.musicxml), ("MIDI", result.midi)):
        if p:
            ctx["files"][label] = p.name
    return templates.TemplateResponse(request, "result.html", ctx)


@app.get("/download/{job}/{name}")
def download(job: str, name: str):
    # 경로 조작 방지: 파일명 성분만 사용
    path = OUT_ROOT / Path(job).name / Path(name).name
    if not path.exists():
        return HTMLResponse("파일을 찾을 수 없습니다.", status_code=404)
    return FileResponse(path)
