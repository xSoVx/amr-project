# Microbiology and AMR Module — Specification

## Introduction
This specification describes a Microbiology and Antimicrobial Resistance (AMR) module for clinical laboratories and public health programs. The module supports end‑to‑end microbiology workflows (order → specimen → culture/ID → AST → interpretation → reporting), surveillance analytics (cumulative antibiograms, resistance trends), and interoperable exchange using FHIR R4 and standardized terminologies (SNOMED CT; optional LOINC, UCUM). It integrates with LIS/EMR/HIS, laboratory instruments/middleware, and Ministry of Health (MoH) reporting pipelines.

## Scope
- In scope:
  - Order management, specimen lifecycle, culture workflows, organism identification, AST capture, interpretive categorization (S/I/R), and report finalization.
  - Standardized data exchange via FHIR R4; SNOMED CT for organisms, organisms’ properties, and clinical concepts.
  - AMR analytics: patient‑level, unit‑level, facility‑level, and cumulative antibiograms.
  - Alerting for critical results, notifiable organisms, and carbapenemase/ESBL/MR/VRE markers.
  - Integration with LIS/EMR/HIS, instrument middleware (AST, MALDI‑TOF, blood culture systems), and MoH reporting.
- Out of scope (initial phase):
  - Wet‑lab instrument control.
  - Advanced molecular genomics pipelines (WGS/AMR gene calling) beyond basic result ingestion.
  - Antimicrobial stewardship (AMS) clinical decision support beyond basic notifications.

## Functional Requirements

### 1) Orders and Specimens
- Receive and create lab orders with clinical indication, suspected site, priority, isolation status, and collection instructions.
- Track specimen lifecycle (requested, collected, received, rejected, processed, stored, disposed) with timestamps, collector, and chain‑of‑custody.
- Support multiple specimen types (blood, urine, sputum, CSF, wound, stool, swabs) with SNOMED CT body site and specimen concepts.
- Enforce rejection criteria (e.g., insufficient volume, wrong container, delayed transport); enable re‑collection workflows.
- Support reflex/duplicate order rules and order linking (e.g., paired blood cultures).

### 2) Culture, Identification, and Workups
- Record culture setups, subcultures, gram stain, colony counts/semi‑quantitative growth, contamination indicators.
- Capture organism identification (manual, biochemical, MALDI‑TOF, PCR panel), method, confidence, and versioned references.
- Manage mixed cultures; track per‑isolate lineage (specimen → culture → isolate).
- QC logging for media, reagents, and control strains.

### 3) Antimicrobial Susceptibility Testing (AST)
- Ingest AST from instruments/middleware; support manual entry and verification.
- Store per‑antibiotic MIC/zone values, method (e.g., VITEK, Phoenix, Kirby‑Bauer), and interpretation (S/I/R; plus I‑I for EUCAST if applicable).
- Apply breakpoint interpretation rules (CLSI/EUCAST), versioned and auditable; maintain historical interpretations when breakpoints update.
- Support intrinsic resistance rules, phenotype flags (ESBL, AmpC, KPC/NDM/OXA‑48, MRSA, VRE), and comment insertion.
- Reflex/confirmatory testing rules (e.g., D‑test, carbapenemase detection), with workflow prompts.

### 4) Results, Validation, and Reporting
- Multistage verification: technologist entry → senior review → microbiologist sign‑off.
- Generate interim and final Diagnostic Reports with:
  - Narrative culture results, organism list, AST tables, interpretive comments, specimen details, collection/receipt times, and disclaimers.
- Corrected/amended reports with reason, audit trail, and downstream notifications.
- Critical value and notifiable disease alerts (configurable routing to clinician/ward/ID team; on‑call rosters).
- Attachments: images (gram stain), instrument PDFs, QC documents.

### 5) Surveillance and Analytics
- Generate cumulative antibiograms (facility, service line, unit, organism, specimen type, period), with inclusion criteria per CLSI M39.
- Trend dashboards: resistance over time, MDRO incidence, broad‑spectrum usage overlays (if medication data available).
- Outbreak detection signals (e.g., thresholds, spike detection) with export for infection prevention teams.
- De‑duplication logic for surveillance vs. patient care reporting (configurable windows).

### 6) Terminology and Reference Data
- Use SNOMED CT for organisms, clinical findings, specimen types, procedures; support mapping management UI.
- Manage antibiotic dictionaries (preferred: ATC/RxNorm codes) and standardized units (UCUM).
- Manage breakpoint catalogs (CLSI/EUCAST), versioning and roll‑back; facility‑specific policies and suppress/merge rules.

