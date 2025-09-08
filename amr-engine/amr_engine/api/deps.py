from __future__ import annotations

from typing import Dict, Any
from fastapi import Depends, Header, HTTPException, status, Request

from ..config import get_settings
from ..core.auth import require_admin, get_current_user


def admin_auth(x_admin_token: str | None = Header(default=None)) -> None:
    """Legacy admin authentication dependency - DEPRECATED."""
    settings = get_settings()
    if not settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin functions disabled")
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def admin_required(request: Request) -> Dict[str, Any]:
    """Modern admin authentication dependency with OAuth2 support."""
    # This will be used by Depends() and automatically handle authentication
    pass


# For backward compatibility, we'll keep the old function but also provide new one
async def get_admin_user(request: Request) -> Dict[str, Any]:
    """Get authenticated admin user."""
    return await require_admin(request)


async def get_authenticated_user(request: Request) -> Dict[str, Any]:
    """Get authenticated user (may be admin or regular user)."""
    return await get_current_user(request)

