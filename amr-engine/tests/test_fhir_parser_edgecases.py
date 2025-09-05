from fastapi.testclient import TestClient


def test_missing_zone_for_disc_returns_400_with_operation_outcome(client: TestClient):
    obs = {
        "resourceType": "Observation",
        "code": {"text": "Ciprofloxacin [Susceptibility] by disk diffusion"},
        "method": {"text": "DISC"},
        "specimen": {"reference": "Specimen/1"},
        "subject": {"reference": "Patient/123"},
        "note": [{"text": "Escherichia coli"}]
    }
    # Will fail later since code display exists but no valueQuantity; parser allows it, classifier yields RR
    r = client.post("/classify", json=obs)
    assert r.status_code == 200
    data = r.json()[0]
    assert data["decision"] == "RR"
    assert "Missing disc" in data["reason"]


def test_missing_code_display_fails_validation(client: TestClient):
    obs = {
        "resourceType": "Observation",
        "valueQuantity": {"value": 1, "unit": "mg/L"},
        "method": {"coding": [{"code": "MIC"}]},
        "specimen": {"reference": "Specimen/1"},
        "subject": {"reference": "Patient/123"},
        "note": [{"text": "Escherichia coli"}]
    }
    r = client.post("/classify", json=obs)
    assert r.status_code == 400
    body = r.json()
    assert "OperationOutcome" in body["detail"]["resourceType"]

