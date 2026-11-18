"""로컬 계정: scrypt 비밀번호 해시 + HMAC 서명 쿠키 (외부 서비스 불필요)."""

import hashlib
import hmac
import secrets
import time

from ebook.db import data_dir

SESSION_COOKIE = "ebook_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30일


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def _secret() -> bytes:
    path = data_dir() / "secret.key"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return path.read_text().encode()


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_session(user_id: int) -> str:
    payload = f"{user_id}.{int(time.time()) + SESSION_MAX_AGE}"
    return f"{payload}.{_sign(payload)}"


def read_session(cookie: str | None) -> int | None:
    """유효한 쿠키면 user_id, 아니면 None."""
    if not cookie:
        return None
    try:
        user_id, expires, sig = cookie.split(".")
        if not hmac.compare_digest(sig, _sign(f"{user_id}.{expires}")):
            return None
        if int(expires) < time.time():
            return None
        return int(user_id)
    except ValueError:
        return None
