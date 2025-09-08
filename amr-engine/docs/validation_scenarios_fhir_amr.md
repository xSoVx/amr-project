**Overview**
- Below are focused validation scenarios for a FHIR R4–based AMR classification service, targeting critical edge cases. Each includes Preconditions, an Input FHIR JSON example, Expected Output, and concrete Validation Criteria.

**TC-AMR-001: Missing MIC Value (MIC method)**
- Preconditions:
  - Active ruleset: EUCAST 2024.1 + local overlay.
  - Service enforces method/value consistency (MIC requires `valueQuantity` in mg/L).
- Input (FHIR JSON):
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Patient", "id": "pat1" } },
    {
      "resource": {
        "resourceType": "Specimen",
        "id": "spec1",
        "type": { "text": "Urine" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "org1",
        "status": "final",
        "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory" }] }],
        "code": { "text": "Organism identified" },
        "valueCodeableConcept": { "text": "Escherichia coli" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "sus1",
        "status": "final",
        "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory" }] }],
        "code": { "text": "Ciprofloxacin [Susceptibility] by MIC" },
        "method": { "text": "MIC" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" },
        "derivedFrom": [{ "reference": "Observation/org1" }]
      }
    }
  ]
}
```
- Expected Output:
  - HTTP 400 ProblemDetails or classification outcome “Requires Review” with reason “MIC value missing for MIC method”.
- Validation Criteria:
  - FHIR resource valid overall; susceptibility Observation lacks `valueQuantity`.
  - Service detects missing `valueQuantity` when `method` indicates MIC.
  - No classification computed; explicit error message cites missing MIC.

**TC-AMR-002: Conflicting Results (MIC vs Disk)**
- Preconditions:
  - Active ruleset: EUCAST 2024.1 + local.
  - Method precedence configured (e.g., MIC > Disk) or conflict policy set to “Requires Review”.
- Input (FHIR JSON):
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Patient", "id": "pat1" } },
    { "resource": { "resourceType": "Specimen", "id": "spec1", "type": { "text": "Blood" } } },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "org1",
        "status": "final",
        "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory" }] }],
        "code": { "text": "Organism identified" },
        "valueCodeableConcept": { "text": "Klebsiella pneumoniae" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "sus_mic",
        "status": "final",
        "code": { "text": "Ceftriaxone [Susceptibility] by MIC" },
        "method": { "text": "MIC" },
        "valueQuantity": { "value": 0.5, "unit": "mg/L", "system": "http://unitsofmeasure.org", "code": "mg/L" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" },
        "derivedFrom": [{ "reference": "Observation/org1" }]
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "sus_disk",
        "status": "final",
        "code": { "text": "Ceftriaxone [Susceptibility] by disk diffusion" },
        "method": { "text": "DISK" },
        "valueQuantity": { "value": 13, "unit": "mm", "system": "http://unitsofmeasure.org", "code": "mm" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" },
        "derivedFrom": [{ "reference": "Observation/org1" }]
      }
    }
  ]
}
```
- Expected Output:
  - Classification for ceftriaxone flagged as “Requires Review” due to conflicting method results, or resolved per configured precedence with an audit warning.
- Validation Criteria:
  - Both observations reference same organism/specimen and antibiotic.
  - Values map to discordant categories using current breakpoints.
  - Service either:
    - Marks conflict and returns REVIEW; or
    - Chooses MIC (if precedence=MIC) but logs/returns a conflict warning with both inputs echoed.

**TC-AMR-003: Multi-Drug Resistant – ESBL Enterobacterales**
- Preconditions:
  - Policy flag `esbl_override_beta_lactams=true`.
  - Organism: Escherichia coli (Enterobacterales).
