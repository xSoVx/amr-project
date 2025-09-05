from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="")

    SERVICE_NAME: str = "amr-engine"
    LOG_LEVEL: str = "INFO"
    AMR_RULES_PATH: str = "amr_engine/rules/eucast_v_2025_1.yaml"
    ADMIN_TOKEN: Optional[str] = None
    EUST_VER: Optional[str] = None

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

