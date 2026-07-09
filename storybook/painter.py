"""화가 에이전트 - 장면 묘사(image_prompt)를 실제 이미지로 그린다.

OpenAI 이미지 생성 API(gpt-image-1)를 사용한다. OPENAI_API_KEY가 없으면
그림 없이 None을 돌려주고, 호출부(build.py)가 프롬프트 텍스트로 대체한다.
키만 넣으면 바로 실제 그림이 나오는 pluggable 구조.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

IMAGE_MODEL = os.environ.get("STORYBOOK_IMAGE_MODEL", "gpt-image-1")
IMAGE_SIZE = os.environ.get("STORYBOOK_IMAGE_SIZE", "1024x1024")
_ENDPOINT = "https://api.openai.com/v1/images/generations"


def image_enabled() -> bool:
    """이미지 생성 API 키가 설정돼 실제 그림을 그릴 수 있으면 True."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def paint(prompt: str) -> str | None:
    """이미지 프롬프트로 그림을 생성해 base64(PNG) 문자열을 반환. 키 없으면 None."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return None
    try:
        response = httpx.post(
            _ENDPOINT,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": IMAGE_MODEL, "prompt": prompt, "size": IMAGE_SIZE, "n": 1},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["data"][0]["b64_json"]
    except Exception:
        logger.exception("이미지 생성 실패 - 프롬프트 텍스트로 대체합니다.")
        return None
