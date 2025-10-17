#!/bin/bash

# Docker Build Script for MCP Atlassian
# This script builds the Docker image for offline deployment

set -e

# Configuration
IMAGE_NAME=${1:-"mcp-atlassian"}
IMAGE_TAG=${2:-"latest"}
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

echo "🐳 Building Docker image: ${FULL_IMAGE_NAME}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running or not accessible"
    exit 1
fi

# Build the Docker image
echo "📦 Building image using Dockerfile..."
docker build \
    --tag "${FULL_IMAGE_NAME}" \
    .

# Verify the image was built successfully
if docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep -q "${IMAGE_NAME}:${IMAGE_TAG}"; then
    echo "✅ Successfully built ${FULL_IMAGE_NAME}"
    echo "📊 Image details:"
    docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep "${IMAGE_NAME}:${IMAGE_TAG}"
else
    echo "❌ Error: Failed to build image"
    exit 1
fi

echo ""
echo "🎯 Build completed successfully!"
echo "💡 To save the image for offline deployment, run:"
echo "   ./scripts/docker-save.sh ${IMAGE_NAME} ${IMAGE_TAG}"
echo ""
echo "💡 To run the container:"
echo "   docker run --rm -it -p 8000:8000 ${FULL_IMAGE_NAME}"
echo ""
echo "💡 To run with environment file:"
echo "   docker run --rm -it -p 8000:8000 --env-file .env ${FULL_IMAGE_NAME}"