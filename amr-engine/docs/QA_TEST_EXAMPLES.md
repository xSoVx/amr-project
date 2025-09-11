# AMR Engine QA Test Examples

This document provides comprehensive test examples for Quality Assurance testing of the AMR Engine with pseudonymization functionality.

## HL7v2 Test Examples

### Valid HL7v2 Examples (Good Cases)

#### 1. Complete E. coli Susceptibility Report
```
MSH|^~\&|LABSYS|CENTRAL_LAB|EMR|MAIN_HOSPITAL|20240315143000||ORU^R01|MSG001|P|2.5
PID|1||P12345678^^^MRN^MR||JOHNSON^ROBERT^M||19801215|M|||123 MAIN ST^^ANYTOWN^NY^12345||555-1234|||123456789
OBR|1|||MICRO^Microbiology Culture^L||202403151200||||||||SPEC001^URINE^L||||||||20240315140000|||F
OBX|1|ST|ORG^Organism^L||Escherichia coli||||||F
OBX|2|NM|MIC^Ampicillin MIC^L||16|mg/L|R|||F
OBX|3|NM|MIC^Ciprofloxacin MIC^L||0.25|mg/L|S|||F
OBX|4|NM|MIC^Gentamicin MIC^L||2|mg/L|S|||F
OBX|5|NM|DISC^Amoxicillin Disc^L||12|mm|R|||F
```

#### 2. Staphylococcus aureus MRSA Testing
```
MSH|^~\&|MICRO_LAB|ST_MARY|HIS|ST_MARY|20240315150000||ORU^R01|MSG002|P|2.5
PID|1||MRN987654321^^^HOSP^MR||SMITH^JANE^A||19920605|F|||456 ELM AVE^^HEALTHCARE^CA^90210||555-9876|||987654321
OBR|1|||BAC^Bacterial Culture^L||202403151400||||||||SPEC002^BLOOD^L||||||||20240315143000|||F
OBX|1|ST|ORG^Organism^L||Staphylococcus aureus||||||F
OBX|2|ST|MRSA^MRSA Detection^L||POSITIVE||||||F
OBX|3|NM|MIC^Vancomycin MIC^L||1|mg/L|S|||F
OBX|4|NM|MIC^Linezolid MIC^L||2|mg/L|S|||F
OBX|5|DISC|DISC^Clindamycin Disc^L||22|mm|S|||F
```

#### 3. Klebsiella pneumoniae with Multiple Antibiotics
```
MSH|^~\&|LAB_SYSTEM|GENERAL_HOSP|EMR_SYS|GENERAL_HOSP|20240316080000||ORU^R01|MSG003|P|2.5
PID|1||PATIENT777^^^MRN^MR||WILLIAMS^DAVID^J||19751120|M|||789 OAK ST^^METROPOLIS^TX^77001||555-3333|||444555666
OBR|1|||CULT^Culture^L||202403160600||||||||SPEC003^SPUTUM^L||||||||20240316074500|||F
OBX|1|ST|ORG^Organism^L||Klebsiella pneumoniae||||||F
OBX|2|NM|MIC^Meropenem MIC^L||0.5|mg/L|S|||F
OBX|3|NM|MIC^Ceftriaxone MIC^L||32|mg/L|R|||F
OBX|4|NM|MIC^Amikacin MIC^L||8|mg/L|S|||F
OBX|5|NM|MIC^Colistin MIC^L||1|mg/L|S|||F
```

#### 4. Pseudomonas aeruginosa Wound Culture
```
MSH|^~\&|MICRO_LAB|CITY_HOSPITAL|LAB_INFO|CITY_HOSPITAL|20240317112000||ORU^R01|MSG004|P|2.5
PID|1||ID555999^^^ACCT^AN||BROWN^SARAH^K||19880303|F|||321 PINE RD^^RIVERSIDE^FL^33101||555-7788|||111222333
OBR|1|||WND^Wound Culture^L||202403171000||||||||SPEC004^WOUND^L||||||||20240317103000|||F
OBX|1|ST|ORG^Organism^L||Pseudomonas aeruginosa||||||F
OBX|2|NM|MIC^Piperacillin-Tazobactam MIC^L||8|mg/L|S|||F
OBX|3|NM|MIC^Ceftazidime MIC^L||4|mg/L|S|||F
OBX|4|NM|MIC^Tobramycin MIC^L||2|mg/L|S|||F
OBX|5|DISC|DISC^Aztreonam Disc^L||18|mm|S|||F
```

