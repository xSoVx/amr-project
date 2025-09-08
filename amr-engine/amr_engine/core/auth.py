"""
Authentication and authorization module supporting OAuth2 and static tokens.
"""
from __future__ import annotations

import logging
import ssl
from typing import Optional, Dict, Any
from urllib.parse import urljoin

import httpx
import jwt
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config import get_settings

logger = logging.getLogger(__name__)


class OAuth2Validator:
    """OAuth2 token validator with JWKS support."""
    
    def __init__(self):
        self.settings = get_settings()
        self.jwks_cache: Dict[str, Any] = {}
        self.security = HTTPBearer(auto_error=False)
    
    async def get_jwks(self, issuer_url: str) -> Dict[str, Any]:
        """Get JWKS from OAuth2 issuer with caching."""
        if issuer_url in self.jwks_cache:
            return self.jwks_cache[issuer_url]
        
        try:
            # Discover JWKS endpoint
            discovery_url = urljoin(issuer_url, ".well-known/openid-configuration")
            
            async with httpx.AsyncClient(timeout=30) as client:
                # Get OpenID Connect discovery document
                discovery_response = await client.get(discovery_url)
                discovery_response.raise_for_status()
                discovery_data = discovery_response.json()
                
                # Get JWKS from discovery document
                jwks_uri = discovery_data.get("jwks_uri")
                if not jwks_uri:
                    raise ValueError("No jwks_uri found in discovery document")
                
                jwks_response = await client.get(jwks_uri)
                jwks_response.raise_for_status()
                jwks_data = jwks_response.json()
                
                # Cache JWKS data
                self.jwks_cache[issuer_url] = jwks_data
                return jwks_data
                
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from {issuer_url}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable"
            )
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate OAuth2 JWT token."""
        try:
            # Decode token header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                raise ValueError("Token missing key ID")
            
            # Get JWKS for token validation
            jwks = await self.get_jwks(self.settings.OAUTH2_ISSUER_URL)
            
            # Find matching key
            key = None
            for jwk in jwks.get("keys", []):
                if jwk.get("kid") == kid:
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
                    break
            
            if not key:
                raise ValueError(f"No matching key found for kid: {kid}")
            
            # Validate and decode token
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.settings.OAUTH2_AUDIENCE,
                issuer=self.settings.OAUTH2_ISSUER_URL
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )


class AuthenticationService:
    """Unified authentication service supporting both OAuth2 and static tokens."""
    
    def __init__(self):
        self.settings = get_settings()
        self.oauth2_validator = OAuth2Validator() if self.settings.OAUTH2_ENABLED else None
        self.security = HTTPBearer(auto_error=False)
    
    async def authenticate_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """Authenticate incoming request using configured method."""
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            # Check for legacy X-Admin-Token header
            legacy_token = request.headers.get("X-Admin-Token")
            if legacy_token and self.settings.ADMIN_TOKEN:
                return await self._validate_static_token(legacy_token)
            return None
        
        if not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # OAuth2 validation if enabled
        if self.settings.OAUTH2_ENABLED and self.oauth2_validator:
            try:
                return await self.oauth2_validator.validate_token(token)
            except HTTPException:
                # Fall back to static token if OAuth2 fails and static token is configured
                if self.settings.ADMIN_TOKEN:
                    return await self._validate_static_token(token)
                raise
        
        # Static token validation
        if self.settings.ADMIN_TOKEN:
            return await self._validate_static_token(token)
        
        return None
    
    async def _validate_static_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate static admin token."""
        if token == self.settings.ADMIN_TOKEN:
            return {
                "sub": "admin",
                "scope": "admin",
                "auth_method": "static_token"
            }
        return None
    
    def require_admin_auth(self) -> bool:
        """Check if admin authentication is required."""
        return self.settings.OAUTH2_ENABLED or bool(self.settings.ADMIN_TOKEN)


# Global authentication service instance
auth_service = AuthenticationService()


async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Dependency to get current authenticated user."""
    if not auth_service.require_admin_auth():
        return {"sub": "anonymous", "scope": "public"}
    
    user = await auth_service.authenticate_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user


async def require_admin(request: Request) -> Dict[str, Any]:
    """Dependency to require admin authentication."""
    user = await get_current_user(request)
    
    # Check if user has admin scope
    scope = user.get("scope", "")
    if "admin" not in scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return user