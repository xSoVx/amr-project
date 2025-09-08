from __future__ import annotations

import json
import logging
import os
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jsonschema import Draft202012Validator

from ..config import get_settings
from .exceptions import RulesValidationError

logger = logging.getLogger(__name__)


class Rule:
    def __init__(self, raw: Dict[str, Any], version: Optional[str]) -> None:
        self.raw = raw
        self.version = version or raw.get("version")
        self.organism_name = raw.get("organism", {}).get("name")
        self.organism_snomed = raw.get("organism", {}).get("snomed")
        ab = raw.get("antibiotic", {})
        self.antibiotic_name = ab.get("name")
        self.antibiotic_atc = ab.get("atc")
        self.method = raw.get("method")
        self.mic = raw.get("mic")
        self.disc = raw.get("disc")
        self.exceptions = raw.get("exceptions", [])


class Ruleset:
    def __init__(self, rules: List[Rule], version: Optional[str], sources: List[str]) -> None:
        self.rules = rules
        self.version = version
        self.sources = sources

    def find(self, organism: Optional[str], antibiotic: Optional[str], method: Optional[str]) -> Optional[Rule]:
        if not (organism and antibiotic and method):
            return None
        o_norm = organism.lower()
        a_norm = antibiotic.lower()
        for r in self.rules:
            if r.method != method:
                continue
            if r.organism_name and r.organism_name.lower() == o_norm and r.antibiotic_name and r.antibiotic_name.lower() == a_norm:
                return r
        return None


class RulesLoader:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._schema: Dict[str, Any] = {}
        self._validator: Optional[Draft202012Validator] = None
        self.ruleset: Optional[Ruleset] = None

        # Register SIGHUP handler only on Unix systems
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, self._on_sighup)

    def _on_sighup(self, signum: int, frame: Any) -> None:  # pragma: no cover (signal path)
        logger.info("SIGHUP received: reloading rules")
        self.load()

    def load_schema(self, schema_path: Path) -> None:
        with schema_path.open("r", encoding="utf-8") as f:
            self._schema = json.load(f)
        self._validator = Draft202012Validator(self._schema)

    def _validate(self, data: Dict[str, Any], source: str) -> None:
        assert self._validator is not None
        errors = sorted(self._validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            msgs = [f"{list(e.path)}: {e.message}" for e in errors]
            raise RulesValidationError(f"Rule validation failed for {source}: {'; '.join(msgs)}")

    def load(self) -> Ruleset:
        schema_path = Path(__file__).parent.parent / "rules" / "schema.json"
        if not self._schema:
            self.load_schema(schema_path)

        files = self.settings.rules_paths()
        rules: List[Rule] = []
        sources: List[str] = []
        for p in files:
            if not p.exists():
                raise RulesValidationError(f"Rules file not found: {p}")
            with p.open("r", encoding="utf-8") as f:
                if p.suffix.lower() in (".yaml", ".yml"):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            self._validate(data, str(p))
            version = data.get("version") or self.settings.EUST_VER
            for item in data.get("rules", []):
                rules.append(Rule(item, version))
            sources.append(str(p))
        self.ruleset = Ruleset(rules, self.settings.EUST_VER, sources)
        logger.info("Rules loaded", extra={"sources": sources, "count": len(rules)})
        return self.ruleset