#### 5. Enterococcus faecium VRE Testing
```
MSH|^~\&|LABWARE|METRO_MEDICAL|EPIC|METRO_MEDICAL|20240318094500||ORU^R01|MSG005|P|2.5
PID|1||PTID123456^^^EPIC^MR||DAVIS^MICHAEL^R||19650815|M|||654 MAPLE DR^^SUBURBAN^IL^60601||555-4455|||777888999
OBR|1|||ENTERO^Enterococcus Culture^L||202403180800||||||||SPEC005^RECTAL^L||||||||20240318085000|||F
OBX|1|ST|ORG^Organism^L||Enterococcus faecium||||||F
OBX|2|ST|VRE^VRE Detection^L||POSITIVE||||||F
OBX|3|NM|MIC^Linezolid MIC^L||2|mg/L|S|||F
OBX|4|NM|MIC^Daptomycin MIC^L||3|mg/L|S|||F
OBX|5|NM|MIC^Ampicillin MIC^L||>16|mg/L|R|||F
```

### Invalid HL7v2 Examples (Bad Cases)

#### 6. Missing MSH Segment (Critical Error)
```
PID|1||BAD001^^^MRN^MR||ERROR^TEST^CASE||19900101|M|||ERROR ST^^ERROR^XX^00000||555-0000|||000000000
OBR|1|||MICRO^Test^L||202403151200||||||||SPECBAD^URINE^L||||||||20240315140000|||F
OBX|1|ST|ORG^Organism^L||Escherichia coli||||||F
```

#### 7. Malformed MSH Segment
```
MSH|WRONG_DELIMITERS|LAB|HOSP|EMR|HOSP|20240315||ORU|MSG007|P|2.5
PID|1||BAD002^^^MRN^MR||MALFORMED^MSH^TEST||19850510|F|||BAD ADDR^^CITY^ST^12345||555-1111|||111111111
OBR|1|||CULT^Culture^L||202403151300||||||||SPECBAD2^BLOOD^L||||||||20240315131500|||F
OBX|1|ST|ORG^Organism^L||Staphylococcus aureus||||||F
```

#### 8. Missing Required OBX Segments
```
MSH|^~\&|LAB|HOSPITAL|EMR|HOSPITAL|20240316100000||ORU^R01|MSG008|P|2.5
PID|1||BAD003^^^MRN^MR||INCOMPLETE^DATA^TEST||19700225|M|||INCOMPLETE ST^^CITY^ST^54321||555-2222|||222222222
OBR|1|||MICRO^Microbiology^L||202403160900||||||||SPECBAD3^SPUTUM^L||||||||20240316093000|||F
```

#### 9. Invalid Field Separators and Encoding
```
MSH~^&\~LAB~HOSPITAL~EMR~HOSPITAL~20240317~ORU^R01~MSG009~P~2.5
PID~1~~BAD004^^^MRN^MR~~INVALID^ENCODING^TEST~~19950412~F~~~WRONG ENCODING^^CITY^ST^98765~~555-3333~~~333333333
OBR~1~~~CULT^Culture^L~~202403171100~~~~~~~~SPECBAD4^WOUND^L~~~~~~~~20240317110000~~~F
OBX~1~ST~ORG^Organism^L~~Pseudomonas aeruginosa~~~~~~F
```

#### 10. Truncated Message (Incomplete)
```
MSH|^~\&|LAB|HOSPITAL|EMR|HOSPITAL|20240318120000||ORU^R01|MSG010|P|2.5
PID|1||BAD005^^^MRN^MR||TRUNCATED^MESSAGE^TEST||19801010|M|||INCOMPLETE ADDR^^CI
```

## FHIR R4 Test Examples

### Valid FHIR Examples (Good Cases)

#### 1. Complete E. coli Bundle with Patient and Observations
```json
{
  "resourceType": "Bundle",
  "id": "bundle-ecoli-001",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "patient-12345",
        "identifier": [
          {
            "use": "usual",
            "type": {
              "coding": [
                {
                  "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                  "code": "MR"
                }
              ]
            },
            "value": "MRN12345678"
          }
        ],
        "name": [
          {
            "family": "Johnson",
            "given": ["Robert", "M"]
          }
        ],
        "gender": "male",
        "birthDate": "1980-12-15"
      }
    },
    {
      "resource": {
        "resourceType": "Specimen",
        "id": "specimen-urine-001",
        "identifier": [
          {
            "value": "SPEC001"
          }
        ],
        "type": {
          "coding": [
            {
              "system": "http://snomed.info/sct",
              "code": "122575003",
              "display": "Urine specimen"
            }
          ]
        },
        "subject": {
          "reference": "Patient/patient-12345"
        },
        "collection": {
          "collectedDateTime": "2024-03-15T14:00:00Z"
        }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "organism-ecoli",
        "status": "final",
        "category": [
          {
            "coding": [
              {
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "laboratory"
              }
            ]
          }
        ],
        "code": {
          "coding": [
            {
              "system": "http://loinc.org",
              "code": "634-6",
              "display": "Bacteria identified in Specimen by Culture"
            }
          ]
        },
        "subject": {
          "reference": "Patient/patient-12345"
        },
        "specimen": {
          "reference": "Specimen/specimen-urine-001"
        },
        "valueCodeableConcept": {
          "coding": [
            {
              "system": "http://snomed.info/sct",
              "code": "112283007",
              "display": "Escherichia coli"
            }
          ]
        }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "ampicillin-mic",
        "status": "final",
        "category": [
          {
            "coding": [
              {
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "laboratory"
              }
            ]
          }
        ],
        "code": {
          "coding": [
            {
              "system": "http://loinc.org",
              "code": "18864-9",
              "display": "Ampicillin [Susceptibility] by Minimum inhibitory concentration (MIC)"
            }
          ]
        },
        "subject": {
          "reference": "Patient/patient-12345"
        },
        "specimen": {
          "reference": "Specimen/specimen-urine-001"
        },
        "valueQuantity": {
          "value": 16,
          "unit": "mg/L"
        },
        "interpretation": [
          {
            "coding": [
              {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                "code": "R",
                "display": "Resistant"
              }
            ]
          }
        ]
      }
    }
  ]
}
```

