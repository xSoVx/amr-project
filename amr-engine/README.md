# AMR Classification Engine

[![Version](https://img.shields.io/badge/version-0.1.0-brightgreen.svg)](https://github.com/your-org/amr-engine/releases)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-4285F4?style=flat&logo=opentelemetry&logoColor=white)](https://opentelemetry.io/)
[![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=flat&logo=prometheus&logoColor=white)](https://prometheus.io/)
[![FHIR R4](https://img.shields.io/badge/FHIR_R4-326CE5?style=flat&logo=hl7&logoColor=white)](https://hl7.org/fhir/)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Enterprise-ready microservice** for **Antimicrobial Resistance (AMR) classification** with comprehensive observability, audit logging, and multi-profile FHIR validation. Supports FHIR R4 Bundles, HL7v2 messages, and direct JSON input with EUCAST/CLSI-style rules, returning S/I/R/RR decisions with detailed reasoning and full compliance tracking.

> **⚠️ DISCLAIMER**: This is open-source software provided "AS IS" without warranty of any kind. This software is intended for research and educational purposes only. It should not be used for clinical decision-making or patient care without proper validation, regulatory approval, and oversight by qualified healthcare professionals. Users are solely responsible for ensuring compliance with applicable regulations and guidelines in their jurisdiction.

## 🚀 Quick Start

### Local Development
```bash
# Create virtual environment and install dependencies
python -m venv .venv && . .venv/bin/activate
pip install -e .

# Start the server
uvicorn amr_engine.main:app --host 0.0.0.0 --port 8080

# Access Swagger UI
open http://localhost:8080/docs
```

### Docker
```bash
# Build and run
docker build -f docker/Dockerfile -t amr-engine:latest .
docker run -p 8080:8080 --env-file .env amr-engine:latest

# Or use docker-compose
docker-compose -f docker/docker-compose.yml up --build

# With full observability stack (Jaeger, Prometheus, Grafana)
docker-compose -f docker/docker-compose.observability.yml up --build
```

## 📚 API Documentation

### Interactive Swagger UI
- **Development**: http://localhost:8080/docs
- **Docker**: http://localhost:8081/docs (default docker-compose port)

### API Endpoints

#### 🩺 Health & Monitoring
- `GET /healthz` - Health check endpoint
- `GET /version` - Service version information
- `GET /metrics` - Prometheus metrics

#### 🧬 Classification Endpoints

##### Universal Classification
- `POST /classify` - **Auto-detecting endpoint**
  - Supports FHIR R4 Bundles, HL7v2 messages, and direct JSON
  - Automatically detects input format
  - Most flexible endpoint for integration

##### Format-Specific Endpoints
- `POST /classify/fhir` - **FHIR R4 Bundle/Observations**
  - Dedicated FHIR processing
  - Supports Bundles, Observation arrays, single Observations
  - FHIR-specific validation and error handling

- `POST /classify/hl7v2` - **HL7v2 Messages**
  - Dedicated HL7v2 message processing
  - Parses MSH/OBR/OBX segments
  - Extracts microbiology results

- `POST /rules/dry-run` - **Test Classification Rules**
  - Dry run for testing without metrics impact
  - Useful for rule validation and debugging

#### ⚙️ Administration
- `POST /admin/rules/reload` - Reload classification rules
  - Requires `X-Admin-Token` header
  - Hot-reload rules without service restart

## 💾 Input Formats

### FHIR R4 Bundle Example
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Observation",
        "status": "final",
        "code": {
          "coding": [
            {
              "system": "http://loinc.org",
              "code": "87181-4",
              "display": "Amoxicillin [Susceptibility]"
            }
          ]
        },
        "subject": {
          "reference": "Patient/123"
        },
        "valueQuantity": {
          "value": 4.0,
          "unit": "mg/L"
        },
        "component": [
          {
            "code": {
              "coding": [
                {
                  "system": "http://snomed.info/sct",
                  "code": "264395009",
                  "display": "Microorganism"
                }
              ]
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
        ]
      }
    }
  ]
}
```

### HL7v2 Message Example
```
MSH|^~\&|LAB|FACILITY|EMR|HOSPITAL|20240101120000||ORU^R01|12345|P|2.5
OBR|1|||MICRO^Microbiology|||||||||||||||||||F
OBX|1|ST|ORG^Organism||Escherichia coli||||||F
OBX|2|NM|MIC^Amoxicillin MIC||4.0|mg/L|||||F
```

### Direct JSON Input Example
```json
{
  "organism": "Escherichia coli",
  "antibiotic": "Amoxicillin",
  "method": "MIC",
  "mic_mg_L": 4.0,
  "specimenId": "SPEC-001"
}
```

## 📊 Classification Results

```json
{
  "specimenId": "SPEC-001",
  "organism": "Escherichia coli",
  "antibiotic": "Amoxicillin",
  "method": "MIC",
  "input": {
    "organism": "Escherichia coli",
    "antibiotic": "Amoxicillin",
    "method": "MIC",
    "mic_mg_L": 4.0,
    "specimenId": "SPEC-001"
  },
  "decision": "S",
  "reason": "MIC 4.0 mg/L <= breakpoint 8.0 mg/L",
  "ruleVersion": "EUCAST v2025.1"
}
```

### Decision Categories
- **S** - Susceptible
- **I** - Susceptible, increased exposure  
- **R** - Resistant
- **RR** - Resistant, rare resistance

## 🧪 Testing

```bash
# Run tests
pytest -q --maxfail=1 --disable-warnings

# Run with coverage
pytest --cov=amr_engine --cov-report=html

# Docker test container
docker-compose -f docker/docker-compose.yml run tests
```

## ⚙️ Configuration

### Environment Variables (.env.example)
```bash
# Core Configuration
AMR_RULES_PATH=amr_engine/rules/eucast_v_2025_1.yaml
ADMIN_TOKEN=change-me-in-production
SERVICE_NAME=amr-engine
LOG_LEVEL=INFO
EUST_VER=EUCAST-2025.1

# OpenTelemetry Tracing Configuration
# OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:14268/api/traces
# OTEL_TRACE_SAMPLE_RATE=1.0

# Monitoring and Observability
# PROMETHEUS_METRICS_PORT=9090
# ENABLE_AUDIT_LOGGING=true

# Optional: Custom breakpoint sources
# CLSI_RULES_PATH=amr_engine/rules/clsi_2024.yaml
```

### Docker Environment
```bash
# Docker with environment file
docker run -p 8080:8080 --env-file .env amr-engine:latest

# Docker with inline environment variables
docker run -p 8080:8080 \
  -e AMR_RULES_PATH=amr_engine/rules/eucast_v_2025_1.yaml \
  -e ADMIN_TOKEN=your-secure-token \
  amr-engine:latest
```

## 🔒 Security

- **No secrets in repository** - All sensitive data via environment variables
- **Non-root Docker user** - Container runs with restricted permissions
- **Minimal dependencies** - Reduced attack surface
- **Token-protected admin endpoints** - Secured rule reload functionality
- **Input validation** - Comprehensive request validation and sanitization

## 🏗️ Enterprise Architecture

### Key Components
- **FastAPI Framework** - Modern, fast web framework with automatic OpenAPI
- **Pydantic Models** - Data validation and serialization
- **FHIR Adapter** - FHIR R4 resource parsing and validation
- **HL7v2 Parser** - HL7v2 message segment parsing
- **Rule Engine** - YAML/JSON-based classification rules
- **OpenTelemetry Tracing** - Distributed tracing with Jaeger integration
- **Prometheus Metrics** - Comprehensive domain-specific metrics
- **FHIR AuditEvent Logging** - Compliance-ready audit trails

### Enterprise Features

#### 🔍 **Observability & Monitoring**
- **Distributed Tracing** - OpenTelemetry integration with Jaeger
- **Domain-Specific Metrics** - Classification, terminology, validation, and performance metrics
- **Structured Error Taxonomy** - Actionable error codes with FHIR OperationOutcome integration
- **Real-Time Dashboards** - Grafana integration for comprehensive monitoring

#### 🛡️ **Compliance & Audit**
- **FHIR AuditEvent Generation** - Standards-compliant audit logging
- **Classification Tracking** - Full audit trail for all classification decisions
- **Rule Version Auditing** - Track which rule versions were applied
- **Profile Pack Selection Auditing** - Record tenant-specific profile pack usage

#### 🏥 **Multi-Profile FHIR Validation**
- **IL-Core Support** - Israeli national FHIR implementation guide
- **US-Core Support** - US national FHIR implementation guide  
- **IPS Support** - International Patient Summary profiles
- **Custom Profile Packs** - Support for organization-specific profiles
- **Tenant-Specific Assignment** - Multi-tenant profile pack management
- **Conflict Resolution** - Intelligent priority-based profile selection

#### 🔧 **Rule Management**
- **Startup Validation** - Rules validated against JSON Schema at startup
- **Hot Reload** - Update rules without service restart via `/admin/rules/reload`
- **Version Control** - Rule versions tracked and reported in results
- **Multiple Sources** - Support for EUCAST, CLSI, and custom rule sets
- **Expert Rules Engine** - Intrinsic resistance and combination therapy handling

### Observability Stack

#### 📊 **Metrics & Dashboards**
- **Prometheus** - Time-series metrics collection
- **Grafana** - Real-time dashboards and alerting
- **Custom AMR Metrics** - Classification rates, error rates, terminology coverage

#### 🔍 **Distributed Tracing**
- **Jaeger** - Request flow visualization
- **Service Dependencies** - Cross-service call tracking
- **Performance Profiling** - Latency and bottleneck identification

#### 📝 **Logging & Audit**
- **Structured JSON Logs** - Request ID and classification summary
- **FHIR AuditEvents** - Standards-compliant audit trails
- **Health Checks** - Kubernetes/Docker-ready endpoints
- **Error Tracking** - Comprehensive error categorization

## 🔍 Observability & Monitoring

### Full Stack Deployment
Start the complete observability stack with:

```bash
docker-compose -f docker/docker-compose.observability.yml up --build
```

This provides:

#### 🌐 **Access URLs**
- **AMR Engine**: http://localhost:8080
- **Swagger API Docs**: http://localhost:8080/docs  
- **Jaeger Tracing UI**: http://localhost:16686
- **Prometheus Metrics**: http://localhost:9090
- **Grafana Dashboards**: http://localhost:3000 (admin/admin)

#### 📊 **Key Metrics Available**
- `amr_classifications_total` - Total classifications by decision, organism, antibiotic
- `amr_classification_duration_seconds` - Classification processing time
- `amr_terminology_lookups_total` - Terminology service usage
- `amr_profile_validations_total` - FHIR validation results
- `amr_audit_events_total` - Compliance audit event generation
- `amr_structured_errors_total` - Error categorization and tracking

#### 🔎 **Distributed Tracing**
View request flows through:
1. **Classification Operations** - Complete request lifecycle from input to decision
2. **FHIR Processing** - Bundle parsing, validation, and resource extraction  
3. **Rule Evaluation** - Rule matching and decision logic execution
4. **Terminology Lookups** - Code system validation and mapping
5. **Profile Validation** - Multi-tenant FHIR profile pack validation

## 🚢 Deployment

### Kubernetes Example
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: amr-engine
spec:
  replicas: 3
  selector:
    matchLabels:
      app: amr-engine
  template:
    metadata:
      labels:
        app: amr-engine
    spec:
      containers:
      - name: amr-engine
        image: amr-engine:latest
        ports:
        - containerPort: 8080
        env:
        - name: AMR_RULES_PATH
          value: "amr_engine/rules/eucast_v_2025_1.yaml"
        - name: ADMIN_TOKEN
          valueFrom:
            secretKeyRef:
              name: amr-secrets
              key: admin-token
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Production Considerations

#### 🏥 **Healthcare & Compliance**
- **FHIR R4 Compliance** - Full conformance with FHIR R4 specification
- **Multi-Profile Support** - IL-Core, US-Core, IPS, and custom profiles
- **Audit Trail Generation** - FHIR AuditEvent resources for regulatory compliance
- **Tenant Isolation** - Multi-tenant profile pack assignment and validation
- **Data Privacy** - No patient data persistence, stateless processing

#### 🔧 **Operational Excellence**
- **Environment-Specific Rules** - Use appropriate rule files per environment
- **Resource Limits** - Configure memory and CPU limits for containers
- **Monitoring & Alerting** - Set up Grafana alerts for error rates and performance
- **Backup & Recovery** - Implement proper backup strategy for rule files
- **Secrets Management** - Use Kubernetes secrets or vault for ADMIN_TOKEN
- **High Availability** - Deploy with multiple replicas and health checks

#### 🔍 **Observability Requirements**
- **Distributed Tracing** - Configure OTEL_EXPORTER_OTLP_ENDPOINT for trace collection
- **Metrics Collection** - Ensure Prometheus can scrape /metrics endpoint
- **Log Aggregation** - Collect structured JSON logs for analysis
- **Dashboard Configuration** - Import Grafana dashboards for AMR-specific metrics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## ⚖️ Legal Disclaimer & Limitations

### Open Source Software Notice
This AMR Classification Engine is **open-source software** released under the MIT License. It is provided free of charge for research, educational, and development purposes.

### Medical Device and Clinical Use Warning
> **🚨 IMPORTANT**: This software is **NOT** a medical device and has **NOT** been approved by any regulatory authority (FDA, CE, Health Canada, TGA, etc.) for clinical use. 

#### Restrictions:
- **❌ Not for clinical decision-making**: Do not use for patient diagnosis, treatment decisions, or clinical care
- **❌ Not for production healthcare systems**: Requires validation and regulatory approval before clinical deployment  
- **❌ No medical liability coverage**: Authors and contributors assume no responsibility for medical outcomes
- **❌ No accuracy guarantees**: Classification results may contain errors and require expert review

#### Intended Use:
- ✅ **Research and development** of AMR classification systems
- ✅ **Educational purposes** for understanding FHIR, HL7v2, and AMR guidelines
- ✅ **Software development** and integration testing
- ✅ **Academic research** with proper validation and oversight

### Regulatory Compliance
Users deploying this software must ensure compliance with:
- Local healthcare regulations and data protection laws
- Medical device regulations if used in clinical settings
- Laboratory information system requirements
- HIPAA, GDPR, or equivalent data privacy regulations
- Institutional review board (IRB) approval for research use

### Professional Responsibility
Healthcare professionals using this software must:
- Validate all results against established laboratory procedures
- Maintain appropriate quality control measures
- Follow institutional protocols for antimicrobial resistance testing
- Ensure proper oversight by qualified microbiologists or infectious disease specialists

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

**MIT License Summary**: This software is provided "AS IS", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement.

