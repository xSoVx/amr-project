"""
Golden dataset tests with comprehensive coverage enforcement.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, List, Any

from amr_engine.core.classifier import Classifier
from amr_engine.core.rules_loader import RulesLoader
from amr_engine.core.schemas import ClassificationInput, ClassificationResult


class GoldenDatasetTester:
    """Test runner for golden dataset validation with coverage tracking."""
    
    def __init__(self):
        self.loader = RulesLoader()
        self.loader.load()
        self.classifier = Classifier(self.loader)
        
        # Coverage tracking
        self.organism_coverage = set()
        self.antibiotic_coverage = set()
        self.method_coverage = set()
        self.decision_coverage = set()
        self.feature_coverage = set()
        
        # Expected minimum coverage percentages
        self.min_coverage_percent = 80
        
        # Golden dataset - comprehensive test cases
        self.golden_dataset = self._create_golden_dataset()
    
    def _create_golden_dataset(self) -> List[Dict[str, Any]]:
        """Create comprehensive golden dataset for AMR classification testing."""
        return [
            # Escherichia coli - MIC tests
            {
                "input": {
                    "organism": "Escherichia coli",
                    "antibiotic": "Ciprofloxacin", 
                    "method": "MIC",
                    "mic_mg_L": 0.25,
                    "specimenId": "GOLD-001"
                },
                "expected": {
                    "decision": "S",
                    "organism": "Escherichia coli",
                    "antibiotic": "Ciprofloxacin"
                }
            },
            {
                "input": {
                    "organism": "Escherichia coli",
                    "antibiotic": "Ciprofloxacin",
                    "method": "MIC", 
                    "mic_mg_L": 4.0,
                    "specimenId": "GOLD-002"
                },
                "expected": {
                    "decision": "R",
                    "organism": "Escherichia coli",
                    "antibiotic": "Ciprofloxacin"
                }
            },
            
            # Escherichia coli - Disc tests
            {
                "input": {
                    "organism": "Escherichia coli",
                    "antibiotic": "Ampicillin",
                    "method": "DISC",
                    "disc_zone_mm": 20.0,
                    "specimenId": "GOLD-003"
                },
                "expected": {
                    "decision": ["S", "I"],  # Could be either depending on breakpoints
                    "organism": "Escherichia coli",
                    "antibiotic": "Ampicillin"
                }
            },
            {
                "input": {
                    "organism": "Escherichia coli",
                    "antibiotic": "Ampicillin",
                    "method": "DISC",
                    "disc_zone_mm": 10.0,
                    "specimenId": "GOLD-004"
                },
                "expected": {
                    "decision": "R",
                    "organism": "Escherichia coli", 
                    "antibiotic": "Ampicillin"
                }
            },
            
            # Staphylococcus aureus - MIC tests
            {
                "input": {
                    "organism": "Staphylococcus aureus",
                    "antibiotic": "Gentamicin",
                    "method": "MIC",
                    "mic_mg_L": 2.0,
                    "specimenId": "GOLD-005"
                },
                "expected": {
                    "decision": "S",
                    "organism": "Staphylococcus aureus",
                    "antibiotic": "Gentamicin"
                }
            },
            
            # MRSA with beta-lactam override
            {
                "input": {
                    "organism": "Staphylococcus aureus",
                    "antibiotic": "Penicillin",
                    "method": "MIC",
                    "mic_mg_L": 0.06,
                    "specimenId": "GOLD-006",
                    "features": {"mrsa": True}
                },
                "expected": {
                    "decision": "R",  # Should be overridden to resistant
                    "organism": "Staphylococcus aureus",
                    "antibiotic": "Penicillin"
                }
            },
            
            # ESBL-positive organism
            {
                "input": {
                    "organism": "Escherichia coli",
                    "antibiotic": "Ceftriaxone", 
                    "method": "MIC",
                    "mic_mg_L": 1.0,
                    "specimenId": "GOLD-007",
                    "features": {"esbl": True}
                },
                "expected": {
                    "decision": "RR",  # Should require review due to ESBL
                    "organism": "Escherichia coli",
                    "antibiotic": "Ceftriaxone"
                }
            },
            
            # Klebsiella pneumoniae
            {
                "input": {
                    "organism": "Klebsiella pneumoniae",
                    "antibiotic": "Meropenem",
                    "method": "MIC",
                    "mic_mg_L": 0.25,
                    "specimenId": "GOLD-008"
                },
                "expected": {
                    "decision": "S",
                    "organism": "Klebsiella pneumoniae",
                    "antibiotic": "Meropenem"
                }
            },
            
            # Pseudomonas aeruginosa
            {
                "input": {
                    "organism": "Pseudomonas aeruginosa",
                    "antibiotic": "Piperacillin",
                    "method": "DISC",
                    "disc_zone_mm": 25.0,
                    "specimenId": "GOLD-009"
                },
                "expected": {
                    "decision": ["S", "I"],
                    "organism": "Pseudomonas aeruginosa",
                    "antibiotic": "Piperacillin"
                }
            },
            
            # Missing values - should return 'Requires Review'
            {
                "input": {
                    "organism": "Escherichia coli",
                    "antibiotic": "Ciprofloxacin",
                    "method": "DISC",
                    "disc_zone_mm": None,
                    "specimenId": "GOLD-010"
                },
                "expected": {
                    "decision": "Requires Review",
                    "organism": "Escherichia coli",
                    "antibiotic": "Ciprofloxacin"
                }
            },
            
            # Borderline MIC values
            {
                "input": {
                    "organism": "Escherichia coli",
                    "antibiotic": "Amoxicillin",
                    "method": "MIC", 
                    "mic_mg_L": 8.0,  # Right at breakpoint
                    "specimenId": "GOLD-011"
                },
                "expected": {
                    "decision": ["S", "I", "R"],  # Could be any depending on exact breakpoint
                    "organism": "Escherichia coli",
                    "antibiotic": "Amoxicillin"
                }
            },
            
            # Vancomycin against MRSA (should not be overridden)
            {
                "input": {
                    "organism": "Staphylococcus aureus",
                    "antibiotic": "Vancomycin",
                    "method": "MIC",
                    "mic_mg_L": 1.0,
                    "specimenId": "GOLD-012",
                    "features": {"mrsa": True}
                },
                "expected": {
                    "decision": "S",  # Vancomycin should not be auto-resistant
                    "organism": "Staphylococcus aureus",
                    "antibiotic": "Vancomycin"
                }
            },
            
            # Multiple features
            {
                "input": {
                    "organism": "Klebsiella pneumoniae",
                    "antibiotic": "Gentamicin",
                    "method": "DISC",
                    "disc_zone_mm": 16.0,
                    "specimenId": "GOLD-013",
                    "features": {"esbl": True, "carbapenemase": False}
                },
                "expected": {
                    "decision": ["S", "I", "R", "RR"],
                    "organism": "Klebsiella pneumoniae",
                    "antibiotic": "Gentamicin"
                }
            }
        ]
    
    def run_golden_dataset_tests(self) -> Dict[str, Any]:
        """Run all golden dataset tests and return results with coverage metrics."""
        results = {
            "total_tests": len(self.golden_dataset),
            "passed_tests": 0,
            "failed_tests": 0,
            "failures": [],
            "coverage_metrics": {}
        }
        
        for i, test_case in enumerate(self.golden_dataset):
            try:
                input_data = ClassificationInput(**test_case["input"])
                actual_result = self.classifier.classify(input_data)
                expected = test_case["expected"]
                
                # Track coverage
                self._track_coverage(input_data, actual_result)
                
                # Validate result
                if self._validate_result(actual_result, expected):
                    results["passed_tests"] += 1
                else:
                    results["failed_tests"] += 1
                    results["failures"].append({
                        "test_index": i,
                        "input": test_case["input"],
                        "expected": expected,
                        "actual": {
                            "decision": actual_result.decision,
                            "organism": actual_result.organism,
                            "antibiotic": actual_result.antibiotic,
                            "reason": actual_result.reason
                        }
                    })
                    
            except Exception as e:
                results["failed_tests"] += 1
                results["failures"].append({
                    "test_index": i,
                    "input": test_case["input"],
                    "error": str(e)
                })
        
        # Calculate coverage metrics
        results["coverage_metrics"] = self._calculate_coverage()
        
        return results
    
    def _validate_result(self, actual: ClassificationResult, expected: Dict[str, Any]) -> bool:
        """Validate actual result against expected values."""
        # Check decision
        expected_decision = expected["decision"]
        if isinstance(expected_decision, list):
            if actual.decision not in expected_decision:
                return False
        else:
            if actual.decision != expected_decision:
                return False
        
        # Check organism and antibiotic
        if actual.organism != expected["organism"]:
            return False
        if actual.antibiotic != expected["antibiotic"]:
            return False
        
        return True
    
    def _track_coverage(self, input_data: ClassificationInput, result: ClassificationResult):
        """Track coverage metrics."""
        if input_data.organism:
            self.organism_coverage.add(input_data.organism)
        if input_data.antibiotic:
            self.antibiotic_coverage.add(input_data.antibiotic)
        if input_data.method:
            self.method_coverage.add(input_data.method)
        if result.decision:
            self.decision_coverage.add(result.decision)
        
        # Track features
        for feature_key in input_data.features.keys():
            self.feature_coverage.add(feature_key)
    
    def _calculate_coverage(self) -> Dict[str, Any]:
        """Calculate coverage percentages."""
        # Get total available items from rules/system
        total_organisms = self._get_total_organisms()
        total_antibiotics = self._get_total_antibiotics()
        total_methods = ["MIC", "DISC"]
        total_decisions = ["S", "I", "R", "RR", "Requires Review"]
        
        coverage_metrics = {
            "organism_coverage": {
                "covered": len(self.organism_coverage),
                "total": len(total_organisms),
                "percentage": (len(self.organism_coverage) / len(total_organisms)) * 100,
                "covered_items": list(self.organism_coverage),
                "missing_items": list(set(total_organisms) - self.organism_coverage)
            },
            "antibiotic_coverage": {
                "covered": len(self.antibiotic_coverage),
                "total": len(total_antibiotics),
                "percentage": (len(self.antibiotic_coverage) / len(total_antibiotics)) * 100,
                "covered_items": list(self.antibiotic_coverage),
                "missing_items": list(set(total_antibiotics) - self.antibiotic_coverage)
            },
            "method_coverage": {
                "covered": len(self.method_coverage),
                "total": len(total_methods),
                "percentage": (len(self.method_coverage) / len(total_methods)) * 100,
                "covered_items": list(self.method_coverage)
            },
            "decision_coverage": {
                "covered": len(self.decision_coverage),
                "total": len(total_decisions),
                "percentage": (len(self.decision_coverage) / len(total_decisions)) * 100,
                "covered_items": list(self.decision_coverage)
            },
            "feature_coverage": {
                "covered": len(self.feature_coverage),
                "covered_items": list(self.feature_coverage)
            }
        }
        
        return coverage_metrics
    
    def _get_total_organisms(self) -> List[str]:
        """Get all organisms from the rule set."""
        organisms = set()
        if self.loader.ruleset:
            for rule in self.loader.ruleset.rules:
                organisms.add(rule.organism)
        
        # Add common organisms not necessarily in rules
        common_organisms = [
            "Escherichia coli",
            "Staphylococcus aureus", 
            "Klebsiella pneumoniae",
            "Pseudomonas aeruginosa",
            "Enterococcus faecalis",
            "Streptococcus pneumoniae"
        ]
        organisms.update(common_organisms)
        return list(organisms)
    
    def _get_total_antibiotics(self) -> List[str]:
        """Get all antibiotics from the rule set."""
        antibiotics = set()
        if self.loader.ruleset:
            for rule in self.loader.ruleset.rules:
                antibiotics.add(rule.antibiotic)
        
        # Add common antibiotics
        common_antibiotics = [
            "Penicillin", "Amoxicillin", "Ampicillin",
            "Ciprofloxacin", "Gentamicin", "Vancomycin",
            "Ceftriaxone", "Meropenem", "Piperacillin"
        ]
        antibiotics.update(common_antibiotics)
        return list(antibiotics)
    
    def assert_minimum_coverage(self, coverage_metrics: Dict[str, Any]):
        """Assert that minimum coverage requirements are met."""
        organism_pct = coverage_metrics["organism_coverage"]["percentage"]
        antibiotic_pct = coverage_metrics["antibiotic_coverage"]["percentage"] 
        method_pct = coverage_metrics["method_coverage"]["percentage"]
        decision_pct = coverage_metrics["decision_coverage"]["percentage"]
        
        assert organism_pct >= self.min_coverage_percent, \
            f"Organism coverage {organism_pct:.1f}% below minimum {self.min_coverage_percent}%"
        
        assert antibiotic_pct >= self.min_coverage_percent, \
            f"Antibiotic coverage {antibiotic_pct:.1f}% below minimum {self.min_coverage_percent}%"
        
        assert method_pct >= self.min_coverage_percent, \
            f"Method coverage {method_pct:.1f}% below minimum {self.min_coverage_percent}%"
        
        assert decision_pct >= self.min_coverage_percent, \
            f"Decision coverage {decision_pct:.1f}% below minimum {self.min_coverage_percent}%"


@pytest.fixture
def golden_tester():
    """Create golden dataset tester."""
    return GoldenDatasetTester()


def test_golden_dataset_comprehensive_coverage(golden_tester):
    """Test golden dataset with comprehensive coverage enforcement."""
    results = golden_tester.run_golden_dataset_tests()
    
    # Assert all tests pass
    assert results["failed_tests"] == 0, \
        f"Golden dataset tests failed: {results['failures']}"
    
    # Assert minimum coverage requirements
    golden_tester.assert_minimum_coverage(results["coverage_metrics"])
    
    print(f"\nGolden Dataset Results:")
    print(f"Total tests: {results['total_tests']}")
    print(f"Passed: {results['passed_tests']}")
    print(f"Failed: {results['failed_tests']}")
    
    coverage = results["coverage_metrics"]
    print(f"\nCoverage Metrics:")
    print(f"Organisms: {coverage['organism_coverage']['percentage']:.1f}%")
    print(f"Antibiotics: {coverage['antibiotic_coverage']['percentage']:.1f}%")
    print(f"Methods: {coverage['method_coverage']['percentage']:.1f}%")
    print(f"Decisions: {coverage['decision_coverage']['percentage']:.1f}%")


def test_golden_dataset_individual_cases(golden_tester):
    """Test each golden dataset case individually for better debugging."""
    for i, test_case in enumerate(golden_tester.golden_dataset):
        input_data = ClassificationInput(**test_case["input"])
        result = golden_tester.classifier.classify(input_data)
        
        expected = test_case["expected"]
        
        # Check decision
        if isinstance(expected["decision"], list):
            assert result.decision in expected["decision"], \
                f"Test {i}: Expected decision in {expected['decision']}, got {result.decision}"
        else:
            assert result.decision == expected["decision"], \
                f"Test {i}: Expected decision {expected['decision']}, got {result.decision}"
        
        # Check organism and antibiotic
        assert result.organism == expected["organism"], \
            f"Test {i}: Organism mismatch"
        assert result.antibiotic == expected["antibiotic"], \
            f"Test {i}: Antibiotic mismatch"