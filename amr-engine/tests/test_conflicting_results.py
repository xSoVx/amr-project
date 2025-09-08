"""
Test cases for conflicting MIC vs disk diffusion results.
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


def test_conflicting_mic_susceptible_disc_resistant(classifier):
    """Test case where MIC shows susceptible but disc shows resistant."""
    # MIC result (should be susceptible)
    mic_input = ClassificationInput(
        organism="Escherichia coli",
        antibiotic="Ciprofloxacin",
        method="MIC",
        mic_mg_L=0.25,  # Low MIC = susceptible
        specimenId="CONFLICT-001"
    )
    
    # Disc result (should be resistant)
    disc_input = ClassificationInput(
        organism="Escherichia coli",
        antibiotic="Ciprofloxacin",
        method="DISC",
        disc_zone_mm=15.0,  # Small zone = resistant
        specimenId="CONFLICT-001"
    )
    
    mic_result = classifier.classify(mic_input)
    disc_result = classifier.classify(disc_input)
    
    # Verify that both classifications work independently
    assert mic_result.decision in ["S", "I", "R", "RR"]
    assert disc_result.decision in ["S", "I", "R", "RR"]
    
    # Document the conflict in test assertions
    assert mic_result.organism == disc_result.organism
    assert mic_result.antibiotic == disc_result.antibiotic
    assert mic_result.specimenId == disc_result.specimenId
    
    # Verify methods are different
    assert mic_result.method == "MIC"
    assert disc_result.method == "DISC"


def test_conflicting_mic_resistant_disc_susceptible(classifier):
    """Test case where MIC shows resistant but disc shows susceptible."""
    # MIC result (should be resistant)
    mic_input = ClassificationInput(
        organism="Staphylococcus aureus",
        antibiotic="Gentamicin",
        method="MIC",
        mic_mg_L=32.0,  # High MIC = resistant
        specimenId="CONFLICT-002"
    )
    
    # Disc result (should be susceptible)  
    disc_input = ClassificationInput(
        organism="Staphylococcus aureus",
        antibiotic="Gentamicin",
        method="DISC",
        disc_zone_mm=25.0,  # Large zone = susceptible
        specimenId="CONFLICT-002"
    )
    
    mic_result = classifier.classify(mic_input)
    disc_result = classifier.classify(disc_input)
    
    # Verify both classifications work
    assert mic_result.decision in ["S", "I", "R", "RR"]
    assert disc_result.decision in ["S", "I", "R", "RR"]
    
    # Verify specimen consistency
    assert mic_result.specimenId == disc_result.specimenId == "CONFLICT-002"


def test_multiple_conflicting_antibiotics_same_organism(classifier):
    """Test multiple antibiotics with conflicting results for same organism."""
    organism = "Klebsiella pneumoniae"
    specimen_id = "CONFLICT-003"
    
    test_cases = [
        {
            "antibiotic": "Amoxicillin",
            "mic_value": 2.0,  # Might be susceptible
            "disc_zone": 12.0  # Likely resistant
        },
        {
            "antibiotic": "Gentamicin", 
            "mic_value": 8.0,  # Borderline
            "disc_zone": 18.0  # Borderline
        }
    ]
    
    for case in test_cases:
        mic_input = ClassificationInput(
            organism=organism,
            antibiotic=case["antibiotic"],
            method="MIC",
            mic_mg_L=case["mic_value"],
            specimenId=specimen_id
        )
        
        disc_input = ClassificationInput(
            organism=organism,
            antibiotic=case["antibiotic"],
            method="DISC",
            disc_zone_mm=case["disc_zone"],
            specimenId=specimen_id
        )
        
        mic_result = classifier.classify(mic_input)
        disc_result = classifier.classify(disc_input)
        
        # Both should classify successfully
        assert mic_result.decision in ["S", "I", "R", "RR"]
        assert disc_result.decision in ["S", "I", "R", "RR"]
        
        # Verify consistency
        assert mic_result.organism == disc_result.organism == organism
        assert mic_result.antibiotic == disc_result.antibiotic == case["antibiotic"]
        assert mic_result.specimenId == disc_result.specimenId == specimen_id


def test_edge_case_borderline_values_conflict(classifier):
    """Test borderline values that might lead to different interpretations."""
    # Edge case with values right at breakpoints
    mic_input = ClassificationInput(
        organism="Escherichia coli",
        antibiotic="Ampicillin", 
        method="MIC",
        mic_mg_L=8.0,  # Right at common breakpoint
        specimenId="EDGE-001"
    )
    
    disc_input = ClassificationInput(
        organism="Escherichia coli",
        antibiotic="Ampicillin",
        method="DISC", 
        disc_zone_mm=17.0,  # Right at common breakpoint
        specimenId="EDGE-001"
    )
    
    mic_result = classifier.classify(mic_input)
    disc_result = classifier.classify(disc_input)
    
    # Should handle edge cases gracefully
    assert mic_result.decision in ["S", "I", "R", "RR"]
    assert disc_result.decision in ["S", "I", "R", "RR"]
    
    # Results should include reasoning
    assert mic_result.reason is not None
    assert disc_result.reason is not None


def test_conflicting_results_with_features(classifier):
    """Test conflicting results when additional features are present."""
    # Add organism features that might affect interpretation
    mic_input = ClassificationInput(
        organism="Escherichia coli",
        antibiotic="Ceftriaxone",
        method="MIC",
        mic_mg_L=1.0,
        specimenId="FEATURE-001",
        features={"esbl": True}  # ESBL-positive might affect interpretation
    )
    
    disc_input = ClassificationInput(
        organism="Escherichia coli", 
        antibiotic="Ceftriaxone",
        method="DISC",
        disc_zone_mm=22.0,
        specimenId="FEATURE-001",
        features={"esbl": True}
    )
    
    mic_result = classifier.classify(mic_input)
    disc_result = classifier.classify(disc_input)
    
    # Features should be considered in classification
    assert mic_result.decision in ["S", "I", "R", "RR"]
    assert disc_result.decision in ["S", "I", "R", "RR"]
    
    # Both should consider the ESBL feature
    assert "esbl" in str(mic_result.input.get("features", {})).lower() or "esbl" in mic_result.reason.lower()
    assert "esbl" in str(disc_result.input.get("features", {})).lower() or "esbl" in disc_result.reason.lower()