# AMR Classification Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

Production-ready microservice for **Antimicrobial Resistance (AMR) classification**. Supports multiple input formats including FHIR R4 Bundles, HL7v2 messages, and direct JSON input. Applies EUCAST/CLSI-style rules and returns S/I/R/RR decisions with detailed reasoning.

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
# Rules configuration
AMR_RULES_PATH=amr_engine/rules/eucast_v_2025_1.yaml

# Security
ADMIN_TOKEN=change-me-in-production

# Service configuration  
SERVICE_NAME=amr-engine
LOG_LEVEL=INFO
EUCAST_VER=2025.1

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

## 🏗️ Architecture

### Key Components
- **FastAPI Framework** - Modern, fast web framework with automatic OpenAPI
- **Pydantic Models** - Data validation and serialization
- **FHIR Adapter** - FHIR R4 resource parsing and validation
- **HL7v2 Parser** - HL7v2 message segment parsing
- **Rule Engine** - YAML/JSON-based classification rules
- **Prometheus Metrics** - Built-in monitoring and observability

### Rule Management
- **Startup Validation** - Rules validated against JSON Schema at startup
- **Hot Reload** - Update rules without service restart via `/admin/rules/reload`
- **Version Control** - Rule versions tracked and reported in results
- **Multiple Sources** - Support for EUCAST, CLSI, and custom rule sets

### Logging & Monitoring
- **Structured JSON Logs** - Request ID and classification summary
- **Prometheus Metrics** - Classification counters by decision type
- **Health Checks** - Kubernetes/Docker-ready health endpoints
- **Performance Monitoring** - Request timing and error tracking

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
- Use environment-specific rule files
- Configure appropriate resource limits
- Set up proper monitoring and alerting
- Implement proper backup and recovery for rule files
- Use secrets management for ADMIN_TOKEN

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

