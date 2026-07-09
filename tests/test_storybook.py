import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_painter_placeholder_without_keys(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from storybook import painter

    importlib.reload(painter)
    assert painter.active_provider() == "placeholder"
    uri = painter.paint("a happy rabbit in the forest")
    assert uri.startswith("data:image/svg+xml")


def test_writer_fallback_without_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from storybook import writer

    importlib.reload(writer)
    story = writer.write_story("토끼", pages=3)
    assert story["fallback"] is True
    assert len(story["pages"]) == 3
    assert all("text" in p and "scene" in p for p in story["pages"])


def test_writer_parse_codefence():
    from storybook import writer

    data = writer._parse('```json\n{"title":"x","pages":[]}\n```')
    assert data["title"] == "x"


def test_web_create_flow_without_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from storybook import painter, web, writer

    importlib.reload(writer)
    importlib.reload(painter)
    importlib.reload(web)
    app = FastAPI()
    app.include_router(web.router)
    c = TestClient(app)
    assert c.get("/storybook").status_code == 200
    res = c.post("/storybook/create", data={"topic": "토끼", "pages": 3})
    assert res.status_code == 200
    assert "토끼" in res.text
    assert res.text.count("data:image/svg+xml") == 3
