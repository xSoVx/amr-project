# Patient Identifier Pseudonymization

## Overview

The AMR Engine implements comprehensive patient identifier pseudonymization to protect Protected Health Information (PHI) while maintaining data utility for antimicrobial resistance analysis. This system replaces real patient identifiers with cryptographically secure dummy identifiers at the application entry point, ensuring PHI protection throughout the entire processing pipeline.

## Features

### 🔒 **Cryptographic Security**
- **HMAC-SHA256** hashing with configurable salt
- **AES encryption** for bidirectional mapping storage
- **Consistent pseudonym generation** across requests
- **Tamper-resistant** identifier mapping

### 🛡️ **Comprehensive Coverage**
- **All Message Formats**: FHIR R4, HL7v2, JSON
- **Multiple ID Types**: Patient ID, MRN, SSN, Specimen ID
- **Middleware Integration**: Intercepts ALL requests at entry point
- **Pre-processing Protection**: Pseudonymization before external library processing

### 📊 **Audit Trail Integration**
- **Pseudonymized audit logs** only
- **HIPAA-compliant** audit events
- **Reversible mapping** for authorized debugging
- **Comprehensive tracking** of pseudonymization events

## Architecture

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Client        │    │  Pseudonymization    │    │   AMR Engine        │
│   Request       │───▶│     Middleware       │───▶│   Core Logic        │
│                 │    │                      │    │                     │
│ Real Patient    │    │ • FHIR Bundle        │    │ Pseudonymized       │
│ Identifiers     │    │ • HL7v2 Messages     │    │ Identifiers Only    │
│                 │    │ • JSON Data          │    │                     │
└─────────────────┘    └──────────────────────┘    └─────────────────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │ Encrypted Storage    │
                       │ • Bidirectional Map  │
                       │ • AES Encryption     │
                       │ • Persistent Cache   │
                       └──────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Enable/disable pseudonymization
PSEUDONYMIZATION_ENABLED=true

# Cryptographic salt (required for production)
PSEUDONYM_SALT_KEY=your-secure-salt-key-here

# Encryption key for mapping storage (optional)
PSEUDONYM_ENCRYPTION_KEY=your-encryption-key-here

# Storage configuration
PSEUDONYM_STORAGE_PATH=./pseudonym_storage
PSEUDONYM_DUMMY_ID_PREFIX=PSY
PSEUDONYM_DUMMY_ID_LENGTH=12
```

### Configuration Class

```python
from amr_engine.security.pseudonymization import PseudonymizationConfig

config = PseudonymizationConfig(
    salt_key="your-secure-salt",
    encryption_key="your-encryption-key",
    storage_path=Path("./pseudonym_storage"),
    dummy_id_prefix="PSY",
    dummy_id_length=12
)
```

## Usage

### Automatic Pseudonymization

The middleware automatically pseudonymizes all incoming requests:

```python
# FastAPI automatically applies pseudonymization
@app.post("/classify")
async def classify_data(request: Request, payload: Any):
    # payload already contains pseudonymized identifiers
    # Original patient IDs have been replaced with PSY-PT-XXXXXXXX format
    pass
```

### Manual Pseudonymization

```python
from amr_engine.security.middleware import pseudonymize_patient_id, depseudonymize_patient_id

# Pseudonymize an identifier
original_id = "PATIENT-12345"
pseudonym = pseudonymize_patient_id(original_id, "Patient")
# Returns: PSY-PT-A1B2C3D4

# Reverse pseudonymization (for authorized debugging)
recovered_id = depseudonymize_patient_id(pseudonym)
# Returns: PATIENT-12345
```

### Service Integration

```python
from amr_engine.security.pseudonymization import PseudonymizationService

service = PseudonymizationService(config)

# FHIR Bundle pseudonymization
pseudonymized_bundle = service.pseudonymize_fhir_bundle(fhir_bundle)

# HL7v2 message pseudonymization
pseudonymized_hl7 = service.pseudonymize_hl7v2_message(hl7_message)

# Generic JSON pseudonymization
pseudonymized_json = service.pseudonymize_json_data(json_data)
```

## Supported Identifier Types

| Type | Prefix | Examples |
|------|--------|----------|
| Patient ID | `PSY-PT-` | `PSY-PT-A1B2C3D4` |
| MRN | `PSY-MR-` | `PSY-MR-E5F6G7H8` |
| SSN | `PSY-SS-` | `PSY-SS-I9J0K1L2` |
| Specimen ID | `PSY-SP-` | `PSY-SP-M3N4O5P6` |
| Generic | `PSY-ID-` | `PSY-ID-Q7R8S9T0` |

## Message Format Support

### FHIR R4 Bundle

```json
{
  "resourceType": "Bundle",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "PSY-PT-A1B2C3D4",  // ← Pseudonymized
        "subject": {
          "reference": "Patient/PSY-PT-A1B2C3D4"  // ← Pseudonymized
        }
      }
    }
  ]
}
```

### HL7v2 Messages

```
MSH|^~\&|LAB|FACILITY|EMR|HOSPITAL|20240101120000||ORU^R01|12345|P|2.5
PID|1||PSY-PT-A1B2C3D4^^^MRN^MR||DOE^JOHN||19800101|M|  // ← Pseudonymized
OBR|1|||MICRO^Microbiology||||||||||PSY-SP-E5F6G7H8|    // ← Pseudonymized
```

### JSON Data

```json
{
  "patient_id": "PSY-PT-A1B2C3D4",    // ← Pseudonymized
  "specimen_id": "PSY-SP-E5F6G7H8",   // ← Pseudonymized
  "mrn": "PSY-MR-I9J0K1L2",           // ← Pseudonymized
  "organism": "E. coli",              // ← Unchanged
  "antibiotic": "Amoxicillin"         // ← Unchanged
}
```

## Audit Trail Integration

### Pseudonymized Audit Events

All audit events use pseudonymized identifiers:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_id": "PSY-PT-A1B2C3D4",     // ← Pseudonymized
  "specimen_id": "PSY-SP-E5F6G7H8",    // ← Pseudonymized
  "classification_result": "S",
  "pseudonymization_enabled": true,
  "original_identifiers_pseudonymized": true
}
```

