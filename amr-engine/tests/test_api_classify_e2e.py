import json

from amr_engine.main import create_app
from fastapi.testclient import TestClient


def test_api_classify_bundle_success(client: TestClient):
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": "18906-8",
                                "display": "Ciprofloxacin [Susceptibility]",
                            }
                        ]
                    },
                    "valueQuantity": {"value": 0.25, "unit": "mg/L"},
                    "method": {"coding": [{"code": "MIC"}]},
                    "specimen": {"reference": "Specimen/1"},
                    "subject": {"reference": "Patient/123"},
                    "note": [{"text": "Escherichia coli; ESBL=false"}],
                }
            }
        ],
    }
    r = client.post("/classify", json=bundle)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert data[0]["decision"] == "S"


def test_api_classify_fhir_validation_error(client: TestClient):
    bad = {"resourceType": "Bundle", "type": "collection", "entry": [{"resource": {"resourceType": "Observation"}}]}
    r = client.post("/classify", json=bad)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["resourceType"] == "OperationOutcome"

