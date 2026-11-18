"""PDF 서재 FastAPI 앱 (웹훅 서버와 별개로 실행: python -m ebook)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ebook.web import router

app = FastAPI(title="PDF 서재")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
app.include_router(router)
