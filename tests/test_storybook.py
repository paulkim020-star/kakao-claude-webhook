"""
동화책 생성 모듈 검증 (네트워크 없이 결정적으로).

실행: pip install -r requirements-dev.txt && pytest
"""

import pytest
from fastapi.testclient import TestClient

import storybook.db as db
from storybook import painter, writer

FIXED_STORY = {
    "title": "용감한 토끼의 모험",
    "pages": [
        {"text": "토끼가 숲으로 떠났어요.", "scene": "a brave rabbit in a forest"},
        {"text": "토끼는 친구를 만났어요.", "scene": "a rabbit meeting a friend"},
    ],
}
FIXED_IMAGE = "data:image/png;base64,AAAA"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "storybook.db"))
    # 작가/화가를 고정값으로 대체 → 네트워크 호출 없음
    monkeypatch.setattr(writer, "write_story", lambda topic, pages=6: FIXED_STORY)
    monkeypatch.setattr(painter, "paint", lambda scene: FIXED_IMAGE)
    from main import app

    with TestClient(app) as c:
        yield c


def test_home_shows_form(client):
    res = client.get("/storybook")
    assert res.status_code == 200
    assert 'action="/storybook/create"' in res.text
    assert 'name="topic"' in res.text


def test_create_and_view_book(client):
    res = client.post(
        "/storybook/create",
        data={"topic": "용감한 토끼", "pages": 2},
        follow_redirects=False,
    )
    assert res.status_code == 303
    location = res.headers["location"]
    assert location.startswith("/storybook/book/")

    res = client.get(location)
    assert res.status_code == 200
    assert FIXED_STORY["title"] in res.text
    assert "토끼가 숲으로 떠났어요." in res.text
    assert FIXED_IMAGE in res.text


def test_painter_placeholder_without_key(monkeypatch):
    monkeypatch.setattr(painter, "OPENAI_API_KEY", "")
    result = painter.paint("a cat")
    assert result.startswith("data:image/svg+xml;base64,")


def test_writer_requires_api_key(monkeypatch):
    monkeypatch.setattr(writer, "_client", None)
    with pytest.raises(RuntimeError):
        writer.write_story("아무 주제")
