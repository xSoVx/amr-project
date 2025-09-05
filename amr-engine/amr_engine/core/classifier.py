from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .reasoning import disc_reason, mic_reason
from .rules_loader import Rule, RulesLoader
from .schemas import ClassificationInput, ClassificationResult
from .expert_rules import expert_rule_engine
from .tracing import get_tracer

logger = logging.getLogger(__name__)


class Classifier:
    def __init__(self, loader: RulesLoader) -> None:
        self.loader = loader

    @get_tracer().trace_classification()
    def classify(self, item: ClassificationInput) -> ClassificationResult:
        tracer = get_tracer()
        
        # Add trace attributes for classification parameters
        tracer.add_span_attributes(
            organism=item.organism or "unknown",
            antibiotic=item.antibiotic or "unknown", 
            method=item.method or "unknown",
            specimen_id=item.specimenId or "unknown"
        )
        
        # Validate features for expert rules
        feature_warnings = expert_rule_engine.validate_features_for_rules(item)
        
        rule = None
        ruleset = self.loader.ruleset or self.loader.load()
        
        # Trace rule lookup
        with tracer.trace_rule_evaluation("lookup", item.organism or "unknown", item.antibiotic or "unknown") as span:
            rule = ruleset.find(item.organism, item.antibiotic, item.method)
            span.set_attribute("rule_found", rule is not None)
        
        # Apply expert rules first (intrinsic resistance, etc.)
        with tracer.start_span("amr.expert_rules") as span:
            expert_decision, expert_rationale = expert_rule_engine.apply_rules(item, "RR")
            span.set_attribute("expert_decision", expert_decision)
            span.set_attribute("expert_applied", expert_decision != "RR")
        if expert_decision != "RR" and expert_rationale:
            # Expert rule override
            return ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision=expert_decision,
                reason=f"Expert rule: {'; '.join(expert_rationale)}",
                ruleVersion=ruleset.version,
            )
        
        # Missing rule
        if not rule:
            return ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision="RR",
                reason="No matching rule found" + (f"; Warnings: {'; '.join(feature_warnings)}" if feature_warnings else ""),
                ruleVersion=ruleset.version,
            )

        # Exceptions
        if self._hit_exception(rule, item):
            return ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision="RR",
                reason="Exception matched (requires review)",
                ruleVersion=rule.version or ruleset.version,
            )

        if rule.method == "MIC":
            if item.mic_mg_L is None:
                return ClassificationResult(
                    specimenId=item.specimenId,
                    organism=item.organism,
                    antibiotic=item.antibiotic,
                    method=item.method,
                    input=item.model_dump(exclude_none=True),
                    decision="RR",
                    reason="Missing MIC value",
                    ruleVersion=rule.version or ruleset.version,
                )
            s_max = rule.mic.get("susceptible_max") if rule.mic else None
            i_rng = tuple(rule.mic["intermediate_range"]) if rule.mic and rule.mic.get("intermediate_range") else None
            r_min = rule.mic.get("resistant_min") if rule.mic else None
            val = item.mic_mg_L
            if s_max is not None and val <= float(s_max):
                decision = "S"
            elif i_rng is not None and float(i_rng[0]) <= val <= float(i_rng[1]):
                decision = "I"
            elif r_min is not None and val >= float(r_min):
                decision = "R"
            else:
                decision = "RR"
            baseline_reason = mic_reason(val, s_max, i_rng if i_rng else None, r_min, rule.version or ruleset.version)
            
            # Apply expert rules to baseline decision
            final_decision, expert_rationale = expert_rule_engine.apply_rules(item, decision)
            
            final_reason = baseline_reason
            if expert_rationale:
                final_reason += f"; Expert override: {'; '.join(expert_rationale)}"
            if feature_warnings:
                final_reason += f"; Warnings: {'; '.join(feature_warnings)}"
            
            return ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision=final_decision,
                reason=final_reason,
                ruleVersion=rule.version or ruleset.version,
            )

        if rule.method == "DISC":
            if item.disc_zone_mm is None:
                return ClassificationResult(
                    specimenId=item.specimenId,
                    organism=item.organism,
                    antibiotic=item.antibiotic,
                    method=item.method,
                    input=item.model_dump(exclude_none=True),
                    decision="RR",
                    reason="Missing disc zone diameter",
                    ruleVersion=rule.version or ruleset.version,
                )
            s_min = rule.disc.get("susceptible_min_zone_mm") if rule.disc else None
            i_rng = tuple(rule.disc["intermediate_range_zone_mm"]) if rule.disc and rule.disc.get("intermediate_range_zone_mm") else None
            r_max = rule.disc.get("resistant_max_zone_mm") if rule.disc else None
            val = item.disc_zone_mm
            if s_min is not None and val >= float(s_min):
                decision = "S"
            elif i_rng is not None and float(i_rng[0]) <= val <= float(i_rng[1]):
                decision = "I"
            elif r_max is not None and val <= float(r_max):
                decision = "R"
            else:
                decision = "RR"
            baseline_reason = disc_reason(val, s_min, i_rng if i_rng else None, r_max, rule.version or ruleset.version)
            
            # Apply expert rules to baseline decision
            final_decision, expert_rationale = expert_rule_engine.apply_rules(item, decision)
            
            final_reason = baseline_reason
            if expert_rationale:
                final_reason += f"; Expert override: {'; '.join(expert_rationale)}"
            if feature_warnings:
                final_reason += f"; Warnings: {'; '.join(feature_warnings)}"
            
            return ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision=final_decision,
                reason=final_reason,
                ruleVersion=rule.version or ruleset.version,
            )

        return ClassificationResult(
            specimenId=item.specimenId,
            organism=item.organism,
            antibiotic=item.antibiotic,
            method=item.method,
            input=item.model_dump(exclude_none=True),
            decision="RR",
            reason="Unsupported method",
            ruleVersion=rule.version or ruleset.version,
        )

    def _hit_exception(self, rule: Rule, item: ClassificationInput) -> bool:
        # Simple DSL: when: "organism.features.esbl == true"
        for ex in rule.exceptions or []:
            cond = ex.get("when")
            action = ex.get("action")
            if not cond or action != "RR":
                continue
            # Check ESBL flag in features
            if "esbl" in item.features:
                if bool(item.features.get("esbl")) is True:
                    return True
        return False

