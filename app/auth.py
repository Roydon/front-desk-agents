"""HTTP Basic Auth for the hosted demo. Auto-disabled when APP_USER/APP_PASSWORD are unset."""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.settings import settings

_basic = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    if not settings.auth_enabled:
        return
    ok = (
        credentials is not None
        and secrets.compare_digest(credentials.username, settings.app_user)
        and secrets.compare_digest(credentials.password, settings.app_password)
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
