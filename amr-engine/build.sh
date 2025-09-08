#!/bin/bash

# AMR Engine Docker Build Script
# Run this from the amr-engine directory

set -e

echo "🏗️  Building AMR Engine Docker image..."

# Build the main image
docker build -f docker/Dockerfile -t amr-engine:latest .

echo "✅ AMR Engine image built successfully!"

# Build the test image
docker build -f docker/Dockerfile --target test -t amr-engine:test .

echo "✅ AMR Engine test image built successfully!"

# List the images
echo "📦 Built images:"
docker images | grep amr-engine

echo ""
echo "🚀 To run the application:"
echo "   docker run -p 8080:8080 amr-engine:latest"
echo ""
echo "🧪 To run tests:"
echo "   docker run amr-engine:test"
echo ""
echo "📋 To run with docker-compose:"
echo "   docker-compose -f docker/docker-compose.yml up --build"