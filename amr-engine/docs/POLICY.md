# AMR Engine Policy Configuration

The AMR Engine supports comprehensive policy-based configuration for access control, validation rules, and operational settings through `policy.json` files.

## Overview

Policy files use a structured JSON format with schema validation to ensure configuration correctness. They control:

- **Access Control**: Authentication methods, authorization rules, RBAC
- **Validation**: FHIR profile validation, classification rules
- **Operational**: Rate limiting, caching, audit settings
- **Security**: HTTPS enforcement, CORS, headers

## Policy File Structure

```json
{
  "version": "1.0.0",
  "metadata": {
    "name": "My Policy",
    "author": "AMR Team",
    "description": "Policy description"
  },
  "accessControl": { ... },
  "validation": { ... },
  "operational": { ... },
  "security": { ... }
}
```

## Schema Validation

All policy files are validated against the JSON schema located at `schemas/policy-schema.json`.

### Validation Methods

1. **JSON Schema Validation**: Ensures structural correctness and data types
2. **Pydantic Model Validation**: Provides additional business logic validation
3. **Runtime Policy Validation**: Validates policy consistency at startup

### Validation Command

```bash
python -m amr_engine.core.policy validate /path/to/policy.json
```

## Configuration Sections

### Access Control

Controls authentication and authorization:

```json
{
  "accessControl": {
    "authentication": {
      "required": true,
      "methods": ["oauth2", "mtls", "static-token"],
      "oauth2": {
        "enabled": true,
        "issuerUrl": "https://auth.example.com",
        "audience": "amr-engine",
        "requiredScopes": ["amr:classify"]
      }
    },
    "authorization": {
      "rbac": {
        "enabled": true,
        "roles": {
          "classifier": {
            "description": "Standard classification user",
            "permissions": ["classify:read", "classify:write", "health:read"]
          },
          "admin": {
            "permissions": [
              "classify:read", "classify:write", 
              "admin:rules:reload", "admin:metrics:read", "health:read"
            ]
          }
        }
      }
    }
  }
}
```

#### Supported Authentication Methods

- `static-token`: Simple admin token (development only)
- `oauth2`: OAuth 2.0 / OpenID Connect
- `mtls`: Mutual TLS authentication
- `basic`: HTTP Basic authentication

#### RBAC Permissions

- `classify:read`: Read classification results
- `classify:write`: Submit classification requests
- `admin:rules:reload`: Reload classification rules
- `admin:metrics:read`: Access metrics endpoints
- `health:read`: Access health check endpoints

### Validation Policies

Controls data validation and processing:

```json
{
  "validation": {
    "fhir": {
      "strictValidation": true,
      "allowedProfiles": ["IL-Core", "US-Core", "IPS"],
      "defaultProfile": "US-Core",
      "validateReferences": true
    },
    "classification": {
      "requireSpecimen": true,
      "allowMissingValues": false,
      "validationLevel": "strict",
      "maxBatchSize": 100
    }
  }
}
```

#### FHIR Profile Packs

- `Base`: Standard FHIR R4 profiles
- `IL-Core`: Israeli Core Implementation Guide
- `US-Core`: US Core Implementation Guide
- `IPS`: International Patient Summary

#### Validation Levels

- `strict`: Require all fields, strict type checking
- `standard`: Standard validation with some flexibility
- `permissive`: Minimal validation, maximum compatibility

### Operational Policies

Controls runtime behavior:

```json
{
  "operational": {
    "rateLimit": {
      "enabled": true,
      "requestsPerMinute": 60,
      "burstSize": 10,
      "perTenant": true
    },
    "caching": {
      "enabled": true,
      "ruleCacheTtl": 3600,
      "terminologyCacheTtl": 7200
    },
    "audit": {
      "enabled": true,
      "auditAllClassifications": true,
      "retentionDays": 2555
    }
  }
}
```

### Security Policies

Controls security settings:

```json
{
  "security": {
    "encryption": {
      "enforceHttps": true,
      "hsts": true
    },
    "cors": {
      "enabled": true,
      "allowedOrigins": ["https://app.example.com"],
      "allowedMethods": ["GET", "POST"],
      "allowCredentials": true
    },
    "headers": {
      "removeServerHeader": true,
      "customHeaders": {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY"
      }
    }
  }
}
```

## Policy Loading and Merging

### Single Policy File

```bash
export AMR_POLICY_PATH="/etc/amr-engine/policy.json"
```

### Multiple Policy Files

```bash
export AMR_POLICY_PATHS="/etc/amr-engine/base-policy.json,/etc/amr-engine/site-policy.json"
```

When multiple policies are specified, they are merged with later policies overriding earlier ones.

### Environment-Specific Policies

```bash
# Base policy
/etc/amr-engine/base-policy.json

# Environment override
/etc/amr-engine/production-policy.json
/etc/amr-engine/development-policy.json
```

## Examples

### Development Policy

See `examples/policy.json` for a development-friendly configuration with:
- Static token authentication
- Permissive validation
- No rate limiting
- Basic audit logging

### Production Policy

For production environments, use:
- OAuth2 or mTLS authentication
- Strict FHIR validation
- Rate limiting enabled
- Comprehensive audit logging
- HTTPS enforcement

## Validation Tools

### CLI Validation

```bash
# Validate a single policy file
python -c "
from amr_engine.core.policy import PolicyValidator
from pathlib import Path

validator = PolicyValidator()
is_valid = validator.validate_policy_file(Path('examples/policy.json'))
print(f'Policy valid: {is_valid}')
"

# Get validation errors
python -c "
import json
from amr_engine.core.policy import PolicyValidator

validator = PolicyValidator()
with open('examples/policy.json') as f:
    data = json.load(f)

errors = validator.get_validation_errors(data)
if errors:
    for error in errors:
        print(f'ERROR: {error}')
else:
    print('Policy is valid')
"
```

### Programmatic Validation

```python
from amr_engine.core.policy import PolicyValidator, PolicyManager
from pathlib import Path

# Validate single file
validator = PolicyValidator()
is_valid = validator.validate_policy_file(Path("policy.json"))

# Load and manage policies
manager = PolicyManager([Path("policy.json")])
policy = manager.get_policy("My Policy Name")
```

## Best Practices

1. **Version Control**: Always specify a policy version
2. **Validation**: Validate policies before deployment
3. **Environment Separation**: Use separate policies for dev/staging/prod
4. **Principle of Least Privilege**: Grant minimum required permissions
5. **Audit Trails**: Enable comprehensive audit logging in production
6. **Regular Review**: Periodically review and update policies
7. **Schema Evolution**: Test policy compatibility when upgrading

## Troubleshooting

### Common Validation Errors

- **Missing required fields**: Ensure `version` and `metadata` are present
- **Invalid enum values**: Check that profile names, permissions match allowed values
- **Type mismatches**: Ensure boolean/integer fields have correct types
- **Pattern violations**: Role names must match `^[a-zA-Z][a-zA-Z0-9_-]*$`

### Policy Loading Issues

- Check file permissions and paths
- Verify JSON syntax with a validator
- Review logs for specific error messages
- Ensure schema file is accessible

### Runtime Policy Conflicts

- Multiple policies with same name (last loaded wins)
- Conflicting authentication methods
- Incompatible validation settings

## Migration Guide

When upgrading AMR Engine versions:

1. Check for schema changes in `schemas/policy-schema.json`
2. Validate existing policies against new schema
3. Update deprecated configuration options
4. Test policy enforcement in staging environment
5. Update documentation and training materials