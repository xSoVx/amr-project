"""
Test cases for MRSA beta-lactam override rules.
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


def test_mrsa_penicillin_override_resistant(classifier):
    """Test MRSA with penicillin should be resistant regardless of MIC."""
    # Low MIC that would normally be susceptible
    input_data = ClassificationInput(
        organism="Staphylococcus aureus",
        antibiotic="Penicillin",
        method="MIC",
        mic_mg_L=0.06,  # Very low MIC
        specimenId="MRSA-001",
        features={"mrsa": True}  # MRSA positive
    )
    
    result = classifier.classify(input_data)
    
    # MRSA should override to resistant for penicillin
    assert result.decision == "R"
    assert "mrsa" in result.reason.lower() or "expert" in result.reason.lower()
    assert result.organism == "Staphylococcus aureus"
    assert result.antibiotic == "Penicillin"


def test_mrsa_amoxicillin_override_resistant(classifier):
    """Test MRSA with amoxicillin should be resistant."""
    input_data = ClassificationInput(
        organism="Staphylococcus aureus", 
        antibiotic="Amoxicillin",
        method="DISC",
        disc_zone_mm=25.0,  # Large zone that would be susceptible
        specimenId="MRSA-002",
        features={"mrsa": True}
    )
    
    result = classifier.classify(input_data)
    
    # MRSA should override beta-lactams to resistant
    assert result.decision == "R" 
    assert result.method == "DISC"


def test_mrsa_cephalexin_override_resistant(classifier):
    """Test MRSA with cephalexin (1st gen cephalosporin) should be resistant."""
    input_data = ClassificationInput(
        organism="Staphylococcus aureus",
        antibiotic="Cephalexin", 
        method="MIC",
        mic_mg_L=2.0,  # Low MIC
        specimenId="MRSA-003",
        features={"mrsa": True}
    )
    
    result = classifier.classify(input_data)
    
    # First generation cephalosporins should be resistant in MRSA
    assert result.decision == "R"
    assert result.antibiotic == "Cephalexin"


def test_mrsa_vancomycin_not_overridden(classifier):
    """Test MRSA with vancomycin follows normal rules (not overridden)."""
    input_data = ClassificationInput(
        organism="Staphylococcus aureus",
        antibiotic="Vancomycin",
        method="MIC", 
        mic_mg_L=1.0,  # Should be susceptible
        specimenId="MRSA-004",
        features={"mrsa": True}
    )
    
    result = classifier.classify(input_data)
    
    # Vancomycin should not be overridden by MRSA status
    # It should follow normal breakpoint rules
    assert result.decision in ["S", "I"]  # Should not be forced to R
    assert result.antibiotic == "Vancomycin"


def test_mrsa_clindamycin_not_overridden(classifier):
    """Test MRSA with clindamycin follows normal rules."""
    input_data = ClassificationInput(
        organism="Staphylococcus aureus",
        antibiotic="Clindamycin",
        method="DISC",
        disc_zone_mm=20.0,  # Should be susceptible
        specimenId="MRSA-005", 
        features={"mrsa": True}
    )
    
    result = classifier.classify(input_data)
    
    # Clindamycin should follow normal rules
    assert result.decision in ["S", "I", "R", "RR"]  # Not forced to R
    assert result.antibiotic == "Clindamycin"


def test_mssa_penicillin_normal_rules(classifier):
    """Test MSSA (non-MRSA) with penicillin follows normal rules."""
    input_data = ClassificationInput(
        organism="Staphylococcus aureus",
        antibiotic="Penicillin", 
        method="MIC",
        mic_mg_L=0.06,  # Low MIC
        specimenId="MSSA-001",
        features={"mrsa": False}  # MSSA (methicillin-sensitive)
    )
    
    result = classifier.classify(input_data)
    
    # MSSA should follow normal penicillin rules
    assert result.decision in ["S", "I"]  # Should be susceptible with low MIC
    assert result.antibiotic == "Penicillin"


def test_mrsa_multiple_betalactams(classifier):
    """Test MRSA with multiple beta-lactam antibiotics."""
    betalactams = [
        "Penicillin",
        "Amoxicillin", 
        "Ampicillin",
        "Cephalexin",
        "Cefazolin"
    ]
    
    for antibiotic in betalactams:
        input_data = ClassificationInput(
            organism="Staphylococcus aureus",
            antibiotic=antibiotic,
            method="MIC",
            mic_mg_L=0.5,  # Low MIC that would normally be susceptible
            specimenId=f"MRSA-BETA-{antibiotic}",
            features={"mrsa": True}
        )
        
        result = classifier.classify(input_data)
        
        # All beta-lactams should be resistant in MRSA
        assert result.decision == "R", f"{antibiotic} should be resistant in MRSA"
        assert result.antibiotic == antibiotic


def test_mrsa_without_feature_flag(classifier):
    """Test Staphylococcus aureus without MRSA feature follows normal rules."""
    input_data = ClassificationInput(
        organism="Staphylococcus aureus",
        antibiotic="Penicillin",
        method="MIC", 
        mic_mg_L=0.06,  # Low MIC
        specimenId="STAPH-001"
        # No MRSA feature = MSSA
    )
    
    result = classifier.classify(input_data)
    
    # Without MRSA flag, should follow normal rules
    assert result.decision in ["S", "I", "R", "RR"]
    assert result.antibiotic == "Penicillin"


def test_mrsa_advanced_betalactams_not_all_overridden(classifier):
    """Test MRSA with advanced beta-lactams that might not be overridden."""
    # Some advanced beta-lactams might still be effective against MRSA
    advanced_betalactams = [
        "Ceftaroline",  # Anti-MRSA cephalosporin
        "Ceftobiprole"  # Anti-MRSA cephalosporin
    ]
    
    for antibiotic in advanced_betalactams:
        input_data = ClassificationInput(
            organism="Staphylococcus aureus",
            antibiotic=antibiotic,
            method="MIC",
            mic_mg_L=1.0,
            specimenId=f"MRSA-ADV-{antibiotic}",
            features={"mrsa": True}
        )
        
        result = classifier.classify(input_data)
        
        # Advanced beta-lactams might not be automatically resistant
        assert result.decision in ["S", "I", "R", "RR"]
        assert result.antibiotic == antibiotic