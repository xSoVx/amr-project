from fastapi.testclient import TestClient


def test_health_and_version(client: TestClient):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    v = client.get("/version")
    assert v.status_code == 200
    assert "service" in v.json()


def test_metrics_endpoint(client: TestClient):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "amr_classifications_total" in r.text


def test_dry_run_endpoint(client: TestClient):
    payload = {
        "organism": "Escherichia coli",
        "antibiotic": "Ciprofloxacin",
        "method": "MIC",
        "mic_mg_L": 0.25
    }
    r = client.post("/rules/dry-run", json=payload)
    assert r.status_code == 200
    assert r.json()["decision"] in ("S", "I", "R", "RR")