- Input (FHIR JSON):
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Patient", "id": "pat1" } },
    { "resource": { "resourceType": "Specimen", "id": "spec1", "type": { "text": "Urine" } } },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "org1",
        "status": "final",
        "code": {
          "coding": [{ "system": "http://snomed.info/sct", "code": "112283007", "display": "Escherichia coli" }],
          "text": "Escherichia coli"
        },
        "valueCodeableConcept": { "text": "Escherichia coli" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "esbl1",
        "status": "final",
        "code": { "text": "ESBL phenotypic detection" },
        "valueCodeableConcept": { "text": "Detected" },
        "derivedFrom": [{ "reference": "Observation/org1" }],
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "ceftriaxone_mic",
        "status": "final",
        "code": { "text": "Ceftriaxone [Susceptibility] by MIC" },
        "method": { "text": "MIC" },
        "valueQuantity": { "value": 0.5, "unit": "mg/L", "system": "http://unitsofmeasure.org", "code": "mg/L" },
        "derivedFrom": [{ "reference": "Observation/org1" }],
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "ceftazidime_mic",
        "status": "final",
        "code": { "text": "Ceftazidime [Susceptibility] by MIC" },
        "method": { "text": "MIC" },
        "valueQuantity": { "value": 1, "unit": "mg/L", "system": "http://unitsofmeasure.org", "code": "mg/L" },
        "derivedFrom": [{ "reference": "Observation/org1" }],
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    }
  ]
}
```
- Expected Output:
  - Ceftriaxone: Resistant (override due to ESBL regardless of favorable MIC).
  - Ceftazidime: Resistant (override).
- Validation Criteria:
  - ESBL detection associated with same isolate/specimen influences beta-lactam/aztreonam class.
  - Overrides applied even if raw MIC suggests S/I.
  - Non-target classes (e.g., carbapenems) are not auto-overridden.

**TC-AMR-004: Corrupted FHIR Resource**
- Preconditions:
  - Strict FHIR JSON schema validation enabled.
- Input (FHIR JSON):
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Observation",
        "id": "bad1",
        "status": "final",
        "code": { "text": "Levofloxacin [Susceptibility] by MIC" },
        "method": { "text": "MIC" },
        "valueQuantity": { "value": "abc", "unit": "mg/L", "system": "http://unitsofmeasure.org", "code": "mg/L" },
        "specimen": { "reference": "Specimen/specX" }
      }
    }
  ]
}
```
- Expected Output:
  - HTTP 400 ProblemDetails with validation errors:
    - `Observation.subject` missing.
    - `Observation.valueQuantity.value` wrong type (string vs number).
    - `Specimen/specX` not found (unresolvable reference).
- Validation Criteria:
  - JSON schema/type violations reported with precise pointer paths.
  - Missing required references flagged.
  - No classification attempted when structural validation fails.

**TC-AMR-005: Incorrect SNOMED Mapping (Code/Display Mismatch)**
- Preconditions:
  - Terminology validation via `$validate-code` enabled for SNOMED CT.
- Input (FHIR JSON):
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Patient", "id": "pat1" } },
    { "resource": { "resourceType": "Specimen", "id": "spec1", "type": { "text": "Wound" } } },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "org_bad",
        "status": "final",
        "code": {
          "coding": [{ "system": "http://snomed.info/sct", "code": "22298006", "display": "Escherichia coli" }],
          "text": "Escherichia coli"
        },
        "valueCodeableConcept": { "text": "Escherichia coli" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "sus1",
        "status": "final",
        "code": { "text": "Ciprofloxacin [Susceptibility] by MIC" },
        "method": { "text": "MIC" },
        "valueQuantity": { "value": 0.25, "unit": "mg/L", "system": "http://unitsofmeasure.org", "code": "mg/L" },
        "derivedFrom": [{ "reference": "Observation/org_bad" }],
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    }
  ]
}
```
- Expected Output:
  - HTTP 422 ProblemDetails indicating invalid SNOMED code/display pair or code not in expected organism hierarchy.
  - No classification returned.
- Validation Criteria:
  - `$validate-code` invoked for `code.coding[0]` against SNOMED; code/display mismatch detected.
  - Service blocks downstream normalization and classification on terminology failure.
  - Error response includes offending code and system.

**TC-AMR-006: Intrinsic Resistance — Pseudomonas aeruginosa vs Ceftriaxone**
- Preconditions:
  - Intrinsic resistance rules enabled (P. aeruginosa intrinsically R to ceftriaxone/ertapenem/etc.).
- Input (FHIR JSON):
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Patient", "id": "pat1" } },
    { "resource": { "resourceType": "Specimen", "id": "spec1", "type": { "text": "Sputum" } } },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "org1",
        "status": "final",
        "code": { "text": "Organism identified" },
        "valueCodeableConcept": { "text": "Pseudomonas aeruginosa" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "sus1",
        "status": "final",
        "code": { "text": "Ceftriaxone [Susceptibility] by MIC" },
        "method": { "text": "MIC" },
        "valueQuantity": { "value": 0.5, "unit": "mg/L", "system": "http://unitsofmeasure.org", "code": "mg/L" },
        "derivedFrom": [{ "reference": "Observation/org1" }],
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    }
  ]
}
```
- Expected Output:
  - Classification: Resistant via intrinsic rule, regardless of favorable MIC.
  - Rationale mentions organism-specific intrinsic resistance.