#### 2. MRSA Detection Bundle
```json
{
  "resourceType": "Bundle",
  "id": "bundle-mrsa-002",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "patient-67890",
        "identifier": [
          {
            "use": "usual",
            "value": "HOSP987654321"
          }
        ],
        "name": [
          {
            "family": "Smith",
            "given": ["Jane", "A"]
          }
        ],
        "gender": "female",
        "birthDate": "1992-06-05"
      }
    },
    {
      "resource": {
        "resourceType": "Specimen",
        "id": "specimen-blood-002",
        "identifier": [
          {
            "value": "SPEC002"
          }
        ],
        "type": {
          "coding": [
            {
              "system": "http://snomed.info/sct",
              "code": "119297000",
              "display": "Blood specimen"
            }
          ]
        },
        "subject": {
          "reference": "Patient/patient-67890"
        }
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "organism-staph",
        "status": "final",
        "code": {
          "coding": [
            {
              "system": "http://loinc.org",
              "code": "634-6",
              "display": "Bacteria identified"
            }
          ]
        },
        "subject": {
          "reference": "Patient/patient-67890"
        },
        "specimen": {
          "reference": "Specimen/specimen-blood-002"
        },
        "valueCodeableConcept": {
          "coding": [
            {
              "system": "http://snomed.info/sct",
              "code": "3092008",
              "display": "Staphylococcus aureus"
            }
          ]
        }
      }
    }
  ]
}
```

#### 3. Klebsiella pneumoniae Multi-drug Testing
```json
{
  "resourceType": "Bundle",
  "id": "bundle-klebsiella-003",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "patient-kp-777",
        "identifier": [
          {
            "value": "PATIENT777"
          }
        ],
        "name": [
          {
            "family": "Williams",
            "given": ["David", "J"]
          }
        ],
        "gender": "male"
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "meropenem-mic",
        "status": "final",
        "code": {
          "coding": [
            {
              "system": "http://loinc.org",
              "code": "29576-6",
              "display": "Meropenem [Susceptibility] by MIC"
            }
          ]
        },
        "subject": {
          "reference": "Patient/patient-kp-777"
        },
        "valueQuantity": {
          "value": 0.5,
          "unit": "mg/L"
        },
        "interpretation": [
          {
            "coding": [
              {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                "code": "S"
              }
            ]
          }
        ]
      }
    }
  ]
}
```

#### 4. Individual Observation (No Bundle)
```json
{
  "resourceType": "Observation",
  "id": "single-obs-004",
  "status": "final",
  "category": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/observation-category",
          "code": "laboratory"
        }
      ]
    }
  ],
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "18900-1",
        "display": "Ciprofloxacin [Susceptibility] by MIC"
      }
    ]
  },
  "subject": {
    "reference": "Patient/patient-single-555"
  },
  "valueQuantity": {
    "value": 0.25,
    "unit": "mg/L"
  },
  "interpretation": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
          "code": "S",
          "display": "Susceptible"
        }
      ]
    }
  ]
}
```

#### 5. Complex Bundle with Multiple Patients
```json
{
  "resourceType": "Bundle",
  "id": "bundle-multi-patient-005",
  "type": "batch",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "patient-batch-001",
        "identifier": [
          {
            "value": "BATCH001"
          }
        ],
        "name": [
          {
            "family": "Anderson",
            "given": ["Alice"]
          }
        ]
      }
    },
    {
      "resource": {
        "resourceType": "Patient",
        "id": "patient-batch-002", 
        "identifier": [
          {
            "value": "BATCH002"
          }
        ],
        "name": [
          {
            "family": "Baker",
            "given": ["Bob"]
          }
        ]
      }
    },
    {
      "resource": {
        "resourceType": "Observation",
        "id": "obs-batch-001",
        "status": "final",
        "code": {
          "coding": [
            {
              "system": "http://loinc.org",
              "code": "634-6"
            }
          ]
        },
        "subject": {
          "reference": "Patient/patient-batch-001"
        },
        "valueString": "Escherichia coli"
      }
    }
  ]
}
```

