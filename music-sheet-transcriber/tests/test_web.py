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


def test_transcribe_success_shows_svg_preview(tmp_path, monkeypatch):
    """채보 성공 시(파이프라인 stub) 악보 SVG 미리보기와 다운로드 링크가 뜬다."""
    pytest.importorskip("music21")
    pytest.importorskip("verovio")

    from music21 import stream, note

    from transcriber.pipeline import Result
    from transcriber.web import app as webapp

    # 실제 채보 대신 합성 MusicXML 을 가리키는 Result 를 돌려주도록 stub
    xml = tmp_path / "song.musicxml"
    s = stream.Stream()
    for n in ["C4", "E4", "G4", "C5"]:
        s.append(note.Note(n, quarterLength=1))
    s.write("musicxml", fp=str(xml))
    midi = tmp_path / "song.mid"
    midi.write_bytes(b"")

    def fake_run(src, **kwargs):
        return Result(wav=src, stem_wav=None, midi=midi, musicxml=xml, pdf=None)

    monkeypatch.setattr(webapp, "run", fake_run)

    r = client.post(
        "/transcribe",
        data={"engine": "pop2piano", "stem": "none"},
        files={"file": ("song.mp3", b"x", "audio/mpeg")},
    )
    assert r.status_code == 200
    assert "<svg" in r.text            # 인라인 악보 미리보기
    assert "MusicXML 다운로드" in r.text  # 다운로드 링크
