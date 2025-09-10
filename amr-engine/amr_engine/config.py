from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


ProfilePack = Literal["IL-Core", "US-Core", "IPS", "Base"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="")

    SERVICE_NAME: str = "amr-engine"
    LOG_LEVEL: str = "INFO"
    AMR_RULES_PATH: str = "amr_engine/rules/eucast_v_2025_1.yaml"
    ADMIN_TOKEN: Optional[str] = None
    ADMIN_TOKEN_DEVELOPMENT_ONLY: bool = True
    EUST_VER: Optional[str] = None
    
    # FHIR Profile Pack Configuration
    FHIR_PROFILE_PACK: ProfilePack = "Base"
    FHIR_VALIDATION_ENABLED: bool = True
    
    # OAuth2 Configuration
    OAUTH2_ENABLED: bool = False
    OAUTH2_ISSUER_URL: Optional[str] = None
    OAUTH2_AUDIENCE: Optional[str] = None
    
    # mTLS Configuration
    MTLS_ENABLED: bool = False
    MTLS_CA_CERT_PATH: Optional[str] = None
    MTLS_CLIENT_CERT_PATH: Optional[str] = None
    MTLS_CLIENT_KEY_PATH: Optional[str] = None
    
    # Redis Cache Configuration
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 20
    REDIS_SOCKET_TIMEOUT: int = 5
    CACHE_DEFAULT_TTL: int = 3600  # 1 hour
    CACHE_RULE_TTL: int = 7200  # 2 hours
    
    # Pseudonymization Configuration
    PSEUDONYMIZATION_ENABLED: bool = True
    PSEUDONYM_SALT_KEY: Optional[str] = None
    PSEUDONYM_ENCRYPTION_KEY: Optional[str] = None
    PSEUDONYM_STORAGE_PATH: str = "/tmp/pseudonym_storage"
    PSEUDONYM_DUMMY_ID_PREFIX: str = "PSY"
    PSEUDONYM_DUMMY_ID_LENGTH: int = 12

    def rules_paths(self) -> list[Path]:
        p = Path(self.AMR_RULES_PATH)
        if p.is_dir():
            return sorted(
                [
                    *p.glob("*.yaml"),
                    *p.glob("*.yml"),
                    *p.glob("*.json"),
                ]
            )
        return [p]


def get_settings() -> Settings:
    return Settings()

