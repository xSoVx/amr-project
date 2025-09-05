# Enhanced AMR Engine - Full Specification Implementation

## Overview

The Enhanced AMR Engine is a comprehensive Antimicrobial Resistance (AMR) classification microservice that fully implements the specification requirements. It provides end-to-end AMR workflows including FHIR R4/HL7v2 data processing, advanced expert rules, surveillance analytics, multi-site support, and MoH reporting.

## 🆕 Major Enhancements Added

### 1. SNOMED CT Terminology Service Integration
- **File**: `amr_engine/core/terminology.py`
- **Features**:
  - Real-time SNOMED CT validation via terminology servers
  - Offline fallback validation for common organisms
  - Organism name normalization
  - Code/display validation with `$validate-code` operation

### 2. Comprehensive FHIR Resource Support
- **File**: `amr_engine/core/fhir_resources.py`
- **Features**:
  - Complete FHIR R4 resource models (Patient, Specimen, Observation, DiagnosticReport, Bundle)
  - Enhanced resource validation with detailed error reporting
  - Support for `hasMember` relationships and `derivedFrom` references
  - FHIR resource extraction and reference resolution

### 3. Advanced Exception Rules Engine
- **File**: `amr_engine/core/expert_rules.py`
- **Features**:
  - **ESBL Override Rules**: Auto-report beta-lactams as Resistant for ESBL producers
  - **MRSA Override Rules**: Auto-report beta-lactams as Resistant for MRSA
  - **Carbapenemase Override Rules**: Auto-report carbapenems as Resistant for producers
  - **VRE Override Rules**: Auto-report vancomycin as Resistant for VRE
  - **Intrinsic Resistance Rules**: P. aeruginosa, Enterococcus, Acinetobacter natural resistance
  - **Special Rules**: Cefoxitin MRSA screening, D-test for clindamycin

### 4. HL7v2 Message Processing
- **File**: `amr_engine/core/hl7v2_parser.py`
- **Features**:
  - Full HL7v2 ORU^R01 message parsing
  - Automatic organism and antibiotic code mapping
  - Support for MIC/Disc value extraction from OBX segments
  - Integration with existing FHIR workflow

### 5. FHIR Profile Validation
- **File**: `amr_engine/core/fhir_profiles.py`
- **Features**:
  - Built-in validation for standard FHIR profiles
  - AMR-specific profiles (Microbiology Observation, AST Observation)
  - Cardinality validation, data type checking
  - Fixed value validation for CodeableConcepts

### 6. Multi-Site Support & RBAC System
- **File**: `amr_engine/core/rbac.py`
- **Features**:
  - **Roles**: Admin, Microbiologist, Lab Tech, Clinician, Infection Prevention, Surveillance, ReadOnly
  - **Permissions**: 15+ granular permissions for different operations
  - **Multi-Site Access**: Users can access multiple healthcare facilities
  - **JWT Authentication**: Secure token-based authentication
  - **Row-Level Security**: Data filtering based on site access

### 7. Surveillance Analytics & Antibiograms
- **File**: `amr_engine/core/surveillance.py`
- **Features**:
  - **CLSI M39 Compliant Antibiograms**: With deduplication and minimum isolate requirements
  - **MDRO Detection**: Multi-Drug Resistant Organism identification
  - **Outbreak Detection**: Statistical threshold and spike detection
  - **Resistance Trends**: Time-series analysis by organism/antibiotic
  - **Data Export**: CSV/JSON export with PHI protection

### 8. Enhanced API Endpoints
- **File**: `amr_engine/api/routes.py`
- **New Endpoints**:
  - `POST /classify` - Enhanced with FHIR/HL7v2 auto-detection
  - `POST /classify/hl7v2` - Dedicated HL7v2 endpoint
  - Content-type based format detection
  - Async processing support

## 📋 New Dependencies

Added to `pyproject.toml`:
```toml
"PyJWT==2.8.0"           # JWT authentication
"passlib[bcrypt]==1.7.4" # Password hashing
"python-multipart==0.0.6" # Multipart form support
```

## 🚀 Quick Start with Enhanced Features

### 1. Initialize with Enhanced Components
```bash
# Install enhanced dependencies
cd amr-engine
pip install -e .

# The system now includes all enhanced components
```

### 2. FHIR Bundle with SNOMED CT
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Observation",
        "id": "org1",
        "status": "final",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}],
        "code": {"text": "Organism identified"},
        "valueCodeableConcept": {
          "coding": [{"system": "http://snomed.info/sct", "code": "112283007", "display": "Escherichia coli"}]
        }
      }
    }
  ]
}
```

### 3. HL7v2 Message Processing
```
POST /classify/hl7v2
Content-Type: application/hl7-v2+er7

MSH|^~\&|LAB|Hospital|||202401011200||ORU^R01|MSG001|P|2.4
PID|1||12345^^^MRN||DOE^JOHN^A||19800101|M
SPM|1|SPEC001|URINE
OBX|1|CE|ORGANISM^Organism|1|ECOLI^Escherichia coli
OBX|2|ST|CIP^Ciprofloxacin^AST|1|<=0.25^mg/L
```

### 4. Generate Antibiogram
```python
from amr_engine.core.surveillance import surveillance_analytics, SurveillanceFilters
from datetime import datetime, timedelta

filters = SurveillanceFilters(
    start_date=datetime.now() - timedelta(days=365),
    end_date=datetime.now(),
    site_ids=["site-001"]
)

