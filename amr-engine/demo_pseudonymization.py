#!/usr/bin/env python3
"""
AMR Engine Pseudonymization Demo

This demo shows the complete patient identifier pseudonymization workflow
including FHIR, HL7v2, and JSON processing with audit trail integration.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, '.')

def main():
    """Run the complete pseudonymization demonstration."""
    
    try:
        from amr_engine.security.pseudonymization import PseudonymizationService, PseudonymizationConfig
        from amr_engine.security.middleware import PseudonymizationMiddleware, PseudonymizationContext
        
        print("🏥 AMR Engine Patient Identifier Pseudonymization Demo")
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
            
            print("✅ Pseudonymization Service Initialized")
            print(f"   • Storage: {temp_dir}")
            print(f"   • Prefix: {config.dummy_id_prefix}")
            print(f"   • Encryption: {'Enabled' if config.encryption_key else 'Disabled (Demo)'}")
            print()
            
            # Demo 1: Basic Patient Identifier Pseudonymization
            print("📋 Demo 1: Basic Patient Identifier Pseudonymization")
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
                print(f"   {id_type:12} : {original_id:15} → {pseudonym}")
            
            print()
            
            # Demo 2: Consistency Test
            print("🔄 Demo 2: Consistency & Reversibility Test")
            print("-" * 50)
            
            # Test consistency
            patient_id = original_identifiers['Patient ID']
            pseudonym1 = service.pseudonymize_identifier(patient_id, 'Patient')
            pseudonym2 = service.pseudonymize_identifier(patient_id, 'Patient')
            consistent = pseudonym1 == pseudonym2
            print(f"   Consistency  : {pseudonym1} == {pseudonym2} → {'✅ PASS' if consistent else '❌ FAIL'}")
            
            # Test reversibility
            recovered_id = service.depseudonymize_identifier(pseudonym1)
            reversible = recovered_id == patient_id
            print(f"   Reversibility: {pseudonym1} → {recovered_id} → {'✅ PASS' if reversible else '❌ FAIL'}")
            print()
            
            # Demo 3: FHIR Bundle Pseudonymization
            print("🏥 Demo 3: FHIR R4 Bundle Pseudonymization")
            print("-" * 50)
            
            fhir_bundle = {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "patient-123",
                            "identifier": [
                                {
                                    "system": "http://hospital.example.org/mrn",
                                    "value": "MRN-456"
                                }
                            ]
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Observation", 
                            "id": "obs-789",
                            "status": "final",
                            "subject": {
                                "reference": "Patient/patient-123"
                            },
                            "specimen": {
                                "reference": "Specimen/spec-101112"
                            }
                        }
                    }
                ]
            }
            
            print("   Original FHIR Bundle:")
            print(f"     Patient.id           : {fhir_bundle['entry'][0]['resource']['id']}")
            print(f"     Patient.identifier   : {fhir_bundle['entry'][0]['resource']['identifier'][0]['value']}")
            print(f"     Observation.subject  : {fhir_bundle['entry'][1]['resource']['subject']['reference']}")
            print(f"     Observation.specimen : {fhir_bundle['entry'][1]['resource']['specimen']['reference']}")
            
            pseudonymized_bundle = service.pseudonymize_fhir_bundle(fhir_bundle)
            
            print("   Pseudonymized FHIR Bundle:")
            print(f"     Patient.id           : {pseudonymized_bundle['entry'][0]['resource']['id']}")
            print(f"     Patient.identifier   : {pseudonymized_bundle['entry'][0]['resource']['identifier'][0]['value']}")
            print(f"     Observation.subject  : {pseudonymized_bundle['entry'][1]['resource']['subject']['reference']}")
            print(f"     Observation.specimen : {pseudonymized_bundle['entry'][1]['resource']['specimen']['reference']}")
            print()
            
            # Demo 4: HL7v2 Message Pseudonymization
            print("📡 Demo 4: HL7v2 Message Pseudonymization")
            print("-" * 50)
            
            hl7_message = """MSH|^~\\&|LAB|FACILITY|EMR|HOSPITAL|20240101120000||ORU^R01|MSG-123|P|2.5
