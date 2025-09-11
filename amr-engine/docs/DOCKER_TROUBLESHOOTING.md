# Docker Troubleshooting Guide

## Quick Fixes for Common Docker Issues

### 🏗️ Building the Image

#### 1. **Directory Structure Issue**
Make sure you're in the `amr-engine` directory when building:
```bash
cd amr-engine
docker build -f docker/Dockerfile -t amr-engine:latest .
```

#### 2. **Missing Dependencies**
If you get cryptography compilation errors:
```bash
# On Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y gcc g++ libffi-dev libssl-dev

# On Alpine
apk add --no-cache gcc g++ libffi-dev openssl-dev musl-dev

# On macOS
brew install openssl libffi
```

#### 3. **Use the Build Scripts**
Use the provided build scripts for easier building:
```bash
# Linux/macOS
./build.sh

# Windows PowerShell
./build.ps1
```

### 🚀 Running the Container

#### 1. **Port Binding Issues**
If port 8080 is in use:
```bash
docker run -p 8081:8080 amr-engine:latest
```

#### 2. **Environment Variables**
Set required environment variables:
```bash
docker run -p 8080:8080 \
  -e ADMIN_TOKEN=your-secure-token \
  -e LOG_LEVEL=DEBUG \
  amr-engine:latest
```

#### 3. **Health Check Failures**
Check if the health endpoint is working:
```bash
# After container starts, test health endpoint
curl http://localhost:8080/health
```

### 🐛 Debugging Container Issues

#### 1. **Check Container Logs**
```bash
docker logs <container-id>
```

#### 2. **Interactive Shell**
Debug inside the container:
```bash
docker run -it --entrypoint /bin/bash amr-engine:latest
```

#### 3. **Validate Imports Before Building**
Run the validation script to catch import errors:
```bash
cd amr-engine
python validate_imports.py
```

### 📝 Docker Compose Issues

#### 1. **Build Context Problems**
Make sure docker-compose.yml has correct context:
```yaml
services:
  api:
    build:
      context: .  # This should be the amr-engine directory
      dockerfile: docker/Dockerfile
```

#### 2. **Run with docker-compose**
```bash
cd amr-engine
docker-compose -f docker/docker-compose.yml up --build
```

### 🔧 Common Error Solutions

#### Error: "No module named 'amr_engine'"
- **Cause**: Incorrect build context or missing __init__.py files
- **Solution**: Ensure you're building from the amr-engine directory

#### Error: "Failed building wheel for cryptography"
- **Cause**: Missing system dependencies for cryptography
- **Solution**: Install system dependencies (see "Missing Dependencies" above)

#### Error: "Permission denied" on health check
- **Cause**: Container running as non-root user can't access health endpoint
- **Solution**: This is normal behavior, the health check should still work

#### Error: "Address already in use" 
- **Cause**: Port 8080 is already occupied
- **Solution**: Use different port: `docker run -p 8081:8080 amr-engine:latest`

### 📊 Testing the Build

#### 1. **Quick Smoke Test**
```bash
# Test the main endpoints
curl http://localhost:8080/health
curl http://localhost:8080/docs
curl http://localhost:8080/version
```

#### 2. **Run Tests in Container**
```bash
docker run amr-engine:test
```

#### 3. **Manual Classification Test**
```bash
curl -X POST "http://localhost:8080/classify" \
  -H "Content-Type: application/json" \
  -d '{
    "organism": "Escherichia coli",
    "antibiotic": "Amoxicillin", 
    "method": "MIC",
    "mic_mg_L": 4.0,
    "specimenId": "TEST-001"
  }'
```

### 🆘 Getting Help

If you're still having issues:

1. **Check the logs**: `docker logs <container-name>`
2. **Validate environment**: Run `python validate_imports.py` 
3. **Check system resources**: Ensure sufficient RAM/disk space
4. **Try building test image**: `docker build --target test -t amr-engine:test .`

### 🏷️ Build Info

Current build requirements:
- **Python**: 3.11+
- **Docker**: 20.10+
- **Memory**: 2GB+ available
- **Disk**: 5GB+ free space

For additional help, check the main README.md or container logs.