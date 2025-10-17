#!/bin/bash

# Docker Load Script for MCP Atlassian
# This script imports a Docker image for offline deployment

set -e

# Configuration
EXPORT_FILE=${1:-""}
IMAGE_NAME=${2:-""}

if [ -z "${EXPORT_FILE}" ]; then
    echo "❌ Error: Export file path required"
    echo "Usage: $0 <export_file.tar> [image_name]"
    echo ""
    echo "Example: $0 ./exports/mcp-atlassian_latest_20241017_143000.tar"
    echo "Example: $0 ./exports/mcp-atlassian_latest_20241017_143000.tar my-custom-name"
    exit 1
fi

echo "📦 Loading Docker image from: ${EXPORT_FILE}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running or not accessible"
    exit 1
fi

# Check if the export file exists
if [ ! -f "${EXPORT_FILE}" ]; then
    echo "❌ Error: Export file not found: ${EXPORT_FILE}"
    exit 1
fi

# Get file size
FILE_SIZE=$(ls -lh "${EXPORT_FILE}" | awk '{print $5}')
echo "📊 Export file size: ${FILE_SIZE}"

# Load the Docker image
echo "📥 Loading Docker image..."
docker load --input "${EXPORT_FILE}"

# Determine the loaded image name and tag
if [ -n "${IMAGE_NAME}" ]; then
    # Tag the loaded image with custom name
    LOADED_IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}}" | head -1)
    docker tag "${LOADED_IMAGE}" "${IMAGE_NAME}:latest"
    FINAL_IMAGE="${IMAGE_NAME}:latest"
    echo "🏷️  Tagged image as: ${FINAL_IMAGE}"
else
    FINAL_IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}}" | head -1)
fi

# Verify the image was loaded successfully
if docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep -q "$(echo ${FINAL_IMAGE} | cut -d':' -f1)"; then
    echo "✅ Successfully loaded image"
    echo "📊 Loaded image details:"
    docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep "$(echo ${FINAL_IMAGE} | cut -d':' -f1)"
else
    echo "❌ Error: Failed to load image"
    exit 1
fi

# Check for metadata file
METADATA_FILE="${EXPORT_FILE%.tar}_metadata.json"
if [ -f "${METADATA_FILE}" ]; then
    echo "📋 Found metadata file: ${METADATA_FILE}"
    echo "📄 Metadata contents:"
    cat "${METADATA_FILE}" | python3 -m json.tool 2>/dev/null || cat "${METADATA_FILE}"
fi

echo ""
echo "🎯 Load completed successfully!"
echo ""
echo "💡 To run the container:"
echo "   docker run --rm -it -p 8000:8000 ${FINAL_IMAGE}"
echo ""
echo "💡 To run with environment file:"
echo "   docker run --rm -it -p 8000:8000 --env-file .env ${FINAL_IMAGE}"
echo ""
echo "💡 To run as a daemon:"
echo "   docker run -d -p 8000:8000 --name mcp-atlassian --env-file .env ${FINAL_IMAGE}"