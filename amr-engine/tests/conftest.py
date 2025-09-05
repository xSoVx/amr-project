import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from amr_engine.main import create_app


@pytest.fixture(scope="session", autouse=True)
def set_env(tmp_path_factory):
    # Ensure rules path is available
    os.environ.setdefault("AMR_RULES_PATH", str(Path("amr_engine/rules/eucast_v_2025_1.yaml")))
    os.environ.setdefault("ADMIN_TOKEN", "test-token")
    os.environ.setdefault("LOG_LEVEL", "INFO")


@pytest.fixture()
def client():
    app = create_app()
    return TestClient(app)


def load_sample(name: str):
    p = Path("amr_engine/samples") / name
    return json.loads(p.read_text(encoding="utf-8"))

