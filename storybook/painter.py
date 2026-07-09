"""화가 에이전트 - 장면 묘사(scene)를 이미지로 바꾼다.

이미지 생성 API 키를 자동으로 골라 쓴다:
  1. GOOGLE_API_KEY  -> Google Imagen (Gemini API)
  2. OPENAI_API_KEY  -> OpenAI gpt-image-1
둘 다 없거나 호출에 실패하면 회색 SVG 플레이스홀더를 돌려준다.
결과는 항상 HTML <img src>에 바로 넣을 수 있는 data URI 문자열.
"""
from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger("storybook.painter")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

_GOOGLE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "imagen-3.0-generate-002:predict"
)
_OPENAI_URL = "https://api.openai.com/v1/images/generations"


def active_provider() -> str:
    """지금 쓸 이미지 제공자. 키가 없으면 'placeholder'."""
    if GOOGLE_API_KEY:
        return "google"
    if OPENAI_API_KEY:
        return "openai"
    return "placeholder"


def paint(scene: str) -> str:
    """장면 묘사 -> 이미지 data URI. 실패하면 플레이스홀더로 대체."""
    provider = active_provider()
    try:
        if provider == "google":
            return _google(scene)
        if provider == "openai":
            return _openai(scene)
    except Exception:
        logger.exception("화가 에이전트(%s) 호출 실패 - 플레이스홀더로 대체", provider)
    return _placeholder(scene)


def _data_uri(b64: str) -> str:
    return f"data:image/png;base64,{b64}"


def _google(scene: str) -> str:
    resp = httpx.post(
        _GOOGLE_URL,
        params={"key": GOOGLE_API_KEY},
        json={"instances": [{"prompt": scene}], "parameters": {"sampleCount": 1}},
        timeout=60,
    )
    resp.raise_for_status()
    return _data_uri(resp.json()["predictions"][0]["bytesBase64Encoded"])


def _openai(scene: str) -> str:
    resp = httpx.post(
        _OPENAI_URL,
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={"model": "gpt-image-1", "prompt": scene, "n": 1, "size": "1024x1024"},
        timeout=60,
    )
    resp.raise_for_status()
    return _data_uri(resp.json()["data"][0]["b64_json"])


def _placeholder(scene: str) -> str:
    """장면 묘사 텍스트를 담은 회색 SVG 플레이스홀더 data URI."""
    label = (scene[:48] + "…") if len(scene) > 48 else scene
    label = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='512' height='512'>"
        "<rect width='512' height='512' fill='#e6e0d4'/>"
        "<text x='256' y='240' font-family='sans-serif' font-size='24' "
        "fill='#8a7f6c' text-anchor='middle'>그림 준비 중</text>"
        "<text x='256' y='280' font-family='sans-serif' font-size='13' "
        f"fill='#a99f8b' text-anchor='middle'>{label}</text>"
        "</svg>"
    )
    return "data:image/svg+xml;utf8," + quote(svg)