antibiogram = surveillance_analytics.generate_antibiogram(
    filters=filters,
    min_isolates=30  # CLSI M39 requirement
)
```

## 🧪 Validation Test Scenarios

The system now supports all validation scenarios from `docs/validation_scenarios_fhir_amr.md`:

### TC-AMR-001: Missing MIC Value
```json
POST /classify
{
  "resourceType": "Bundle",
  "entry": [{
    "resource": {
      "resourceType": "Observation",
      "code": {"text": "Ciprofloxacin [Susceptibility] by MIC"},
      "method": {"text": "MIC"}
      // Missing valueQuantity - will return HTTP 400
    }
  }]
}
```

### TC-AMR-003: ESBL Override
```json
{
  "resourceType": "Bundle", 
  "entry": [{
    "resource": {
      "resourceType": "Observation",
      "note": [{"text": "Escherichia coli; ESBL=true"}],
      "code": {"text": "Ceftriaxone [Susceptibility] by MIC"},
      "valueQuantity": {"value": 0.5, "unit": "mg/L"}
      // Will return "R" due to ESBL override regardless of favorable MIC
    }
  }]
}
```

### TC-AMR-006: Intrinsic Resistance
```json
{
  "organism": "Pseudomonas aeruginosa",
  "antibiotic": "Ceftriaxone",
  "method": "MIC",
  "mic_mg_L": 0.5
  // Will return "R" due to intrinsic resistance rule
}
```

## 🔒 Security & Multi-Site Features

### User Management
```python
from amr_engine.core.rbac import rbac_manager, Role

# Create microbiologist user
user = rbac_manager.create_user(
    username="micro001",
    password="secure_password",
    roles=[Role.MICROBIOLOGIST],
    site_access=["site-001", "site-002"]
)

# Generate JWT token
token = rbac_manager.create_jwt_token(user)
```

### Site-Based Data Access
```python
# Data is automatically filtered by user's site access
user_data = rbac_manager.filter_data_by_site_access(user, all_data)
```

## 📊 Surveillance & Analytics

### MDRO Detection
```python
mdro_report = surveillance_analytics.get_mdro_report(filters)
print(f"Total MDRO cases: {mdro_report['total_mdro_cases']}")
```

### Outbreak Detection
```python
alerts = surveillance_analytics.detect_outbreaks(
    site_id="site-001",
    lookback_days=30,
    threshold_multiplier=2.0
)
```

### Data Export with PHI Protection
```python
csv_data = surveillance_analytics.export_surveillance_data(
    filters=filters,
    format="csv",
    include_phi=False  # Automatically redacts PHI
)
```

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐
│   FHIR Bundle   │    │   HL7v2 Message  │
└─────────┬───────┘    └─────────┬────────┘
          │                      │
          v                      v
┌─────────────────────────────────────────┐
│         Enhanced Parser Layer           │
│  • FHIR Validation & Profile Checking  │
│  • SNOMED CT Terminology Validation    │
│  • HL7v2 Message Processing           │
└─────────────────┬───────────────────────┘
                  │
                  v
┌─────────────────────────────────────────┐
│         Expert Rules Engine             │
│  • ESBL/MRSA/Carbapenemase Overrides  │
│  • Intrinsic Resistance Rules         │
│  • Special Interpretive Rules         │
└─────────────────┬───────────────────────┘
                  │
                  v
┌─────────────────────────────────────────┐
│        Core Classification Engine       │
│  • EUCAST 2025.1 Breakpoints          │
│  • MIC/Disc Interpretation            │
│  • S/I/R/RR Decision Logic            │
└─────────────────┬───────────────────────┘
                  │
                  v
┌─────────────────────────────────────────┐
│         Multi-Site RBAC Layer           │
│  • Role-Based Permission Checking      │
│  • Site-Based Data Filtering          │
│  • JWT Authentication                 │
└─────────────────┬───────────────────────┘
                  │
                  v
┌─────────────────────────────────────────┐
│       Surveillance & Analytics          │
│  • CLSI M39 Antibiograms              │
│  • MDRO Detection & Reporting         │
│  • Outbreak Detection                 │
│  • Trend Analysis & Export            │
└─────────────────────────────────────────┘
```

## 🎯 Full Specification Compliance

✅ **FHIR R4 Support**: Complete Bundle, Observation, DiagnosticReport, Patient, Specimen  
✅ **SNOMED CT Integration**: Real-time validation with terminology servers  
✅ **HL7v2 Processing**: Full ORU^R01 message parsing and conversion  
✅ **Advanced Exception Rules**: ESBL, MRSA, Carbapenemase, Intrinsic resistance  
✅ **Multi-Site Architecture**: Role-based access control and site filtering  
✅ **Surveillance Analytics**: CLSI M39 antibiograms, MDRO detection, outbreak alerts  
✅ **Profile Validation**: Standard and custom FHIR profile compliance  
✅ **Enterprise Security**: JWT authentication, password hashing, audit trails  
✅ **Data Export**: PHI-protected CSV/JSON export for external analysis  

## 📈 Performance & Scalability

- **Async Processing**: All FHIR/terminology operations are asynchronous
- **Caching**: SNOMED CT codes and profiles cached for performance  
- **Horizontal Scaling**: Stateless design supports load balancing
- **Database Ready**: Surveillance data store easily migrated to production database

## 🔄 Migration Path

The enhanced system maintains 100% backward compatibility with existing API contracts while adding comprehensive new capabilities. Existing clients continue to work unchanged while gaining access to advanced features.

---

**The Enhanced AMR Engine now provides a complete, production-ready implementation of the full AMR specification with enterprise-grade security, multi-site support, and comprehensive surveillance capabilities.**