### Invalid FHIR Examples (Bad Cases)

#### 6. Invalid JSON Structure
```json
{
  "resourceType": "Bundle",
  "id": "bundle-invalid-json",
  "type": "collection"
  "entry": [
    {
      "resource": {
        "resourceType": "Patient"
        "id": "bad-patient-001"
        "identifier": [
          {
            "value": "INVALID_JSON_001"
          }
        ]
      }
    }
  ]
}
```

#### 7. Missing Required Fields
```json
{
  "resourceType": "Bundle",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "identifier": [
          {
            "value": "MISSING_ID_002"
          }
        ]
      }
    }
  ]
}
```

#### 8. Invalid Resource Type
```json
{
  "resourceType": "InvalidResource",
  "id": "bad-resource-008",
  "someField": "This is not a valid FHIR resource"
}
```

#### 9. Malformed References
```json
{
  "resourceType": "Bundle",
  "id": "bundle-bad-refs-009",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Observation",
        "id": "obs-bad-ref",
        "status": "final",
        "subject": {
          "reference": "InvalidReference/does-not-exist"
        },
        "code": {
          "coding": [
            {
              "system": "invalid-system",
              "code": "bad-code"
            }
          ]
        }
      }
    }
  ]
}
```

#### 10. Empty or Null Values
```json
{
  "resourceType": "Bundle",
  "id": null,
  "type": "",
  "entry": []
}
```

## Test Execution Guide

### HL7v2 Testing Commands

#### Good Examples (Should Process Successfully)
```bash
# Test 1: Complete E. coli Report
curl -X POST "http://localhost:8090/classify/hl7v2" \
     -H "Content-Type: application/hl7-v2" \
     -d @hl7v2_example_1.txt

# Test 2: MRSA Detection
curl -X POST "http://localhost:8090/classify/hl7v2" \
     -H "Content-Type: text/plain" \
     -d @hl7v2_example_2.txt

# Test 3-5: Additional valid examples...
```

#### Bad Examples (Should Return Errors)
```bash
# Test 6: Missing MSH (Should fail with parsing error)
curl -X POST "http://localhost:8090/classify/hl7v2" \
     -H "Content-Type: application/hl7-v2" \
     -d @hl7v2_bad_example_1.txt

# Expected: {"error": "HL7v2 parsing error: Missing MSH segment"}
```

### FHIR Testing Commands

#### Good Examples
```bash
# Test 1: Complete Bundle
curl -X POST "http://localhost:8090/classify/fhir" \
     -H "Content-Type: application/fhir+json" \
     -d @fhir_example_1.json

# Test 2-5: Additional valid examples...
```

#### Bad Examples
```bash
# Test 6: Invalid JSON
curl -X POST "http://localhost:8090/classify/fhir" \
     -H "Content-Type: application/fhir+json" \
     -d @fhir_bad_example_1.json

# Expected: {"error": "Invalid JSON structure"}
```

## Expected Pseudonymization Results

### Patient Identifier Transformations
- `P12345678` → `HL7-PT-A1B2C3D4`
- `MRN12345678` → `HL7-MR-B2C3D4E5`
- `SPEC001` → `HL7-SP-C3D4E5F6`
- `PATIENT777` → `HL7-PT-D4E5F6G7`

### Testing Verification Points
1. **Pseudonymization Active**: Check logs for pseudonymization events
2. **Consistent Mapping**: Same input should produce same pseudonym
3. **PHI Protection**: Original identifiers should not appear in responses
4. **Error Handling**: Bad examples should return appropriate error messages
5. **Format Support**: Both HL7v2 and FHIR formats should be processed
6. **Content Types**: Multiple content types should be supported

## QA Testing Checklist

### Functionality Tests
- [ ] All 5 good HL7v2 examples process successfully
- [ ] All 5 good FHIR examples process successfully  
- [ ] All 5 bad HL7v2 examples return appropriate errors
- [ ] All 5 bad FHIR examples return appropriate errors
- [ ] Pseudonymization is active for all valid examples
- [ ] Error messages are informative and appropriate

### Security Tests
- [ ] No original patient identifiers in responses
- [ ] Consistent pseudonym generation
- [ ] Audit logs contain only pseudonymized identifiers
- [ ] No PHI leakage in error messages

### Performance Tests
- [ ] Response times within acceptable limits
- [ ] Memory usage stable during testing
- [ ] No memory leaks with repeated requests
- [ ] Concurrent request handling

This comprehensive test suite provides thorough coverage of both positive and negative test cases for the AMR Engine pseudonymization system.