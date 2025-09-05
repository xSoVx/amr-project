from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set
from .schemas import ClassificationInput, Decision

logger = logging.getLogger(__name__)


class ExpertRule:
    """Expert rule for AMR interpretation overrides."""
    
    def __init__(
        self,
        rule_id: str,
        name: str,
        organism_patterns: List[str],
        antibiotic_patterns: List[str],
        conditions: Dict[str, Any],
        action: str,
        priority: int = 100,
        note: Optional[str] = None
    ):
        self.rule_id = rule_id
        self.name = name
        self.organism_patterns = [p.lower() for p in organism_patterns]
        self.antibiotic_patterns = [p.lower() for p in antibiotic_patterns]
        self.conditions = conditions
        self.action = action
        self.priority = priority
        self.note = note or ""
    
    def matches_organism(self, organism: Optional[str]) -> bool:
        """Check if organism matches rule patterns."""
        if not organism:
            return False
        
        organism_lower = organism.lower()
        return any(pattern in organism_lower for pattern in self.organism_patterns)
    
    def matches_antibiotic(self, antibiotic: Optional[str]) -> bool:
        """Check if antibiotic matches rule patterns."""
        if not antibiotic:
            return False
        
        antibiotic_lower = antibiotic.lower()
        return any(pattern in antibiotic_lower for pattern in self.antibiotic_patterns)
    
    def evaluate_conditions(self, item: ClassificationInput) -> bool:
        """Evaluate rule conditions against classification input."""
        for condition, expected_value in self.conditions.items():
            if condition == "features.esbl":
                if item.features.get("esbl") != expected_value:
                    return False
            elif condition == "features.mrsa":
                if item.features.get("mrsa") != expected_value:
                    return False
            elif condition == "features.carbapenemase":
                if item.features.get("carbapenemase") != expected_value:
                    return False
            elif condition == "features.vre":
                if item.features.get("vre") != expected_value:
                    return False
            elif condition == "method":
                if item.method != expected_value:
                    return False
            elif condition.startswith("mic_range"):
                if item.mic_mg_L is None:
                    return False
                min_val, max_val = expected_value
                if not (min_val <= item.mic_mg_L <= max_val):
                    return False
            elif condition.startswith("disc_range"):
                if item.disc_zone_mm is None:
                    return False
                min_val, max_val = expected_value
                if not (min_val <= item.disc_zone_mm <= max_val):
                    return False
        
        return True
    
    def applies_to(self, item: ClassificationInput) -> bool:
        """Check if rule applies to the given classification input."""
        return (
            self.matches_organism(item.organism) and
            self.matches_antibiotic(item.antibiotic) and
            self.evaluate_conditions(item)
        )


