#!/bin/bash

# Test script for Docker setup
set -e

echo "=== AMR Engine Docker Test Script ==="

# Navigate to the amr-engine directory  
cd "$(dirname "$0")/.."

echo "1. Testing Docker build..."
docker build -f docker/Dockerfile --target app -t amr-engine:latest .

echo "2. Testing Docker compose configuration..."
cd docker
docker-compose config > /dev/null && echo "✅ docker-compose.yml is valid"
docker-compose -f docker-compose.observability.yml config > /dev/null && echo "✅ docker-compose.observability.yml is valid"

echo "3. Testing quick container startup..."
docker run --rm -d --name amr-test -p 8082:8080 \
  -e AMR_RULES_PATH=amr_engine/rules/eucast_v_2025_1.yaml \
  amr-engine:latest

# Wait for container to start
echo "Waiting for container to start..."
sleep 10

# Test health endpoint
if curl -f http://localhost:8082/health > /dev/null 2>&1; then
  echo "✅ Health endpoint is responding"
else
  echo "❌ Health endpoint failed"
fi

# Clean up
docker stop amr-test

echo "4. Testing compose services..."
docker-compose up -d

# Wait for services
sleep 15

# Test API endpoint
if curl -f http://localhost:8081/health > /dev/null 2>&1; then
  echo "✅ Compose API service is responding"
else
  echo "❌ Compose API service failed"
fi

# Clean up
docker-compose down

echo "=== Docker tests completed ==="