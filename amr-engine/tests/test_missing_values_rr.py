from amr_engine.core.classifier import Classifier
from amr_engine.core.rules_loader import RulesLoader
from amr_engine.core.schemas import ClassificationInput


def make_classifier():
    loader = RulesLoader()
    loader.load()
    return Classifier(loader)


def test_missing_method_yields_rr():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Escherichia coli",
            antibiotic="Ciprofloxacin",
        )
    )
    assert res.decision == "RR"
    assert "Unsupported" in res.reason or "No matching rule" in res.reason


def test_no_matching_rule_rr():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Escherichia coli",
            antibiotic="Nonexistent",
            method="MIC",
            mic_mg_L=1.0,
        )
    )
    assert res.decision == "RR"
    assert "No matching rule" in res.reason

