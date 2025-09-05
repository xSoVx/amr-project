from amr_engine.core.classifier import Classifier
from amr_engine.core.rules_loader import RulesLoader
from amr_engine.core.schemas import ClassificationInput


def test_esbl_exception_triggers_rr():
    loader = RulesLoader()
    loader.load()
    c = Classifier(loader)
    res = c.classify(
        ClassificationInput(
            organism="Escherichia coli",
            antibiotic="Ciprofloxacin",
            method="MIC",
            mic_mg_L=0.25,
            features={"esbl": True},
        )
    )
    assert res.decision == "RR"
    assert "Exception" in res.reason or "review" in res.reason.lower()

