"""화가 에이전트: 삽화 프롬프트 -> 이미지 API. 키가 없으면 플레이스홀더로 폴백."""

import base64
import logging
import os
from xml.sax.saxutils import escape

import httpx

logger = logging.getLogger("storybook.painter")

IMAGE_API_PROVIDER = os.environ.get("IMAGE_API_PROVIDER", "openai")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
IMAGE_SIZE = os.environ.get("STORYBOOK_IMAGE_SIZE", "1024x1024")


def _placeholder(scene: str) -> str:
    """이미지 API가 없거나 실패했을 때 쓰는 SVG 플레이스홀더 (data URL)."""
    label = escape(scene[:60])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512">'
        '<rect width="512" height="512" fill="#f6e0c8"/>'
        '<text x="256" y="240" font-size="26" text-anchor="middle"'
        ' font-family="sans-serif" fill="#8a6d4b">🖼️ 이미지 준비중</text>'
        f'<text x="256" y="290" font-size="14" text-anchor="middle"'
        f' font-family="sans-serif" fill="#a58b6a">{label}</text>'
        "</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def paint(scene: str) -> str:
    """삽화 프롬프트로 이미지를 생성해 data URL로 반환. 실패 시 플레이스홀더."""
    if IMAGE_API_PROVIDER == "openai" and OPENAI_API_KEY:
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": "gpt-image-1",
                        "prompt": scene,
                        "size": IMAGE_SIZE,
                        "n": 1,
                    },
                )
                resp.raise_for_status()
                b64 = resp.json()["data"][0]["b64_json"]
                return f"data:image/png;base64,{b64}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("이미지 생성 실패, 플레이스홀더로 대체: %s", exc)

    return _placeholder(scene)