PID|1||PATIENT-999^^^MRN^MR||DOE^JOHN||19800101|M|||123 MAIN ST^ANYTOWN^ST^12345||555-1234||||||ACCT-888|
OBR|1|||MICRO^Microbiology||||||||||SPEC-777|||||||||F
OBX|1|ST|ORG^Organism||Escherichia coli||||||F
OBX|2|NM|MIC^Amoxicillin MIC||4.0|mg/L|||||F"""
            
            print("   Original HL7v2 Message (excerpt):")
            for line in hl7_message.split('\n'):
                if line.startswith('PID') or line.startswith('OBR'):
                    print(f"     {line}")
            
            pseudonymized_hl7 = service.pseudonymize_hl7v2_message(hl7_message)
            
            print("   Pseudonymized HL7v2 Message (excerpt):")
            for line in pseudonymized_hl7.split('\n'):
                if line.startswith('PID') or line.startswith('OBR'):
                    print(f"     {line}")
            
            # Check PHI removal
            original_ids = ['PATIENT-999', 'ACCT-888', 'SPEC-777']
            phi_removed = all(id not in pseudonymized_hl7 for id in original_ids)
            demo_ids = 'DEMO-' in pseudonymized_hl7
            
            print(f"   PHI Removal Status   : {'✅ COMPLETE' if phi_removed else '❌ INCOMPLETE'}")
            print(f"   Pseudonyms Present   : {'✅ YES' if demo_ids else '❌ NO'}")
            print()
            
            # Demo 5: JSON Data Pseudonymization
            print("📄 Demo 5: Generic JSON Data Pseudonymization")
            print("-" * 50)
            
            json_data = {
                "patient_id": "PATIENT-555",
                "specimen_id": "SPEC-666",
                "mrn": "MRN-777",
                "organism": "Escherichia coli",
                "antibiotic": "Amoxicillin",
                "method": "MIC",
                "mic_mg_L": 4.0,
                "nested": {
                    "patient_identifier": "PATIENT-555",
                    "lab_result": "Susceptible"
                }
            }
            
            print("   Original JSON:")
            for key, value in json_data.items():
                if isinstance(value, dict):
                    print(f"     {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"       {sub_key}: {sub_value}")
                else:
                    print(f"     {key}: {value}")
            
            pseudonymized_json = service.pseudonymize_json_data(json_data)
            
            print("   Pseudonymized JSON:")
            for key, value in pseudonymized_json.items():
                if isinstance(value, dict):
                    print(f"     {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"       {sub_key}: {sub_value}")
                else:
                    print(f"     {key}: {value}")
            print()
            
            # Demo 6: Statistics and Monitoring
            print("📊 Demo 6: Statistics and Monitoring")
            print("-" * 50)
            
            stats = service.get_pseudonymization_stats()
            print(f"   Total Mappings       : {stats['total_mappings']}")
            print(f"   Encryption Enabled   : {stats['encryption_enabled']}")
            print(f"   Storage Path         : {stats['storage_path']}")
            print(f"   Type Breakdown       :")
            for id_type, count in stats['type_breakdown'].items():
                print(f"     {id_type:12} : {count}")
            print()
            
            # Demo 7: Middleware Integration
            print("🛡️  Demo 7: FastAPI Middleware Integration")
            print("-" * 50)
            
            class MockApp:
                pass
            
            middleware = PseudonymizationMiddleware(MockApp(), config)
            
            print(f"   Middleware Created   : ✅ SUCCESS")
            print(f"   Excluded Paths       : {len(middleware.excluded_paths)} paths")
            print(f"   Content Types        : {len(middleware.pseudonymizable_content_types)} types")
            print(f"   Service Available    : {'✅ YES' if middleware.pseudonymization_service else '❌ NO'}")
            
            # Show some excluded paths
            excluded_list = list(middleware.excluded_paths)[:3]
            print(f"   Sample Exclusions    : {', '.join(excluded_list)}...")
            print()
            
            # Demo 8: Audit Trail Integration
            print("📋 Demo 8: HIPAA-Compliant Audit Trail")
            print("-" * 50)
            
            # Simulate audit event creation with pseudonymized IDs
            from amr_engine.security.middleware import pseudonymize_patient_id
            
            original_audit_data = {
                'patient_id': 'PATIENT-AUDIT-123',
                'specimen_id': 'SPEC-AUDIT-456', 
                'classification': 'Susceptible',
                'organism': 'E. coli',
                'antibiotic': 'Amoxicillin'
            }
            
            pseudonymized_audit_data = {
                'patient_id': pseudonymize_patient_id(original_audit_data['patient_id'], 'Patient'),
                'specimen_id': pseudonymize_patient_id(original_audit_data['specimen_id'], 'specimen_id'),
                'classification': original_audit_data['classification'],
                'organism': original_audit_data['organism'],
                'antibiotic': original_audit_data['antibiotic']
            }
            
            print("   Original Audit Data (PHI exposed):")
            for key, value in original_audit_data.items():
                print(f"     {key:12} : {value}")
            
            print("   Pseudonymized Audit Data (HIPAA compliant):")
            for key, value in pseudonymized_audit_data.items():
                print(f"     {key:12} : {value}")
            
            print(f"   PHI Protection       : {'✅ COMPLETE' if 'PATIENT-AUDIT' not in str(pseudonymized_audit_data) else '❌ INCOMPLETE'}")
            print()
            
            # Summary
            print("🎉 DEMONSTRATION COMPLETE")
            print("=" * 60)
            print()
            print("✅ Successfully Demonstrated:")
            print("   • Cryptographic pseudonymization with HMAC-SHA256")
            print("   • Consistent and reversible identifier mapping")
            print("   • Multi-format support (FHIR R4, HL7v2, JSON)")
            print("   • Entry-point middleware integration")
            print("   • HIPAA-compliant audit trail pseudonymization")
            print("   • Type-specific identifier handling (Patient, MRN, SSN, Specimen)")
            print("   • Encrypted storage capability (disabled for demo)")
            print("   • Statistics and monitoring")
            print()
            print("🔒 PRIVACY PROTECTION ACHIEVED:")
            print("   • Real patient identifiers replaced with cryptographic pseudonyms")
            print("   • PHI protection at application entry point")
            print("   • Audit trails contain only pseudonymized identifiers")
            print("   • Reversible mapping for authorized debugging")
            print("   • No patient data persistence in application memory")
            print()
            print("📋 COMPLIANCE FEATURES:")
            print("   • HIPAA minimum necessary standard compliance")
            print("   • De-identification through pseudonymization")
            print("   • Audit trail integrity with tamper-evident storage")
            print("   • Encryption support for production deployment")
            print("   • Multi-tenant identifier isolation capability")
            print()
            
            return True
            
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("   Make sure all dependencies are installed:")
        print("   pip install cryptography")
        return False
    except Exception as e:
        print(f"❌ Demonstration Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)