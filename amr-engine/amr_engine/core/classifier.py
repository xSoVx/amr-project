from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .reasoning import disc_reason, mic_reason
from .rules_loader import Rule, RulesLoader
from .schemas import ClassificationInput, ClassificationResult
from .expert_rules import expert_rule_engine
from ..cache.redis_cache import get_cache_manager
try:
    from .tracing import get_tracer
    HAS_TRACING = True
except ImportError:
    HAS_TRACING = False
    def get_tracer():
        class DummyTracer:
            def trace_classification(self):
                def decorator(func): return func
                return decorator
            def add_span_attributes(self, **kwargs): pass
            def start_span(self, *args, **kwargs): 
                from contextlib import contextmanager
                @contextmanager
                def dummy_span():
                    class DummySpan:
                        def set_attribute(self, key, value): pass
                        def add_event(self, event, attributes=None): pass
                    yield DummySpan()
                return dummy_span()
            def trace_rule_evaluation(self, *args, **kwargs):
                from contextlib import contextmanager
                @contextmanager
                def dummy_span():
                    class DummySpan:
                        def set_attribute(self, key, value): pass
                        def add_event(self, event, attributes=None): pass
                    yield DummySpan()
                return dummy_span()
        return DummyTracer()

logger = logging.getLogger(__name__)


class Classifier:
    def __init__(self, loader: RulesLoader, enable_cache: bool = True) -> None:
        self.loader = loader
        self.cache_manager = get_cache_manager() if enable_cache else None

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
        
        # Try cache first if enabled
        if self.cache_manager and self.cache_manager._enabled:
            cached_result = self._get_cached_classification(item)
            if cached_result:
                logger.debug(f"Cache hit for classification: {item.organism}/{item.antibiotic}")
                tracer.add_span_attributes(cache_hit=True)
                return cached_result
            tracer.add_span_attributes(cache_hit=False)
        
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
            
            result = ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision=final_decision,
                reason=final_reason,
                ruleVersion=rule.version or ruleset.version,
            )
            
            # Cache successful MIC classification
            self._cache_classification_result(item, result)
            return result

        if rule.method == "DISC":
            if item.disc_zone_mm is None:
                return ClassificationResult(
                    specimenId=item.specimenId,
                    organism=item.organism,
                    antibiotic=item.antibiotic,
                    method=item.method,
                    input=item.model_dump(exclude_none=True),
                    decision="Requires Review",
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
            
            result = ClassificationResult(
                specimenId=item.specimenId,
                organism=item.organism,
                antibiotic=item.antibiotic,
                method=item.method,
                input=item.model_dump(exclude_none=True),
                decision=final_decision,
                reason=final_reason,
                ruleVersion=rule.version or ruleset.version,
            )
            
            # Cache successful DISC classification
            self._cache_classification_result(item, result)
            return result

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

    def _get_cached_classification(self, item: ClassificationInput) -> Optional[ClassificationResult]:
        """Retrieve cached classification result if available"""
        if not self.cache_manager or not self.cache_manager._enabled:
            return None
            
        try:
            # Extract cache parameters
            organism = item.organism or ""
            antibiotic = item.antibiotic or ""
            method = item.method or ""
            
            # Get measurement value
            if method == 'MIC':
                value = item.mic_mg_L or 0
            elif method == 'DISC':
                value = item.disc_zone_mm or 0
            else:
                return None
                
            # Get rule version (fallback to default)
            ruleset = self.loader.ruleset or self.loader.load()
            rule_version = ruleset.version or "unknown"
            
            # Try cache lookup
            cached_result = self.cache_manager.cache.get_cached_classification(
                organism, antibiotic, method, value, rule_version
            )
            
            if cached_result:
                # Convert dict back to ClassificationResult
                return ClassificationResult(**cached_result)
                
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            
        return None

    def _cache_classification_result(self, item: ClassificationInput, result: ClassificationResult) -> None:
        """Store classification result in cache"""
        if not self.cache_manager or not self.cache_manager._enabled:
            return
            
        try:
            # Extract cache parameters
            organism = item.organism or ""
            antibiotic = item.antibiotic or ""
            method = item.method or ""
            
            # Get measurement value
            if method == 'MIC':
                value = item.mic_mg_L or 0
            elif method == 'DISC':
                value = item.disc_zone_mm or 0
            else:
                return
                
            rule_version = result.ruleVersion or "unknown"
            
            # Store in cache
            self.cache_manager.cache.cache_classification_result(
                organism, antibiotic, method, value, rule_version,
                result.model_dump(), ttl=3600  # 1 hour TTL
            )
            
        except Exception as e:
            logger.warning(f"Cache storage failed: {e}")

