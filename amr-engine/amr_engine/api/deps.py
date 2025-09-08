from __future__ import annotations

from typing import Dict, Any
from fastapi import Depends, Header, HTTPException, status, Request

from ..config import get_settings
from ..core.auth import require_admin, get_current_user


def admin_auth(x_admin_token: str | None = Header(default=None)) -> None:
    """Legacy admin authentication dependency - DEPRECATED.
    
    Use `require_admin_auth` dependency instead for modern authentication.
    This function is kept for backward compatibility only.
    """
    import warnings
    warnings.warn(
        "admin_auth is deprecated. Use require_admin_auth for better security.",
        DeprecationWarning,
        stacklevel=2
    )
    
    settings = get_settings()
    if not settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin functions disabled")
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


async def admin_required(request: Request) -> Dict[str, Any]:
    """Modern admin authentication dependency with OAuth2 support."""
    return await require_admin(request)


# Aliases for different use cases
async def require_admin_auth(request: Request) -> Dict[str, Any]:
    """Require admin authentication - preferred dependency for admin endpoints."""
    return await require_admin(request)


async def get_admin_user(request: Request) -> Dict[str, Any]:
    """Get authenticated admin user - alias for require_admin."""
    return await require_admin(request)


async def get_authenticated_user(request: Request) -> Dict[str, Any]:
    """Get authenticated user (may be admin or regular user)."""
    return await get_current_user(request)

