"""웹 UI 테스트: 폼이 뜨고 업로드 흐름이 배선돼 있는지 검증.

무거운 채보 파이프라인(ffmpeg 등) 없이도 라우팅/에러 처리를 확인한다.
"""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")  # python-multipart
from starlette.testclient import TestClient

from transcriber.web.app import app

client = TestClient(app)


def test_index_serves_upload_form():
    r = client.get("/")
    assert r.status_code == 200
    assert "채보" in r.text
    assert 'type="file"' in r.text


def test_transcribe_reports_error_without_tools():
    # ffmpeg 등이 없는 환경에서도 500 이 아니라 안내 화면(200)이 떠야 함
    r = client.post(
        "/transcribe",
        data={"stem": "none", "pdf": "false"},
        files={"file": ("test.mp3", b"not real audio", "audio/mpeg")},
    )
    assert r.status_code == 200
    assert "채보 결과" in r.text
    # ffmpeg 미설치 안내 문구가 그대로 노출되는지
    assert "ffmpeg" in r.text.lower()


def test_download_missing_returns_404():
    r = client.get("/download/nojob/nofile.pdf")
    assert r.status_code == 404
