"""
Test cases for disc diffusion missing values returning 'Requires Review'.
"""

import pytest

from amr_engine.core.classifier import Classifier
from amr_engine.core.rules_loader import RulesLoader
from amr_engine.core.schemas import ClassificationInput


@pytest.fixture
def classifier():
    """Create classifier with loaded rules."""
    loader = RulesLoader()
    loader.load()
    return Classifier(loader)


def test_disc_missing_zone_diameter_requires_review(classifier):
    """Test that missing disc zone diameter returns 'Requires Review'."""
    input_data = ClassificationInput(
        organism="Escherichia coli",
        antibiotic="Ciprofloxacin",
        method="DISC",
        disc_zone_mm=None,  # Missing disc zone diameter
        specimenId="TEST-001"
    )
    
    result = classifier.classify(input_data)
    
    assert result.decision == "Requires Review"
    assert "Missing disc zone diameter" in result.reason
    assert result.organism == "Escherichia coli"
    assert result.antibiotic == "Ciprofloxacin"
    assert result.method == "DISC"
    assert result.specimenId == "TEST-001"


def test_disc_with_valid_zone_diameter_normal_classification(classifier):
    """Test that disc with valid zone diameter gets normal classification."""
    input_data = ClassificationInput(
        organism="Escherichia coli",
        antibiotic="Ciprofloxacin",
        method="DISC",
        disc_zone_mm=25.0,  # Valid zone diameter
        specimenId="TEST-002"
    )
    
    result = classifier.classify(input_data)
    
    # Should get normal classification (S/I/R/RR), not 'Requires Review'
    assert result.decision in ["S", "I", "R", "RR"]
    assert result.decision != "Requires Review"
    assert "Missing disc zone diameter" not in result.reason


def test_mic_missing_value_still_returns_rr(classifier):
    """Test that missing MIC values still return 'RR' as before."""
    input_data = ClassificationInput(
        organism="Escherichia coli",
        antibiotic="Ciprofloxacin",
        method="MIC",
        mic_mg_L=None,  # Missing MIC value
        specimenId="TEST-003"
    )
    
    result = classifier.classify(input_data)
    
    # MIC missing values should still return RR, not 'Requires Review'
    assert result.decision == "RR"
    assert "Missing MIC value" in result.reason
    assert result.organism == "Escherichia coli"
    assert result.antibiotic == "Ciprofloxacin"
    assert result.method == "MIC"


def test_multiple_disc_missing_values(classifier):
    """Test multiple disc diffusion cases with missing values."""
    test_cases = [
        {
            "organism": "Staphylococcus aureus",
            "antibiotic": "Gentamicin",
            "expected_decision": "Requires Review"
        },
        {
            "organism": "Klebsiella pneumoniae",
            "antibiotic": "Amoxicillin",
            "expected_decision": "Requires Review"
        }
    ]
    
    for i, case in enumerate(test_cases):
        input_data = ClassificationInput(
            organism=case["organism"],
            antibiotic=case["antibiotic"],
            method="DISC",
            disc_zone_mm=None,
            specimenId=f"TEST-00{i+4}"
        )
        
        result = classifier.classify(input_data)
        assert result.decision == case["expected_decision"]
        assert "Missing disc zone diameter" in result.reason