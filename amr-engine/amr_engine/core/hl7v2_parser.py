from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from .exceptions import FHIRValidationError
from .schemas import ClassificationInput

logger = logging.getLogger(__name__)


class HL7v2Message:
    """HL7v2 message parser for AMR data."""
    
    def __init__(self, message: str):
        self.raw_message = message.strip()
        self.segments = self._parse_segments()
        self.message_type = self._get_message_type()
    
    def _parse_segments(self) -> List[Dict[str, Any]]:
        """Parse HL7v2 message into segments."""
        segments = []
        lines = self.raw_message.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Split segment into fields (using | as separator)
            fields = line.split('|')
            if not fields:
                continue
                
            segment_type = fields[0] if fields else ""
            
            segment = {
                'type': segment_type,
                'fields': fields,
                'raw': line
            }
            segments.append(segment)
        
        return segments
    
    def _get_message_type(self) -> Optional[str]:
        """Get message type from MSH segment."""
        for segment in self.segments:
            if segment['type'] == 'MSH':
                fields = segment['fields']
                if len(fields) > 8:
                    # MSH.9 is message type
                    return fields[8]
        return None
    
    def get_segments_by_type(self, segment_type: str) -> List[Dict[str, Any]]:
        """Get all segments of a specific type."""
        return [seg for seg in self.segments if seg['type'] == segment_type]
    
    def parse_field(self, field_value: str) -> List[str]:
        """Parse HL7v2 field with component separator ^."""
        if not field_value:
            return []
        return field_value.split('^')


