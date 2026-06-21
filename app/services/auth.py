from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass

from fastapi import Request

from app.config import Settings

SESSION_COOKIE_NAME = "zhengfudata_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12


@dataclass(frozen=True)
class CurrentUser:
    username: str


def password_hash(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return base64.urlsafe_b64encode(digest).decode()


def verify_admin_password(username: str, password: str, settings: Settings) -> bool:
    expected_hash = password_hash(settings.admin_password, settings.app_secret_key)
    actual_hash = password_hash(password, settings.app_secret_key)
    return username == settings.admin_username and hmac.compare_digest(actual_hash, expected_hash)


def create_session_token(username: str, settings: Settings) -> str:
    expires_at = int(time.time()) + SESSION_MAX_AGE_SECONDS
    payload = f"{username}|{expires_at}"
    signature = hmac.new(
        settings.app_secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    token = f"{payload}|{signature}".encode()
    return base64.urlsafe_b64encode(token).decode()


def read_session_token(token: str, settings: Settings) -> CurrentUser | None:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        username, expires_at_text, signature = decoded.rsplit("|", 2)
        payload = f"{username}|{expires_at_text}"
        expected_signature = hmac.new(
            settings.app_secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None
        if int(expires_at_text) < int(time.time()):
            return None
        return CurrentUser(username=username)
    except (ValueError, TypeError):
        return None


def get_current_user(request: Request, settings: Settings) -> CurrentUser | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return read_session_token(token, settings)
