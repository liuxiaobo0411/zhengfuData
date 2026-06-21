from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.services.auth import CurrentUser, get_current_user


def require_user(request: Request) -> CurrentUser | RedirectResponse:
    user = get_current_user(request, get_settings())
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return user
