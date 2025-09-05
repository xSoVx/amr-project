from amr_engine.core.classifier import Classifier
from amr_engine.core.rules_loader import RulesLoader
from amr_engine.core.schemas import ClassificationInput


def make_classifier():
    loader = RulesLoader()
    loader.load()
    return Classifier(loader)


def test_disc_susceptible_boundary():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Pseudomonas aeruginosa",
            antibiotic="Piperacillin-tazobactam",
            method="DISC",
            disc_zone_mm=21,
        )
    )
    assert res.decision == "S"


def test_disc_intermediate_low():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Pseudomonas aeruginosa",
            antibiotic="Piperacillin-tazobactam",
            method="DISC",
            disc_zone_mm=18,
        )
    )
    assert res.decision == "I"


def test_disc_resistant_max_boundary():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Pseudomonas aeruginosa",
            antibiotic="Piperacillin-tazobactam",
            method="DISC",
            disc_zone_mm=17,
        )
    )
    assert res.decision == "R"


def test_disc_missing_value_returns_rr():
    c = make_classifier()
    res = c.classify(
        ClassificationInput(
            organism="Pseudomonas aeruginosa",
            antibiotic="Piperacillin-tazobactam",
            method="DISC",
        )
    )
    assert res.decision == "RR"
    assert "Missing disc" in res.reason