- Validation Criteria:
  - Intrinsic rule evaluated before breakpoint lookup.
  - Output includes rule identifier and clear rationale overriding MIC-derived category.

**TC-AMR-007: Disk Method Without Zone Diameter**
- Preconditions:
  - Disk diffusion method requires `valueQuantity` in mm.
- Input (FHIR JSON):
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Patient", "id": "pat1" } },
    { "resource": { "resourceType": "Specimen", "id": "spec1", "type": { "text": "Urine" } } },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "org1",
        "status": "final",
        "code": { "text": "Organism identified" },
        "valueCodeableConcept": { "text": "Staphylococcus aureus" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "sus1",
        "status": "final",
        "code": { "text": "Clindamycin [Susceptibility] by disk diffusion" },
        "method": { "text": "DISK" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" },
        "derivedFrom": [{ "reference": "Observation/org1" }]
      }
    }
  ]
}
```
- Expected Output:
  - HTTP 400 ProblemDetails or classification “Requires Review” with message “Zone diameter missing for disk method”.
- Validation Criteria:
  - `valueQuantity` is required when `method=DISK`.
  - No classification performed without a numeric zone in mm.

**TC-AMR-008: MRSA Beta-lactam Override**
- Preconditions:
  - Policy `mrsa_betalactam_override=true`.
- Input (FHIR JSON):
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Patient", "id": "pat1" } },
    { "resource": { "resourceType": "Specimen", "id": "spec1", "type": { "text": "Blood" } } },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "org1",
        "status": "final",
        "code": { "text": "Organism identified" },
        "valueCodeableConcept": { "text": "Staphylococcus aureus" },
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "mrsa_screen",
        "status": "final",
        "code": { "text": "Cefoxitin screen" },
        "valueCodeableConcept": { "text": "Positive" },
        "derivedFrom": [{ "reference": "Observation/org1" }],
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "oxacillin_mic",
        "status": "final",
        "code": { "text": "Oxacillin [Susceptibility] by MIC" },
        "method": { "text": "MIC" },
        "valueQuantity": { "value": 0.25, "unit": "mg/L", "system": "http://unitsofmeasure.org", "code": "mg/L" },
        "derivedFrom": [{ "reference": "Observation/org1" }],
        "subject": { "reference": "Patient/pat1" },
        "specimen": { "reference": "Specimen/spec1" }
      }
    }
  ]
}
```
- Expected Output:
  - Oxacillin (and most beta-lactams): Resistant via MRSA override, with rationale.
- Validation Criteria:
  - MRSA phenotype detection influences beta-lactam classification irrespective of raw MIC.
  - Anti-MRSA cephalosporins (e.g., ceftaroline) are exempt or forced to review per policy.

**General Expected Output Shape (Success)**
```json
{
  "ruleset": "EUCAST_2024.1+local",
  "results": [
    {
      "antibiotic": "ceftriaxone",
      "classification": "R",
      "rationale": "Intrinsic or expert rule applied",
      "ruleIds": ["INTR-003", "EXPR-001"]
    }
  ],
  "warnings": []
}
```

**General Expected Output Shape (Error)**
```json
{
  "type": "https://amr.example.org/errors/validation",
  "title": "Validation failed",
  "status": 400,
  "detail": "valueQuantity.value must be a number",
  "instance": "/v1/classify",
  "errors": [
    { "path": "/entry/0/resource/valueQuantity/value", "message": "Expected number" }
  ],
  "traceId": "01HT.."
}
```

