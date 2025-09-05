from __future__ import annotations

import logging
from typing import Dict, Optional, Any
from urllib.parse import urljoin
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TerminologyValidationResult(BaseModel):
    valid: bool
    display: Optional[str] = None
    system: Optional[str] = None
    code: Optional[str] = None
    error: Optional[str] = None


class SnomedConcept(BaseModel):
    code: str
    display: str
    system: str = "http://snomed.info/sct"
    active: bool = True


class TerminologyService:
    """SNOMED CT and other terminology validation service."""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url or "https://tx.fhir.org/r4"  # Default FHIR terminology server
        self.timeout = timeout
        self._cache: Dict[str, TerminologyValidationResult] = {}
    
    async def validate_code(
        self, 
        system: str, 
        code: str, 
        display: Optional[str] = None,
        use_cache: bool = True
    ) -> TerminologyValidationResult:
        """Validate a code against the terminology server using $validate-code operation."""
        cache_key = f"{system}|{code}|{display}"
        
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            params = {
                "url": system,
                "code": code,
                "coding": f"{system}|{code}"
            }
            if display:
                params["display"] = display
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    urljoin(self.base_url, "CodeSystem/$validate-code"),
                    params=params
                )
                
                if response.status_code == 200:
                    result_data = response.json()
                    parameter = result_data.get("parameter", [])
                    
                    # Extract result from Parameters resource
                    result = True
                    error_msg = None
                    validated_display = display
                    
                    for param in parameter:
                        if param.get("name") == "result":
                            result = param.get("valueBoolean", False)
                        elif param.get("name") == "message":
                            error_msg = param.get("valueString")
                        elif param.get("name") == "display":
                            validated_display = param.get("valueString")
                    
                    validation_result = TerminologyValidationResult(
                        valid=result,
                        display=validated_display,
                        system=system,
                        code=code,
                        error=error_msg
                    )
                else:
                    validation_result = TerminologyValidationResult(
                        valid=False,
                        system=system,
                        code=code,
                        error=f"Terminology server error: {response.status_code}"
                    )
        
        except Exception as e:
            logger.warning(f"Terminology validation failed for {system}|{code}: {e}")
            # Fallback for offline/testing scenarios
            validation_result = TerminologyValidationResult(
                valid=self._offline_validate_snomed(code, display) if system == "http://snomed.info/sct" else False,
                display=display,
                system=system,
                code=code,
                error=f"Offline validation: {str(e)}"
            )
        
        if use_cache:
            self._cache[cache_key] = validation_result
        
        return validation_result
    
    def _offline_validate_snomed(self, code: str, display: Optional[str] = None) -> bool:
        """Basic offline SNOMED CT validation for common organisms."""
        # Common organisms mapping for offline validation
        offline_concepts = {
            "112283007": "Escherichia coli",
            "3092008": "Staphylococcus aureus", 
            "9875009": "Pseudomonas aeruginosa",
            "40886007": "Klebsiella pneumoniae",
            "85729005": "Enterococcus faecium",
            "78006001": "Enterococcus faecalis",
            "5595000": "Acinetobacter baumannii",
            "115329001": "Methicillin resistant Staphylococcus aureus"
        }
        
        if code not in offline_concepts:
            return False
            
        if display and display.lower() not in offline_concepts[code].lower():
            return False
            
        return True
    
    async def lookup_concept(self, system: str, code: str) -> Optional[SnomedConcept]:
        """Lookup a concept and return its details."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    urljoin(self.base_url, "CodeSystem/$lookup"),
                    params={
                        "system": system,
                        "code": code
                    }
                )
                
                if response.status_code == 200:
                    result_data = response.json()
                    parameter = result_data.get("parameter", [])
                    
                    display = None
                    active = True
                    
                    for param in parameter:
                        if param.get("name") == "display":
                            display = param.get("valueString")
                        elif param.get("name") == "active":
                            active = param.get("valueBoolean", True)
                    
                    if display:
                        return SnomedConcept(
                            code=code,
                            display=display,
                            system=system,
                            active=active
                        )
        
        except Exception as e:
            logger.warning(f"Concept lookup failed for {system}|{code}: {e}")
        
        return None
    
    def normalize_organism_name(self, name: str) -> Optional[str]:
        """Normalize organism names to standard forms."""
        # Common normalization patterns
        normalizations = {
            "e. coli": "Escherichia coli",
            "e.coli": "Escherichia coli", 
            "s. aureus": "Staphylococcus aureus",
            "s.aureus": "Staphylococcus aureus",
            "p. aeruginosa": "Pseudomonas aeruginosa",
            "p.aeruginosa": "Pseudomonas aeruginosa",
            "k. pneumoniae": "Klebsiella pneumoniae",
            "k.pneumoniae": "Klebsiella pneumoniae"
        }
        
        normalized = name.lower().strip()
        return normalizations.get(normalized, name)


# Global terminology service instance
terminology_service = TerminologyService()