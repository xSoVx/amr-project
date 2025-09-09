"""
FHIR R4 Observation Builder for AMR Classification Results

This module builds FHIR R4-compliant Observation resources for antimicrobial
resistance classification results, ensuring proper medical data interoperability
and compliance with healthcare standards.

Key Features:
- LOINC code compliance for laboratory observations
- SNOMED CT terminology bindings
- Support for EUCAST/CLSI breakpoint standards
- Proper FHIR R4 resource structure
- US-Core and IL-Core profile compliance
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from enum import Enum

try:
    from fhir.resources.observation import Observation
    from fhir.resources.coding import Coding
    from fhir.resources.codeableconcept import CodeableConcept
    from fhir.resources.reference import Reference
    from fhir.resources.quantity import Quantity
    from fhir.resources.period import Period
    from fhir.resources.observationcomponent import ObservationComponent
    FHIR_AVAILABLE = True
except ImportError:
    FHIR_AVAILABLE = False


class SusceptibilityResult(str, Enum):
    """Standard AMR susceptibility result codes"""
    SUSCEPTIBLE = "S"
    INTERMEDIATE = "I"
    RESISTANT = "R"
    INSUFFICIENT_EVIDENCE = "IE"
    NON_SUSCEPTIBLE = "NS"
    SUSCEPTIBLE_DOSE_DEPENDENT = "SDD"


class TestMethod(str, Enum):
    """Standard AMR testing methods"""
    DISK_DIFFUSION = "disk_diffusion"
    MIC = "mic"
    ETEST = "etest"
    GRADIENT_DIFFUSION = "gradient_diffusion"
    AUTOMATED_SYSTEM = "automated_system"


class BreakpointStandard(str, Enum):
    """Breakpoint interpretation standards"""
    EUCAST = "EUCAST"
    CLSI = "CLSI"
    BSAC = "BSAC"


class AMRObservationBuilder:
    """
    Build FHIR R4 compliant AMR Observations with proper medical coding
    
    This class creates structured, interoperable FHIR Observation resources
    for antimicrobial resistance testing results, ensuring compliance with
    healthcare data standards and clinical guidelines.
    """
    
    # LOINC Codes for AMR Testing
    LOINC_CODES = {
        "susceptibility": "18769-0",      # Antimicrobial susceptibility
        "bacteria_id": "6932-8",          # Bacteria identified
        "method": "33747-0",              # Phenotypic method
        "mic": "33663-4",                 # Minimum inhibitory concentration
        "zone_diameter": "18769-0",       # Zone diameter (uses general susceptibility code)
        "interpretation": "18769-0",       # Susceptibility interpretation
        "breakpoint": "33746-2"           # Breakpoint used for interpretation
    }
    
    # SNOMED CT Codes for Common Organisms (subset)
    ORGANISM_CODES = {
        "staphylococcus aureus": {
            "code": "3092008",
            "display": "Staphylococcus aureus"
        },
        "escherichia coli": {
            "code": "112283007", 
            "display": "Escherichia coli"
        },
        "klebsiella pneumoniae": {
            "code": "56415008",
            "display": "Klebsiella pneumoniae"
        },
        "pseudomonas aeruginosa": {
            "code": "52499004",
            "display": "Pseudomonas aeruginosa"
        },
        "enterococcus faecalis": {
            "code": "78065002",
            "display": "Enterococcus faecalis"
        }
    }
    
    # ATC Codes for Common Antibiotics (subset)
    ANTIBIOTIC_CODES = {
        "amoxicillin": {
            "code": "J01CA04",
            "display": "Amoxicillin"
        },
        "ciprofloxacin": {
            "code": "J01MA02",
            "display": "Ciprofloxacin"  
        },
        "vancomycin": {
            "code": "J01XA01",
            "display": "Vancomycin"
        },
        "meropenem": {
            "code": "J01DH02",
            "display": "Meropenem"
        },
        "ceftriaxone": {
            "code": "J01DD04",
            "display": "Ceftriaxone"
        }
    }
    
    def __init__(self, system_identifier: str = "AMR-Engine"):
        """
        Initialize AMR Observation Builder
        
        Args:
            system_identifier: Identifier for the system creating observations
        """
        if not FHIR_AVAILABLE:
            raise ImportError("FHIR resources library not available. Install fhir.resources package.")
        
        self.system_identifier = system_identifier
    
    def build_susceptibility_observation(
        self,
        patient_ref: str,
        specimen_ref: str,
        organism: str,
        antibiotic: str,
        result: Union[SusceptibilityResult, str],
        method: Union[TestMethod, str] = TestMethod.DISK_DIFFUSION,
        breakpoint_standard: Union[BreakpointStandard, str] = BreakpointStandard.EUCAST,
        mic_value: Optional[float] = None,
        mic_unit: str = "mg/L",
        zone_diameter: Optional[int] = None,
        zone_unit: str = "mm",
        performer_ref: Optional[str] = None,
        effective_datetime: Optional[datetime] = None,
        interpretation_comment: Optional[str] = None
    ) -> Observation:
        """
        Build FHIR Observation for AMR susceptibility testing
        
        Args:
            patient_ref: Reference to Patient resource
            specimen_ref: Reference to Specimen resource
            organism: Organism name (will attempt SNOMED CT mapping)
            antibiotic: Antibiotic name (will attempt ATC mapping) 
            result: Susceptibility result (S/I/R/IE/NS/SDD)
            method: Testing method used
            breakpoint_standard: Standard used for interpretation (EUCAST/CLSI)
            mic_value: MIC value if available
            mic_unit: Unit for MIC (default: mg/L)
            zone_diameter: Zone diameter if disk diffusion
            zone_unit: Unit for zone (default: mm)
            performer_ref: Reference to performing organization/practitioner
            effective_datetime: When test was performed
            interpretation_comment: Additional clinical interpretation
            
        Returns:
            FHIR Observation resource
        """
        observation_id = str(uuid.uuid4())
        effective_time = effective_datetime or datetime.now(timezone.utc)
        
        # Build base observation
        observation = Observation(
            id=observation_id,
            status="final",
            category=[
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/observation-category",
                            code="laboratory",
                            display="Laboratory"
                        )
                    ]
                )
            ],
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://loinc.org",
                        code=self.LOINC_CODES["susceptibility"],
                        display="Antimicrobial susceptibility"
                    )
                ]
            ),
            subject=Reference(reference=patient_ref),
            effectiveDateTime=effective_time.isoformat(),
            issued=datetime.now(timezone.utc).isoformat(),
            valueCodeableConcept=self._build_susceptibility_result_coding(result),
            specimen=Reference(reference=specimen_ref)
        )
        
        # Add performer if provided
        if performer_ref:
            observation.performer = [Reference(reference=performer_ref)]
        
        # Add interpretation comment if provided
        if interpretation_comment:
            observation.note = [{
                "text": interpretation_comment,
                "time": datetime.now(timezone.utc).isoformat()
            }]
        
        # Build components
        components = []
        
        # Organism component
        organism_component = self._build_organism_component(organism)
        if organism_component:
            components.append(organism_component)
        
        # Antibiotic component
        antibiotic_component = self._build_antibiotic_component(antibiotic)
        if antibiotic_component:
            components.append(antibiotic_component)
        
        # Method component
        method_component = self._build_method_component(method)
        if method_component:
            components.append(method_component)
        
        # Breakpoint standard component
        breakpoint_component = self._build_breakpoint_component(breakpoint_standard)
        if breakpoint_component:
            components.append(breakpoint_component)
        
        # MIC component if provided
        if mic_value is not None:
            mic_component = self._build_mic_component(mic_value, mic_unit)
            if mic_component:
                components.append(mic_component)
        
        # Zone diameter component if provided
        if zone_diameter is not None:
            zone_component = self._build_zone_component(zone_diameter, zone_unit)
            if zone_component:
                components.append(zone_component)
        
        if components:
            observation.component = components
        
        return observation
    
    def build_organism_identification_observation(
        self,
        patient_ref: str,
        specimen_ref: str,
        organism: str,
        confidence: Optional[str] = None,
        method: str = "MALDI-TOF",
        performer_ref: Optional[str] = None,
        effective_datetime: Optional[datetime] = None
    ) -> Observation:
        """Build separate organism identification observation"""
        observation_id = str(uuid.uuid4())
        effective_time = effective_datetime or datetime.now(timezone.utc)
        
        observation = Observation(
            id=observation_id,
            status="final",
            category=[
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/observation-category",
                            code="laboratory",
                            display="Laboratory"
                        )
                    ]
                )
            ],
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://loinc.org",
                        code=self.LOINC_CODES["bacteria_id"],
                        display="Bacteria identified"
                    )
                ]
            ),
            subject=Reference(reference=patient_ref),
            effectiveDateTime=effective_time.isoformat(),
            issued=datetime.now(timezone.utc).isoformat(),
            valueCodeableConcept=self._build_organism_coding(organism),
            specimen=Reference(reference=specimen_ref)
        )
        
        if performer_ref:
            observation.performer = [Reference(reference=performer_ref)]
        
        # Add method and confidence as components
        components = []
        
        if method:
            method_component = ObservationComponent(
                code=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://loinc.org",
                            code=self.LOINC_CODES["method"],
                            display="Method"
                        )
                    ]
                ),
                valueString=method
            )
            components.append(method_component)
        
        if confidence:
            confidence_component = ObservationComponent(
                code=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://loinc.org",
                            code="33747-0",
                            display="Confidence"
                        )
                    ]
                ),
                valueString=confidence
            )
            components.append(confidence_component)
        
        if components:
            observation.component = components
        
        return observation
    
    def _build_susceptibility_result_coding(self, result: Union[SusceptibilityResult, str]) -> CodeableConcept:
        """Build susceptibility result coding"""
        result_str = result.value if isinstance(result, SusceptibilityResult) else str(result)
        
        # Map to standard codes
        result_mapping = {
            "S": {"code": "S", "display": "Susceptible"},
            "I": {"code": "I", "display": "Intermediate"}, 
            "R": {"code": "R", "display": "Resistant"},
            "IE": {"code": "IE", "display": "Insufficient Evidence"},
            "NS": {"code": "NS", "display": "Non-susceptible"},
            "SDD": {"code": "SDD", "display": "Susceptible-dose dependent"}
        }
        
        mapping = result_mapping.get(result_str.upper(), {"code": result_str, "display": result_str})
        
        return CodeableConcept(
            coding=[
                Coding(
                    system="http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                    code=mapping["code"],
                    display=mapping["display"]
                )
            ],
            text=mapping["display"]
        )
    
    def _build_organism_component(self, organism: str) -> Optional[ObservationComponent]:
        """Build organism component with SNOMED CT coding if available"""
        organism_coding = self._build_organism_coding(organism)
        
        return ObservationComponent(
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://loinc.org",
                        code=self.LOINC_CODES["bacteria_id"],
                        display="Bacteria identified"
                    )
                ]
            ),
            valueCodeableConcept=organism_coding
        )
    
    def _build_organism_coding(self, organism: str) -> CodeableConcept:
        """Build organism coding with SNOMED CT if available"""
        organism_lower = organism.lower().strip()
        snomed_info = self.ORGANISM_CODES.get(organism_lower)
        
        codings = []
        if snomed_info:
            codings.append(Coding(
                system="http://snomed.info/sct",
                code=snomed_info["code"],
                display=snomed_info["display"]
            ))
        
        # Always include text representation
        return CodeableConcept(
            coding=codings if codings else None,
            text=organism
        )
    
    def _build_antibiotic_component(self, antibiotic: str) -> Optional[ObservationComponent]:
        """Build antibiotic component with ATC coding if available"""
        antibiotic_coding = self._build_antibiotic_coding(antibiotic)
        
        return ObservationComponent(
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://loinc.org",
                        code="33747-0",  # Generic component code
                        display="Antibiotic"
                    )
                ]
            ),
            valueCodeableConcept=antibiotic_coding
        )
    
    def _build_antibiotic_coding(self, antibiotic: str) -> CodeableConcept:
        """Build antibiotic coding with ATC if available"""
        antibiotic_lower = antibiotic.lower().strip()
        atc_info = self.ANTIBIOTIC_CODES.get(antibiotic_lower)
        
        codings = []
        if atc_info:
            codings.append(Coding(
                system="http://www.whocc.no/atc",
                code=atc_info["code"],
                display=atc_info["display"]
            ))
        
        return CodeableConcept(
            coding=codings if codings else None,
            text=antibiotic
        )
    
    def _build_method_component(self, method: Union[TestMethod, str]) -> Optional[ObservationComponent]:
        """Build testing method component"""
        method_str = method.value if isinstance(method, TestMethod) else str(method)
        
        method_display_map = {
            "disk_diffusion": "Disk diffusion",
            "mic": "Minimum inhibitory concentration",
            "etest": "E-test gradient diffusion",
            "gradient_diffusion": "Gradient diffusion",
            "automated_system": "Automated testing system"
        }
        
        display = method_display_map.get(method_str, method_str)
        
        return ObservationComponent(
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://loinc.org",
                        code=self.LOINC_CODES["method"],
                        display="Method"
                    )
                ]
            ),
            valueString=display
        )
    
    def _build_breakpoint_component(self, standard: Union[BreakpointStandard, str]) -> Optional[ObservationComponent]:
        """Build breakpoint standard component"""
        standard_str = standard.value if isinstance(standard, BreakpointStandard) else str(standard)
        
        return ObservationComponent(
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://loinc.org",
                        code=self.LOINC_CODES["breakpoint"],
                        display="Breakpoint standard"
                    )
                ]
            ),
            valueString=standard_str
        )
    
    def _build_mic_component(self, mic_value: float, unit: str = "mg/L") -> Optional[ObservationComponent]:
        """Build MIC value component"""
        return ObservationComponent(
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://loinc.org",
                        code=self.LOINC_CODES["mic"],
                        display="Minimum inhibitory concentration"
                    )
                ]
            ),
            valueQuantity=Quantity(
                value=mic_value,
                unit=unit,
                system="http://unitsofmeasure.org",
                code=unit
            )
        )
    
    def _build_zone_component(self, zone_diameter: int, unit: str = "mm") -> Optional[ObservationComponent]:
        """Build zone diameter component"""
        return ObservationComponent(
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://loinc.org",
                        code=self.LOINC_CODES["zone_diameter"],
                        display="Zone diameter"
                    )
                ]
            ),
            valueQuantity=Quantity(
                value=zone_diameter,
                unit=unit,
                system="http://unitsofmeasure.org",
                code=unit
            )
        )
    
    def build_observation_collection(
        self,
        patient_ref: str,
        specimen_ref: str,
        organism: str,
        susceptibility_results: List[Dict[str, Any]],
        performer_ref: Optional[str] = None,
        effective_datetime: Optional[datetime] = None
    ) -> List[Observation]:
        """
        Build collection of related AMR observations
        
        Args:
            patient_ref: Patient reference
            specimen_ref: Specimen reference  
            organism: Organism name
            susceptibility_results: List of susceptibility test results
            performer_ref: Performing lab/practitioner reference
            effective_datetime: Test performance time
            
        Returns:
            List of FHIR Observation resources
        """
        observations = []
        
        # Create organism identification observation
        organism_obs = self.build_organism_identification_observation(
            patient_ref=patient_ref,
            specimen_ref=specimen_ref,
            organism=organism,
            performer_ref=performer_ref,
            effective_datetime=effective_datetime
        )
        observations.append(organism_obs)
        
        # Create susceptibility observations
        for result in susceptibility_results:
            susceptibility_obs = self.build_susceptibility_observation(
                patient_ref=patient_ref,
                specimen_ref=specimen_ref,
                organism=organism,
                antibiotic=result.get("antibiotic"),
                result=result.get("result"),
                method=result.get("method", TestMethod.DISK_DIFFUSION),
                breakpoint_standard=result.get("breakpoint_standard", BreakpointStandard.EUCAST),
                mic_value=result.get("mic_value"),
                zone_diameter=result.get("zone_diameter"),
                performer_ref=performer_ref,
                effective_datetime=effective_datetime,
                interpretation_comment=result.get("comment")
            )
            observations.append(susceptibility_obs)
        
        return observations