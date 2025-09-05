from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from ..config import get_settings


def admin_auth(x_admin_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin functions disabled")
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")