### 7) Integration and Interoperability
- Support bidirectional FHIR R4 API for orders, specimens, observations, diagnostic reports, and alerts.
- HL7 v2 ORU/OML/OBX ingestion for instruments/middleware where FHIR not available.
- Push MoH‑required case/event reports and aggregate AMR data; schedule and on‑demand.
- Terminology server integration (SNOMED CT; optional LOINC, RxNorm/ATC) with local caching.

### 8) Security, Privacy, and Audit
- Role‑based access control (lab tech, microbiologist, clinician, infection prevention, admin).
- PHI minimization in surveillance exports; pseudonymization for analytics.
- Full audit trail for create/read/update/delete, sign‑offs, rules execution, and data exchange.
- Configurable data retention and legal hold; immutable event logs for report finalization.

### 9) Administration and Configuration
- UI for rules (reflex testing, alert routing, interpretation comments), breakpoint versions, terminology mappings, and data quality checks.
- Multi‑site configuration with site‑specific policies, formularies, and panels.
- Downtime procedures: queued orders/results, reconciliation on recovery.

## Non‑Functional Requirements

- Availability: ≥ 99.9% monthly; planned maintenance windows defined; no data loss on failover.
- Performance: 
  - Order creation < 300 ms p95; report retrieval < 600 ms p95.
  - Bulk analytics (antibiogram) for 50k isolates < 60 s p95.
- Scalability: Scale to 10k orders/day and 100 concurrent users; horizontal scale for analytics jobs.
- Security: Encryption in transit (TLS 1.2+), at rest (AES‑256+); secrets management (HSM/KMS); hardened endpoints; OWASP ASVS L2+.
- Privacy: Jurisdictional compliance (e.g., GDPR/HIPAA/PDPA); data minimization; consent/legitimate‑interest handling as applicable.
- Interoperability: FHIR R4 conformance testing; robust HL7 v2 parsing; terminology server resilience with local cache.
- Observability: Structured logs, metrics (latency, throughput, error rates), distributed tracing for integrations; alerting SLAs.
- Maintainability: Modular service boundaries; versioned APIs; infrastructure as code; automated regression tests.
- Data Quality: Validation rules, duplicate detection, required fields enforcement; terminology drift monitoring.
- Disaster Recovery: RPO ≤ 5 min; RTO ≤ 2 hr; periodic recovery drills.

## Compliance Standards

### FHIR R4 (core and profiles)
- ServiceRequest: lab orders (priority, reasonCode, requester, specimen).
- Specimen: specimen details (type, collection, container, condition).
- Observation:
  - Microbiology parent Observation (culture result) with `hasMember` to:
    - Organism Observations (code = organism identified).
    - Susceptibility Observations per antibiotic (components: antibiotic code, MIC/zone, S/I/R).
  - Phenotypic markers (ESBL/carbapenemase) as separate Observations or components.
- DiagnosticReport: final/interim reports referencing Observations and Specimen.
- Patient, Practitioner, Organization, Encounter: patient and context metadata.
- Bundle/Transaction: batched submission; $process-message for event‑style exchanges.
- Conformance:
  - Use `Observation.category = laboratory`.
  - Units standardized via UCUM; identifiers stable and traceable.
  - Provenance for signing, corrections, and imports.
  - Suggested profiles: HL7 Orders & Observations; IHE LAW (where applicable).

### SNOMED CT
- Organism identification: SNOMED CT Organism hierarchy.
- Clinical findings: infection diagnoses, phenotypic resistance markers.
- Specimen types/sites: SNOMED CT Specimen and Body Structure.
- Mapping strategy:
  - Canonical SNOMED codes stored with local display values.
  - Periodic map reconciliation; preserve original instrument codes for traceability.

### Ministry of Health (MoH)
- Reporting packages:
  - Notifiable infections/organisms case reporting (event‑based).
  - Aggregated AMR reporting (periodic, e.g., GLASS‑aligned metrics if mandated).
- Data schemas: conform to MoH‑published formats (CSV/XML/FHIR/HL7).
- Transport/security: as mandated (VPN, SFTP, API with mTLS/OAuth2).
- Audit: transmission receipts, retries, and reconciliation logs.

Note: Jurisdiction‑specific MoH requirements to be confirmed (see Knowledge Gaps).

## Integration Points

