from amr_engine.core.classifier import Classifier
from amr_engine.core.rules_loader import RulesLoader
from amr_engine.core.schemas import ClassificationInput


def make_classifier():
    loader = RulesLoader()
    loader.load()
    return Classifier(loader)


def test_mic_susceptible_boundary():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Escherichia coli",
            antibiotic="Ciprofloxacin",
            method="MIC",
            mic_mg_L=0.25,
        )
    )
    assert res.decision == "S"
    assert "susceptible_max" in res.reason


def test_mic_intermediate_range_low():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Escherichia coli",
            antibiotic="Ciprofloxacin",
            method="MIC",
            mic_mg_L=0.5,
        )
    )
    assert res.decision == "I"


def test_mic_intermediate_range_high():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Escherichia coli",
            antibiotic="Ciprofloxacin",
            method="MIC",
            mic_mg_L=1.0,
        )
    )
    assert res.decision == "I"


def test_mic_resistant_min_boundary():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Escherichia coli",
            antibiotic="Ciprofloxacin",
            method="MIC",
            mic_mg_L=2.0,
        )
    )
    assert res.decision == "R"


def test_mic_missing_value_returns_rr():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Escherichia coli",
            antibiotic="Ciprofloxacin",
            method="MIC",
        )
    )
    assert res.decision == "RR"
    assert "Missing MIC" in res.reason

