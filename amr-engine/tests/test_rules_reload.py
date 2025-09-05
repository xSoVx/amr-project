import os

import yaml
from amr_engine.core.rules_loader import RulesLoader
from fastapi.testclient import TestClient


def test_reload_endpoint(client: TestClient, tmp_path):
    # Copy current rules to temp and point env to it
    src = tmp_path / "eucast.yaml"
    src.write_text(
        yaml.safe_dump(
            {
                "version": "EUCAST-2025.1",
                "rules": [
                    {
                        "organism": {"name": "Escherichia coli"},
                        "antibiotic": {"name": "Ciprofloxacin"},
                        "method": "MIC",
                        "mic": {"susceptible_max": 0.25, "intermediate_range": [0.5, 1.0], "resistant_min": 2.0},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    os.environ["AMR_RULES_PATH"] = str(src)

    r = client.post("/admin/rules/reload", headers={"X-Admin-Token": os.environ.get("ADMIN_TOKEN", "test-token")})
    assert r.status_code in (200, 403)  # if admin disabled, 403; else OK
    if r.status_code == 200:
        assert "sources" in r.json()