class ExpertRuleEngine:
    """Engine for applying expert rules and overrides."""
    
    def __init__(self):
        self.rules: List[ExpertRule] = []
        self._load_default_rules()
    
    def _load_default_rules(self):
        """Load default expert rules for common AMR scenarios."""
        
        # ESBL Rules - Override beta-lactams for ESBL producers
        esbl_beta_lactams = [
            "ceftriaxone", "ceftazidime", "cefotaxime", "cefpodoxime",
            "aztreonam", "ampicillin", "amoxicillin"
        ]
        
        for antibiotic in esbl_beta_lactams:
            self.rules.append(ExpertRule(
                rule_id=f"ESBL_OVERRIDE_{antibiotic.upper()}",
                name=f"ESBL Override for {antibiotic.title()}",
                organism_patterns=["escherichia", "klebsiella", "enterobacter", "citrobacter", "proteus"],
                antibiotic_patterns=[antibiotic],
                conditions={"features.esbl": True},
                action="R",
                priority=90,
                note=f"ESBL producer - {antibiotic} reported as Resistant regardless of MIC"
            ))
        
        # MRSA Rules - Override beta-lactams for MRSA
        mrsa_beta_lactams = [
            "oxacillin", "methicillin", "nafcillin", "cloxacillin",
            "ampicillin", "amoxicillin", "piperacillin", "ceftriaxone",
            "ceftazidime", "cefazolin", "cefepime"
        ]
        
        for antibiotic in mrsa_beta_lactams:
            self.rules.append(ExpertRule(
                rule_id=f"MRSA_OVERRIDE_{antibiotic.upper()}",
                name=f"MRSA Override for {antibiotic.title()}",
                organism_patterns=["staphylococcus aureus"],
                antibiotic_patterns=[antibiotic],
                conditions={"features.mrsa": True},
                action="R",
                priority=90,
                note=f"MRSA - {antibiotic} reported as Resistant"
            ))
        
        # Carbapenemase Rules - Override carbapenems
        carbapenem_antibiotics = ["meropenem", "imipenem", "ertapenem", "doripenem"]
        
        for antibiotic in carbapenem_antibiotics:
            self.rules.append(ExpertRule(
                rule_id=f"CARBAPENEMASE_OVERRIDE_{antibiotic.upper()}",
                name=f"Carbapenemase Override for {antibiotic.title()}",
                organism_patterns=["escherichia", "klebsiella", "enterobacter", "acinetobacter", "pseudomonas"],
                antibiotic_patterns=[antibiotic],
                conditions={"features.carbapenemase": True},
                action="R",
                priority=95,
                note=f"Carbapenemase producer - {antibiotic} reported as Resistant"
            ))
        
        # VRE Rules - Override vancomycin for VRE
        self.rules.append(ExpertRule(
            rule_id="VRE_VANCOMYCIN",
            name="VRE Vancomycin Override",
            organism_patterns=["enterococcus"],
            antibiotic_patterns=["vancomycin", "teicoplanin"],
            conditions={"features.vre": True},
            action="R",
            priority=95,
            note="VRE - Vancomycin/Teicoplanin reported as Resistant"
        ))
        
        # Intrinsic Resistance Rules
        
        # Pseudomonas aeruginosa intrinsic resistance
        pseudomonas_intrinsic = [
            "ceftriaxone", "cefazolin", "cefoxitin", "ertapenem",
            "ampicillin", "amoxicillin", "trimethoprim-sulfamethoxazole",
            "nitrofurantoin", "tigecycline"
        ]
        
        for antibiotic in pseudomonas_intrinsic:
            self.rules.append(ExpertRule(
                rule_id=f"INTRINSIC_PSEUDOMONAS_{antibiotic.upper().replace('-', '_')}",
                name=f"Pseudomonas Intrinsic Resistance to {antibiotic.title()}",
                organism_patterns=["pseudomonas aeruginosa"],
                antibiotic_patterns=[antibiotic],
                conditions={},
                action="R",
                priority=100,
                note=f"Intrinsic resistance - P. aeruginosa naturally resistant to {antibiotic}"
            ))
        
        # Enterococcus intrinsic resistance
        enterococcus_intrinsic = [
            "ceftriaxone", "ceftazidime", "cefazolin", "cefepime",
            "clindamycin", "trimethoprim-sulfamethoxazole"
        ]
        
        for antibiotic in enterococcus_intrinsic:
            self.rules.append(ExpertRule(
                rule_id=f"INTRINSIC_ENTEROCOCCUS_{antibiotic.upper().replace('-', '_')}",
                name=f"Enterococcus Intrinsic Resistance to {antibiotic.title()}",
                organism_patterns=["enterococcus"],
                antibiotic_patterns=[antibiotic],
                conditions={},
                action="R",
                priority=100,
                note=f"Intrinsic resistance - Enterococcus naturally resistant to {antibiotic}"
            ))
        
        # Acinetobacter intrinsic resistance
        acinetobacter_intrinsic = [
            "ampicillin", "amoxicillin", "ceftriaxone", "ertapenem",
            "nitrofurantoin", "fosfomycin"
        ]
        
        for antibiotic in acinetobacter_intrinsic:
            self.rules.append(ExpertRule(
                rule_id=f"INTRINSIC_ACINETOBACTER_{antibiotic.upper()}",
                name=f"Acinetobacter Intrinsic Resistance to {antibiotic.title()}",
                organism_patterns=["acinetobacter"],
                antibiotic_patterns=[antibiotic],
                conditions={},
                action="R",
                priority=100,
                note=f"Intrinsic resistance - Acinetobacter naturally resistant to {antibiotic}"
            ))
        
        # Special interpretive rules
        
        # Cefoxitin screen for MRSA detection
        self.rules.append(ExpertRule(
            rule_id="CEFOXITIN_MRSA_SCREEN",
            name="Cefoxitin MRSA Screen",
            organism_patterns=["staphylococcus aureus"],
            antibiotic_patterns=["cefoxitin"],
            conditions={"method": "DISC", "disc_range": [0, 21]},  # Zone ≤ 21mm suggests MRSA
            action="RR",
            priority=80,
            note="Cefoxitin zone ≤ 21mm - suggests MRSA, confirm with additional testing"
        ))
        
        # D-test for inducible clindamycin resistance
        self.rules.append(ExpertRule(
            rule_id="D_TEST_CLINDAMYCIN",
            name="Inducible Clindamycin Resistance",
            organism_patterns=["staphylococcus"],
            antibiotic_patterns=["clindamycin"],
            conditions={"features.d_test_positive": True},
            action="R",
            priority=85,
            note="D-test positive - inducible clindamycin resistance"
        ))
        
        # Sort rules by priority (higher priority = lower number = applied first)
        self.rules.sort(key=lambda r: r.priority)
    
    def add_rule(self, rule: ExpertRule):
        """Add a custom expert rule."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)
    
    def apply_rules(self, item: ClassificationInput, baseline_decision: Decision) -> tuple[Decision, List[str]]:
        """Apply expert rules and return final decision with rationale."""
        applied_rules = []
        final_decision = baseline_decision
        
        for rule in self.rules:
            if rule.applies_to(item):
                if rule.action in ["S", "I", "R", "RR"]:
                    final_decision = rule.action  # type: ignore
                    applied_rules.append(f"{rule.rule_id}: {rule.note}")
                    logger.info(f"Applied expert rule {rule.rule_id} to {item.organism}/{item.antibiotic}")
                    break  # Apply only the first matching rule (highest priority)
        
        return final_decision, applied_rules
    
    def get_applicable_rules(self, item: ClassificationInput) -> List[ExpertRule]:
        """Get all rules that apply to the given input."""
        return [rule for rule in self.rules if rule.applies_to(item)]
    
    def validate_features_for_rules(self, item: ClassificationInput) -> List[str]:
        """Validate that required features are present for rule evaluation."""
        warnings = []
        
        organism_lower = item.organism.lower() if item.organism else ""
        antibiotic_lower = item.antibiotic.lower() if item.antibiotic else ""
        
        # Check for ESBL-related organisms
        if any(org in organism_lower for org in ["escherichia", "klebsiella", "enterobacter"]):
            if "esbl" not in item.features:
                warnings.append("ESBL status not reported for Enterobacterales - may affect interpretation")
        
        # Check for S. aureus MRSA screening
        if "staphylococcus aureus" in organism_lower:
            if "mrsa" not in item.features and "cefoxitin" not in antibiotic_lower:
                warnings.append("MRSA status not reported for S. aureus - may affect beta-lactam interpretation")
        
        # Check for Enterococcus VRE screening
        if "enterococcus" in organism_lower and "vancomycin" in antibiotic_lower:
            if "vre" not in item.features:
                warnings.append("VRE status not reported for Enterococcus vs Vancomycin")
        
        # Check for carbapenemase screening
        carbapenems = ["meropenem", "imipenem", "ertapenem", "doripenem"]
        if any(carb in antibiotic_lower for carb in carbapenems):
            if "carbapenemase" not in item.features:
                warnings.append("Carbapenemase status not reported - may affect carbapenem interpretation")
        
        return warnings


# Global expert rule engine
expert_rule_engine = ExpertRuleEngine()