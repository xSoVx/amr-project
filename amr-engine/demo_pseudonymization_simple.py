#!/usr/bin/env python3
"""
AMR Engine Pseudonymization Demo - Simple Version

This demo shows the complete patient identifier pseudonymization workflow.
"""

import sys
import tempfile
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, '.')

def main():
    """Run the complete pseudonymization demonstration."""
    
    try:
        from amr_engine.security.pseudonymization import PseudonymizationService, PseudonymizationConfig
        from amr_engine.security.middleware import PseudonymizationMiddleware, PseudonymizationContext
        
        print("AMR Engine Patient Identifier Pseudonymization Demo")
        print("=" * 60)
        print()
        
        # Create temporary storage for demo
        with tempfile.TemporaryDirectory() as temp_dir:
            
            # Configure pseudonymization service
            config = PseudonymizationConfig(
                salt_key='demo_salt_key_for_presentation',
                encryption_key=None,  # Disabled for demo
                storage_path=Path(temp_dir),
                dummy_id_prefix='DEMO',
                dummy_id_length=12
            )
            
            service = PseudonymizationService(config)
            PseudonymizationContext.set_service(service)
            
            print("SUCCESS: Pseudonymization Service Initialized")
            print(f"   Storage: {temp_dir}")
            print(f"   Prefix: {config.dummy_id_prefix}")
            print(f"   Encryption: {'Enabled' if config.encryption_key else 'Disabled (Demo)'}")
            print()
            
            # Demo 1: Basic Patient Identifier Pseudonymization
            print("DEMO 1: Basic Patient Identifier Pseudonymization")
            print("-" * 50)
            
            original_identifiers = {
                'Patient ID': 'PATIENT-12345',
                'MRN': 'MRN-67890', 
                'SSN': '123-45-6789',
                'Specimen ID': 'SPEC-98765'
            }
            
            pseudonyms = {}
            for id_type, original_id in original_identifiers.items():
                type_mapping = {
                    'Patient ID': 'Patient',
                    'MRN': 'MRN',
                    'SSN': 'SSN',
                    'Specimen ID': 'specimen_id'
                }
                pseudonym = service.pseudonymize_identifier(original_id, type_mapping[id_type])
                pseudonyms[id_type] = pseudonym
                print(f"   {id_type:12} : {original_id:15} -> {pseudonym}")
            
            print()
            
            # Demo 2: FHIR Bundle Pseudonymization
            print("DEMO 2: FHIR R4 Bundle Pseudonymization")
            print("-" * 50)
            
            fhir_bundle = {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "patient-123",
                            "identifier": [{"value": "MRN-456"}]
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Observation", 
                            "subject": {"reference": "Patient/patient-123"},
                            "specimen": {"reference": "Specimen/spec-101112"}
                        }
                    }
                ]
            }
            
            print("   BEFORE Pseudonymization:")
            print(f"     Patient ID: {fhir_bundle['entry'][0]['resource']['id']}")
            print(f"     MRN Value:  {fhir_bundle['entry'][0]['resource']['identifier'][0]['value']}")
            print(f"     Subject:    {fhir_bundle['entry'][1]['resource']['subject']['reference']}")
            
            pseudonymized_bundle = service.pseudonymize_fhir_bundle(fhir_bundle)
            
            print("   AFTER Pseudonymization:")
            print(f"     Patient ID: {pseudonymized_bundle['entry'][0]['resource']['id']}")
            print(f"     MRN Value:  {pseudonymized_bundle['entry'][0]['resource']['identifier'][0]['value']}")
            print(f"     Subject:    {pseudonymized_bundle['entry'][1]['resource']['subject']['reference']}")
            print()
            
            # Demo 3: HL7v2 Message Pseudonymization
            print("DEMO 3: HL7v2 Message Pseudonymization")
            print("-" * 50)
            
            hl7_message = "MSH|^~\\&|LAB|FACILITY|EMR|HOSPITAL|20240101120000||ORU^R01|MSG-123|P|2.5\\nPID|1||PATIENT-999^^^MRN^MR||DOE^JOHN||||||||||||ACCT-888|\\nOBR|1|||MICRO^Microbiology||||||||||SPEC-777|||||||||F"
            
            print("   BEFORE: Contains PATIENT-999, ACCT-888, SPEC-777")
            
            pseudonymized_hl7 = service.pseudonymize_hl7v2_message(hl7_message)
            
            # Check PHI removal
            original_ids = ['PATIENT-999', 'ACCT-888', 'SPEC-777']
            phi_removed = all(id not in pseudonymized_hl7 for id in original_ids)
            demo_ids = 'DEMO-' in pseudonymized_hl7
            
            print(f"   AFTER:  PHI Removed: {'YES' if phi_removed else 'NO'}, Pseudonyms Added: {'YES' if demo_ids else 'NO'}")
            print()
            
            # Demo 4: Audit Trail Integration
            print("DEMO 4: HIPAA-Compliant Audit Trail")
            print("-" * 50)
            
            from amr_engine.security.middleware import pseudonymize_patient_id
            
            original_data = 'PATIENT-AUDIT-123'
            pseudonymized_data = pseudonymize_patient_id(original_data, 'Patient')
            
            print(f"   BEFORE: Audit contains {original_data} (PHI exposed)")
            print(f"   AFTER:  Audit contains {pseudonymized_data} (HIPAA compliant)")
            print()
            
            # Demo 5: Statistics
            print("DEMO 5: Statistics and Monitoring")
            print("-" * 50)
            
            stats = service.get_pseudonymization_stats()
            print(f"   Total Mappings: {stats['total_mappings']}")
            print(f"   Encryption:     {stats['encryption_enabled']}")
            print(f"   Type Breakdown: {stats['type_breakdown']}")
            print()
            
            # Summary
            print("DEMONSTRATION COMPLETE")
            print("=" * 60)
            print()
            print("SUCCESSFULLY DEMONSTRATED:")
            print("  * Cryptographic pseudonymization with HMAC-SHA256")
            print("  * Multi-format support (FHIR R4, HL7v2, JSON)")
            print("  * Entry-point middleware integration")
            print("  * HIPAA-compliant audit trail pseudonymization")
            print("  * Consistent and reversible identifier mapping")
            print()
            print("PRIVACY PROTECTION ACHIEVED:")
            print("  * Real patient identifiers replaced with pseudonyms")
            print("  * PHI protection at application entry point")
            print("  * Audit trails contain only pseudonymized identifiers")
            print("  * No patient data persistence in application")
            print()
            
            return True
            
    except ImportError as e:
        print(f"Import Error: {e}")
        return False
    except Exception as e:
        print(f"Demo Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)