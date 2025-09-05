from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .reasoning import disc_reason, mic_reason
from .rules_loader import Rule, RulesLoader
from .schemas import ClassificationInput, ClassificationResult

logger = logging.getLogger(__name__)


class Classifier:
    def __init__(self, loader: RulesLoader) -> None:
        self.loader = loader

    def classify(self, item: ClassificationInput) -> ClassificationResult:
        rule = None
        ruleset = self.loader.ruleset or self.loader.load()
        rule = ruleset.find(item.organism, item.antibiotic, item.method)
        # Missing rule
        if not rule:
            return ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision="RR",
                reason="No matching rule found",
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
            reason = mic_reason(val, s_max, i_rng if i_rng else None, r_min, rule.version or ruleset.version)
            return ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision=decision,
                reason=reason,
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
            reason = disc_reason(val, s_min, i_rng if i_rng else None, r_max, rule.version or ruleset.version)
            return ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision=decision,
                reason=reason,
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