class HL7v2ToFHIRConverter:
    """Convert HL7v2 messages to FHIR-compatible data for AMR processing."""
    
    def __init__(self):
        self.organism_mappings = {
            # Common organism code mappings
            'ECOLI': 'Escherichia coli',
            'SAUR': 'Staphylococcus aureus',
            'PAER': 'Pseudomonas aeruginosa',
            'KPNE': 'Klebsiella pneumoniae',
            'EFAE': 'Enterococcus faecalis',
            'EFAM': 'Enterococcus faecium'
        }
        
        self.antibiotic_mappings = {
            # Common antibiotic code mappings
            'CIP': 'Ciprofloxacin',
            'CRO': 'Ceftriaxone', 
            'CAZ': 'Ceftazidime',
            'OXA': 'Oxacillin',
            'PIP': 'Piperacillin',
            'MEM': 'Meropenem',
            'VAN': 'Vancomycin',
            'GEN': 'Gentamicin'
        }
    
    def convert_oru_message(self, message: HL7v2Message) -> List[ClassificationInput]:
        """Convert HL7v2 ORU (Observation Result) message to classification inputs."""
        if message.message_type != 'ORU^R01':
            raise FHIRValidationError(f"Unsupported HL7v2 message type: {message.message_type}")
        
        results: List[ClassificationInput] = []
        
        # Get PID (Patient) segment
        pid_segments = message.get_segments_by_type('PID')
        patient_id = None
        if pid_segments:
            pid_fields = pid_segments[0]['fields']
            if len(pid_fields) > 3:
                patient_id = pid_fields[3]  # PID.3 - Patient ID
        
        # Get SPM (Specimen) segments
        spm_segments = message.get_segments_by_type('SPM')
        specimen_id = None
        specimen_type = None
        if spm_segments:
            spm_fields = spm_segments[0]['fields']
            if len(spm_fields) > 2:
                specimen_id = spm_fields[2]  # SPM.2 - Specimen ID
            if len(spm_fields) > 4:
                specimen_type = spm_fields[4]  # SPM.4 - Specimen Type
        
        # Process OBX (Observation) segments
        obx_segments = message.get_segments_by_type('OBX')
        
        # Group OBX segments by organism
        organism_groups = self._group_obx_by_organism(obx_segments)
        
        for organism, obx_list in organism_groups.items():
            for obx in obx_list:
                classification_input = self._parse_obx_segment(
                    obx, patient_id, specimen_id, organism
                )
                if classification_input:
                    results.append(classification_input)
        
        return results
    
    def _group_obx_by_organism(self, obx_segments: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group OBX segments by organism."""
        organisms: Dict[str, List[Dict[str, Any]]] = {}
        current_organism = "Unknown"
        
        for obx in obx_segments:
            fields = obx['fields']
            if len(fields) < 4:
                continue
            
            # OBX.3 - Observation Identifier
            obs_id = fields[3] if len(fields) > 3 else ""
            # OBX.5 - Observation Value
            obs_value = fields[5] if len(fields) > 5 else ""
            
            # Check if this is an organism identification
            if self._is_organism_observation(obs_id):
                current_organism = self._parse_organism_value(obs_value)
                if current_organism not in organisms:
                    organisms[current_organism] = []
            
            # Check if this is a susceptibility observation
            elif self._is_susceptibility_observation(obs_id):
                if current_organism not in organisms:
                    organisms[current_organism] = []
                organisms[current_organism].append(obx)
        
        return organisms
    
    def _is_organism_observation(self, obs_id: str) -> bool:
        """Check if observation is organism identification."""
        organism_patterns = [
            r'.*ORGANISM.*',
            r'.*IDENTIFICATION.*',
            r'.*ISOLATE.*',
            r'.*CULTURE.*RESULT.*'
        ]
        
        for pattern in organism_patterns:
            if re.search(pattern, obs_id.upper()):
                return True
        return False
    
    def _is_susceptibility_observation(self, obs_id: str) -> bool:
        """Check if observation is susceptibility testing."""
        susceptibility_patterns = [
            r'.*SUSCEPTIBILITY.*',
            r'.*MIC.*',
            r'.*DISC.*',
            r'.*SENSITIVITY.*',
            r'.*ANTIBIOTIC.*'
        ]
        
        for pattern in susceptibility_patterns:
            if re.search(pattern, obs_id.upper()):
                return True
        return False
    
    def _parse_organism_value(self, value: str) -> str:
        """Parse organism name from HL7v2 value."""
        # Try to map coded values
        organism_code = value.split('^')[0] if '^' in value else value
        organism_name = self.organism_mappings.get(organism_code.upper(), organism_code)
        
        return organism_name
    
    def _parse_obx_segment(
        self, 
        obx: Dict[str, Any], 
        patient_id: Optional[str],
        specimen_id: Optional[str], 
        organism: str
    ) -> Optional[ClassificationInput]:
        """Parse individual OBX segment into ClassificationInput."""
        fields = obx['fields']
        
        if len(fields) < 6:
            return None
        
        # OBX.3 - Observation Identifier
        obs_id = fields[3]
        # OBX.5 - Observation Value
        obs_value = fields[5]
        # OBX.6 - Units
        units = fields[6] if len(fields) > 6 else ""
        # OBX.8 - Abnormal Flags
        abnormal_flags = fields[8] if len(fields) > 8 else ""
        
        # Parse antibiotic name
        antibiotic = self._extract_antibiotic_from_obs_id(obs_id)
        if not antibiotic:
            return None
        
        # Parse method and value
        method, numeric_value = self._parse_method_and_value(obs_value, units)
        
        # Extract features from abnormal flags
        features = self._parse_abnormal_flags(abnormal_flags)
        
        mic_value = numeric_value if method == "MIC" else None
        disc_value = numeric_value if method == "DISC" else None
        
        return ClassificationInput(
            organism=organism,
            antibiotic=antibiotic,
            method=method,
            mic_mg_L=mic_value,
            disc_zone_mm=disc_value,
            specimenId=specimen_id,
            patientId=patient_id,
            features=features
        )
    
    def _extract_antibiotic_from_obs_id(self, obs_id: str) -> Optional[str]:
        """Extract antibiotic name from observation identifier."""
        # Parse components separated by ^
        components = obs_id.split('^')
        
        # Try to find antibiotic in components
        for component in components:
            component_upper = component.upper()
            # Check if component matches known antibiotic codes
            if component_upper in self.antibiotic_mappings:
                return self.antibiotic_mappings[component_upper]
            
            # Check for common antibiotic name patterns
            for code, name in self.antibiotic_mappings.items():
                if code in component_upper or name.upper() in component_upper:
                    return name
        
        # Fallback: try to extract from full string
        obs_upper = obs_id.upper()
        for code, name in self.antibiotic_mappings.items():
            if code in obs_upper or name.upper() in obs_upper:
                return name
        
        return None
    
    def _parse_method_and_value(self, obs_value: str, units: str) -> Tuple[Optional[str], Optional[float]]:
        """Parse method and numeric value from observation value and units."""
        method = None
        numeric_value = None
        
        # Clean value
        value_clean = obs_value.strip()
        
        # Try to extract numeric value
        numeric_match = re.search(r'([0-9]+\.?[0-9]*)', value_clean)
        if numeric_match:
            try:
                numeric_value = float(numeric_match.group(1))
            except ValueError:
                pass
        
        # Determine method from units or value format
        units_upper = units.upper()
        value_upper = value_clean.upper()
        
        if any(unit in units_upper for unit in ['MG/L', 'UG/ML', 'MCG/ML']):
            method = "MIC"
        elif 'MM' in units_upper:
            method = "DISC"
        elif any(pattern in value_upper for pattern in ['MIC', 'MINIMUM', 'INHIBITORY']):
            method = "MIC"
        elif any(pattern in value_upper for pattern in ['ZONE', 'DISC', 'DIAMETER']):
            method = "DISC"
        
        return method, numeric_value
    
    def _parse_abnormal_flags(self, abnormal_flags: str) -> Dict[str, Any]:
        """Parse abnormal flags into features."""
        features = {}
        
        if not abnormal_flags:
            return features
        
        flags_upper = abnormal_flags.upper()
        
        # Common resistance markers
        if 'ESBL' in flags_upper:
            features['esbl'] = True
        if 'MRSA' in flags_upper:
            features['mrsa'] = True
        if 'VRE' in flags_upper:
            features['vre'] = True
        if any(marker in flags_upper for marker in ['KPC', 'NDM', 'OXA']):
            features['carbapenemase'] = True
        
        return features


def parse_hl7v2_message(message_text: str) -> List[ClassificationInput]:
    """Main function to parse HL7v2 message and return classification inputs."""
    try:
        message = HL7v2Message(message_text)
        converter = HL7v2ToFHIRConverter()
        
        if message.message_type and message.message_type.startswith('ORU'):
            return converter.convert_oru_message(message)
        else:
            raise FHIRValidationError(f"Unsupported HL7v2 message type: {message.message_type}")
    
    except Exception as e:
        logger.error(f"Failed to parse HL7v2 message: {e}")
        raise FHIRValidationError(f"HL7v2 parsing error: {str(e)}")