### FHIR AuditEvent Resources

```json
{
  "resourceType": "AuditEvent",
  "entity": [
    {
      "what": {
        "identifier": {
          "value": "PSY-PT-A1B2C3D4"  // ← Pseudonymized
        }
      },
      "detail": [
        {
          "type": "pseudonymization_enabled",
          "valueString": "true"
        }
      ]
    }
  ]
}
```

## Security Features

### 1. **Entry Point Protection**
- Middleware intercepts ALL requests
- Pseudonymization occurs BEFORE external library processing
- Real patient data never reaches core application logic

### 2. **Cryptographic Strength**
- HMAC-SHA256 with configurable salt
- Consistent deterministic pseudonyms
- Cryptographically secure random generation

### 3. **Encrypted Storage**
- AES encryption for mapping files
- PBKDF2 key derivation from passwords
- Tamper-evident storage with file permissions

### 4. **Audit Compliance**
- All audit trails use pseudonymized identifiers only
- HIPAA-compliant audit events
- Reversible mapping for authorized access

## Testing

Run the pseudonymization tests:

```bash
# Run all pseudonymization tests
pytest tests/test_pseudonymization.py -v

# Run with coverage
pytest tests/test_pseudonymization.py --cov=amr_engine.security --cov-report=html
```

### Test Coverage

- ✅ Basic pseudonymization and depseudonymization
- ✅ Consistency across multiple calls
- ✅ Different identifier types
- ✅ FHIR bundle processing
- ✅ HL7v2 message processing
- ✅ Generic JSON data processing
- ✅ Mapping persistence and loading
- ✅ Error handling and edge cases

## Monitoring

### Pseudonymization Statistics

```python
from amr_engine.security.middleware import get_current_pseudonymization_service

service = get_current_pseudonymization_service()
stats = service.get_pseudonymization_stats()

print(stats)
# {
#   "total_mappings": 1250,
#   "type_breakdown": {
#     "Patient": 500,
#     "MRN": 400,
#     "specimen_id": 350
#   },
#   "encryption_enabled": true,
#   "storage_path": "./pseudonym_storage"
# }
```

### Middleware Statistics

```python
from amr_engine.main import app

# Get middleware instance (for admin endpoints)
for middleware in app.user_middleware:
    if hasattr(middleware, 'get_service_stats'):
        stats = middleware.get_service_stats()
        print(stats)
```

## Maintenance

### Clearing Old Mappings

```python
# Clear mappings older than 30 days
cleared_count = service.clear_mappings(older_than_days=30)
print(f"Cleared {cleared_count} old mappings")

# Clear all mappings (use with caution)
cleared_count = service.clear_mappings()
```

### Backup and Recovery

```bash
# Backup pseudonymization mappings
tar -czf pseudonym_backup_$(date +%Y%m%d).tar.gz ./pseudonym_storage/

# Restore pseudonymization mappings
tar -xzf pseudonym_backup_20241201.tar.gz
```

## Production Deployment

### Required Configuration

1. **Set secure salt key**:
   ```bash
   export PSEUDONYM_SALT_KEY=$(openssl rand -hex 32)
   ```

2. **Set encryption key**:
   ```bash
   export PSEUDONYM_ENCRYPTION_KEY=$(openssl rand -base64 32)
   ```

3. **Configure storage path**:
   ```bash
   export PSEUDONYM_STORAGE_PATH=/secure/storage/pseudonym_mappings
   ```

4. **Set appropriate file permissions**:
   ```bash
   chmod 700 /secure/storage/pseudonym_mappings
   ```

### Health Checks

The pseudonymization service includes health monitoring:

```bash
# Check service health
curl http://localhost:8080/health

# Response includes pseudonymization status
{
  "status": "healthy",
  "pseudonymization": {
    "enabled": true,
    "total_mappings": 1250,
    "encryption_enabled": true
  }
}
```

## Troubleshooting

### Common Issues

1. **Pseudonymization disabled**:
   - Check `PSEUDONYMIZATION_ENABLED=true`
   - Verify middleware is properly loaded

2. **Inconsistent pseudonyms**:
   - Ensure `PSEUDONYM_SALT_KEY` is consistent across restarts
   - Check mapping file permissions

3. **Encryption errors**:
   - Verify `PSEUDONYM_ENCRYPTION_KEY` format
   - Check available disk space for mapping files

4. **Performance issues**:
   - Monitor mapping cache size
   - Consider periodic cleanup of old mappings

### Debug Mode

Enable debug logging for pseudonymization:

```bash
export LOG_LEVEL=DEBUG
```

This will log pseudonymization events (without exposing original identifiers).

## Compliance

This implementation supports:
- ✅ **HIPAA** - PHI protection through pseudonymization
- ✅ **GDPR** - Pseudonymization as privacy protection measure  
- ✅ **FDA** - Medical device software validation requirements
- ✅ **ISO 27001** - Information security management

## Security Contact

For security-related issues with the pseudonymization system, please contact the security team immediately. Do not file public issues for security vulnerabilities.