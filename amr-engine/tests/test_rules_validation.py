from pathlib import Path

import json
import yaml
from amr_engine.core.rules_loader import RulesLoader


def test_rules_schema_valid():
    loader = RulesLoader()
    ruleset = loader.load()
    assert ruleset is not None
    assert len(ruleset.rules) >= 1


def test_rules_invalid_missing_required(tmp_path):
    bad = {
        "rules": [
            {
                # missing organism/antibiotic required fields
                "method": "MIC",
                "mic": {"susceptible_max": 1}
            }
        ]
    }
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(bad), encoding="utf-8")

    from amr_engine.config import Settings

    s = Settings(AMR_RULES_PATH=str(p))
    loader = RulesLoader()
    loader.settings = s  # inject
    try:
        loader.load()
        assert False, "Should have raised"
    except Exception as e:
        assert "validation" in str(e).lower() or "Rule validation" in str(e)