- EMR/HIS/LIS:
  - Orders in via FHIR `ServiceRequest` or HL7 v2 OML.
  - Results out via FHIR `DiagnosticReport`/`Observation` or HL7 v2 ORU.
- Instrument/Middleware:
  - AST/ID systems (VITEK, Phoenix, Microscan), MALDI‑TOF, blood culture systems, PCR panels.
  - Protocols: HL7 v2, ASTM, vendor APIs; middleware (e.g., DataInnovations).
- Terminology Services:
  - SNOMED CT; optional LOINC for lab test codes; RxNorm/ATC for antibiotics; UCUM for units.
- Identity and Access:
  - SSO (OIDC/SAML); role provisioning; user directory sync.
- Public Health/MoH:
  - Case‑based and aggregate data feeds; acknowledgements and error handling.
- Analytics Warehouse:
  - Outbound de‑identified datasets; scheduled or streaming to BI platforms.

## Data Model and FHIR Mapping (Overview)
- Order (ServiceRequest) → references `Specimen` (planned or collected).
- Specimen (Specimen) → type (SNOMED), collection details, container, accession.
- Culture Result (Observation) → parent Observation, `hasMember` groups:
  - Organism (Observation) → code: organism (SNOMED), method, comments.
  - Susceptibility (Observation) → code: “Antibiotic susceptibility,” components:
    - `antibiotic` (code: RxNorm/ATC; mapped to local), `value` (MIC/zone with UCUM), `interpretation` (S/I/R), `method` (e.g., Etest).
- DiagnosticReport → composes Observations, includes status, conclusion, presentedForm (PDF), and performer.
- Provenance → signer, timestamps, reason (finalize/correct).

## Security and Privacy Controls
- Access control by role and patient relationship; row‑level filters for multi‑site.
- Field‑level masking for sensitive results (e.g., HIV where jurisdiction dictates).
- Data at rest/in transit encryption, secure key management, regular rotation.
- Detailed audit trails; exportable for compliance review.
- Pseudonymization for analytics and MoH aggregate reporting where required.

## Quality Management
- Conformance with ISO 15189 processes and documentation practices within laboratory context.
- Versioned SOPs embedded as references; QC tracking and instrument maintenance logs.
- Validation: data import validation, rules engine test harness, reference panel verifications after breakpoint updates.

## Operational Considerations
- Breakpoint update workflow: preview impact, staged rollout, re‑interpretation audit, communication to clinicians.
- Downtime: offline order capture and result entry with reconciliation on recovery.
- Monitoring: integration queue depths, retry rates, MoH submission success, antibiogram job durations.

## Glossary
- AST: Antimicrobial Susceptibility Testing.
- S/I/R: Susceptible/Intermediate/Resistant category per breakpoints.
- CLSI/EUCAST: Standards bodies defining AST breakpoints and methods.
- MALDI‑TOF: Mass spectrometry method for organism identification.
- MIC: Minimum Inhibitory Concentration.
- MDRO: Multidrug‑Resistant Organism.
- GLASS: Global Antimicrobial Resistance Surveillance System (WHO).
- LIS/EMR/HIS: Laboratory/Clinical/Electronic Health systems.
- UCUM: Unified Code for Units of Measure.

## Knowledge Gaps
- Jurisdiction and MoH: Which country/region and the exact MoH reporting specifications, formats, and transport requirements?
- Standards: Preferred breakpoint standard (CLSI vs. EUCAST) and target versions; antibiogram standard (e.g., CLSI M39).
- Terminologies: Use of LOINC for tests and RxNorm/ATC for antibiotics—mandated or optional?
- Integrations: Existing LIS/EMR, instrument middleware/vendors, and supported protocols (HL7 v2 flavors, FHIR profiles).
- Workload: Expected volumes (orders/day, isolates/day), concurrency, and SLO targets to finalize performance sizing.
- Multi‑site: Number of facilities, cross‑facility data sharing, segregation requirements.
- Security/Privacy: Regulatory framework in scope (HIPAA/GDPR/PDPA/etc.), data residency constraints, retention policies.
- Reporting: Notifiable organism list, critical value thresholds, alerting escalation policies and on‑call schedules.
- Analytics: Required antibiogram stratifications (unit, age group, specimen type) and de‑duplication rules.
- Languages/Localization: Required UI/report languages and date/number formats.
- Deployment: On‑prem vs. cloud, preferred cloud provider/services, and disaster recovery topology.

