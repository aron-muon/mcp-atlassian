#!/bin/bash

# Docker Save Script for MCP Atlassian
# This script exports a Docker image for offline deployment

set -e

# Configuration
IMAGE_NAME=${1:-"mcp-atlassian"}
IMAGE_TAG=${2:-"latest"}
OUTPUT_DIR=${3:-"./exports"}
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

# Create timestamp for the export file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
EXPORT_FILE="${OUTPUT_DIR}/${IMAGE_NAME}_${IMAGE_TAG}_${TIMESTAMP}.tar"

echo "📦 Exporting Docker image: ${FULL_IMAGE_NAME}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running or not accessible"
    exit 1
fi

# Check if the image exists
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${FULL_IMAGE_NAME}$"; then
    echo "❌ Error: Image ${FULL_IMAGE_NAME} not found"
    echo "💡 Run './scripts/docker-build.sh ${IMAGE_NAME} ${IMAGE_TAG}' first"
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "${OUTPUT_DIR}"

# Get image information
IMAGE_SIZE=$(docker images --format "{{.Size}}" "${FULL_IMAGE_NAME}")
IMAGE_ID=$(docker images --format "{{.ID}}" "${FULL_IMAGE_NAME}")

echo "📊 Image Information:"
echo "   Name: ${FULL_IMAGE_NAME}"
echo "   ID: ${IMAGE_ID}"
echo "   Size: ${IMAGE_SIZE}"
echo "   Export file: ${EXPORT_FILE}"

# Save the Docker image
echo "💾 Saving Docker image to tar file..."
docker save \
    --output "${EXPORT_FILE}" \
    "${FULL_IMAGE_NAME}"

# Verify the export file was created
if [ -f "${EXPORT_FILE}" ]; then
    FILE_SIZE=$(ls -lh "${EXPORT_FILE}" | awk '{print $5}')
    echo "✅ Successfully exported image"
    echo "📊 Export file size: ${FILE_SIZE}"
    echo "📍 Location: ${EXPORT_FILE}"
else
    echo "❌ Error: Failed to export image"
    exit 1
fi

# Create a metadata file with export information
METADATA_FILE="${OUTPUT_DIR}/${IMAGE_NAME}_${IMAGE_TAG}_${TIMESTAMP}_metadata.json"
cat > "${METADATA_FILE}" << EOF
{
    "image_name": "${IMAGE_NAME}",
    "image_tag": "${IMAGE_TAG}",
    "full_image_name": "${FULL_IMAGE_NAME}",
    "image_id": "${IMAGE_ID}",
    "image_size": "${IMAGE_SIZE}",
    "export_file": "${EXPORT_FILE}",
    "export_timestamp": "${TIMESTAMP}",
    "export_date": "$(date -Iseconds)",
    "docker_version": "$(docker --version)"
}
EOF

echo "📋 Metadata file created: ${METADATA_FILE}"

echo ""
echo "🎯 Export completed successfully!"
echo ""
echo "📋 To transfer to offline system:"
echo "   1. Copy the tar file: ${EXPORT_FILE}"
echo "   2. Copy the metadata file: ${METADATA_FILE}"
echo "   3. On the offline system, run: ./scripts/docker-load.sh ${EXPORT_FILE}"
echo ""
echo "💡 Alternative: Copy the entire ${OUTPUT_DIR} directory"