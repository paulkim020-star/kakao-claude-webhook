"""storybook 독립 모듈 테스트 - 작가 JSON 파싱, 화가 fallback, HTML 조립."""
import json

import pytest

from storybook import build, painter, writer


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text):
        self.content = [_Block(text)]


class _FakeClient:
    """anthropic.Anthropic 대역 - client.messages.create(...) 호출을 흉내낸다."""

    def __init__(self, text):
        self._text = text
        self.messages = self

    def create(self, **kwargs):
        return _Response(self._text)


_STORY = {
    "title": "달에 간 아기 토끼",
    "pages": [
        {"text": "아기 토끼가 하늘을 봤어요.", "image_prompt": "a white baby rabbit looking at the sky"},
        {"text": "토끼는 달로 날아갔어요.", "image_prompt": "a white baby rabbit flying to the moon"},
    ],
}


# ---------- 작가 에이전트 ----------

def test_write_story_parses_json():
    client = _FakeClient(json.dumps(_STORY, ensure_ascii=False))
    story = writer.write_story("토끼", pages=2, client=client)
    assert story["title"] == "달에 간 아기 토끼"
    assert len(story["pages"]) == 2
    assert story["pages"][0]["image_prompt"].startswith("a white baby rabbit")


def test_write_story_strips_code_fence():
    fenced = "```json\n" + json.dumps(_STORY, ensure_ascii=False) + "\n```"
    story = writer.write_story("토끼", pages=2, client=_FakeClient(fenced))
    assert len(story["pages"]) == 2


def test_write_story_rejects_empty_pages():
    with pytest.raises(ValueError):
        writer.write_story("토끼", client=_FakeClient('{"title": "x", "pages": []}'))


# ---------- 화가 에이전트 ----------

def test_paint_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert painter.paint("a cat") is None
    assert painter.image_enabled() is False


# ---------- HTML 조립 ----------

def test_build_storybook_falls_back_to_prompt(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(writer, "write_story", lambda *a, **k: dict(_STORY))
    out = build.build_storybook("토끼", pages=2, out_path=tmp_path / "book.html")
    html = out.read_text(encoding="utf-8")
    assert "달에 간 아기 토끼" in html
    assert "아기 토끼가 하늘을 봤어요." in html
    # 키가 없으니 실제 <img> 대신 프롬프트가 표시된다
    assert "a white baby rabbit looking at the sky" in html
    assert "data:image/png;base64," not in html
