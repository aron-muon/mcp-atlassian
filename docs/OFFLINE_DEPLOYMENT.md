# Offline Docker Deployment Guide

This guide provides step-by-step instructions for building and deploying the MCP Atlassian Docker image in offline environments.

## Overview

The offline deployment process involves:
1. Building the Docker image on an internet-connected system
2. Exporting the image as a portable tar file
3. Transferring the image to the offline system
4. Loading and running the container

## Prerequisites

### Build System Requirements
- Docker installed and running
- Access to the internet (for building dependencies)
- Sufficient disk space for the Docker image (typically 500MB-1GB)

### Target System Requirements
- Docker installed and running
- No internet access required
- Sufficient disk space for the imported image
- Configuration files prepared for Atlassian credentials

## Quick Start

### 1. Build the Docker Image

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd mcp-atlassian

# Build the Docker image
./scripts/docker-build.sh mcp-atlassian latest
```

### 2. Export the Image

```bash
# Export the image for offline deployment
./scripts/docker-save.sh mcp-atlassian latest ./exports
```

This creates:
- `./exports/mcp-atlassian_latest_<timestamp>.tar` - The Docker image
- `./exports/mcp-atlassian_latest_<timestamp>_metadata.json` - Image metadata

### 3. Transfer to Offline System

Copy the exported files to the offline system using your preferred method:
- USB drive or external storage
- Network file share
- Air-gapped network transfer
- Physical media transfer

### 4. Load and Run on Offline System

```bash
# Load the Docker image
./scripts/docker-load.sh ./exports/mcp-atlassian_latest_<timestamp>.tar

# Run with environment configuration
docker run --rm -it -p 8000:8000 --env-file .env mcp-atlassian:latest
```

## Detailed Instructions

### Building the Image

The Docker build script creates a multi-stage image that includes all dependencies:

```bash
# Build with custom name and tag
./scripts/docker-build.sh my-mcp-atlassian v1.0

# Build with default settings
./scripts/docker-build.sh
```

The build process:
1. Downloads the base Alpine Linux image
2. Installs Python and uv package manager
3. Builds and installs all project dependencies
4. Creates a minimal runtime image with only necessary components

### Exporting for Offline Use

The export script creates a portable tar file containing all Docker layers:

```bash
# Basic export
./scripts/docker-save.sh mcp-atlassian latest

# Export to specific directory
./scripts/docker-save.sh mcp-atlassian latest /path/to/exports

# Export custom image
./scripts/docker-save.sh my-mcp-atlassian v1.0 ./offline-exports
```

Export features:
- Creates timestamped files for easy version tracking
- Generates metadata JSON with image information
- Reports file sizes for transfer planning
- Validates the export process

### Transferring Files

The generated files are:
- **Docker Image**: `<image_name>_<tag>_<timestamp>.tar` (typically 500MB-1GB)
- **Metadata**: `<image_name>_<tag>_<timestamp>_metadata.json` (few KB)

Transfer methods:
- **USB Drive**: Copy files directly to USB storage
- **Network Share**: Place on shared network location
- **SCP/SFTP**: Secure file transfer for networked systems
- **Physical Media**: Use external drives or media

### Loading on Offline System

```bash
# Load with automatic image naming
./scripts/docker-load.sh ./exports/mcp-atlassian_latest_20241017_143000.tar

# Load with custom image name
./scripts/docker-load.sh ./exports/mcp-atlassian_latest_20241017_143000.tar my-offline-mcp
```

The load process:
- Validates Docker daemon availability
- Checks export file integrity
- Loads all image layers into Docker
- Optionally tags the image with custom name
- Verifies successful import

## Configuration

### Environment Variables

Create an `.env` file with your Atlassian configuration:

```bash
# Copy the example template
cp .env.example .env

# Edit with your configuration
nano .env
```

Required variables for basic usage:

```env
# Jira Configuration
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token

# Confluence Configuration
CONFLUENCE_URL=https://your-domain.atlassian.net
CONFLUENCE_USERNAME=your-email@company.com
CONFLUENCE_API_TOKEN=your-api-token
```

### Authentication Methods

The container supports multiple authentication methods:

1. **OAuth 2.0 (Cloud)**: Configure with OAuth variables
2. **Personal Access Tokens**: Preferred for Server/Data Center
3. **Basic Authentication**: Email + API token
4. **Header-Based Authentication**: For reverse proxy setups

See the main documentation for complete authentication options.

### Running the Container

#### Basic Development Run
```bash
docker run --rm -it -p 8000:8000 mcp-atlassian:latest
```

#### Production Run with Environment File
```bash
docker run -d \
  --name mcp-atlassian \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  mcp-atlassian:latest
```

#### Header-Based Authentication
```bash
# Run container (no environment variables needed for auth)
docker run -d \
  --name mcp-atlassian \
  --restart unless-stopped \
  -p 8000:8000 \
  mcp-atlassian:latest

# Send requests with authentication headers
curl -H "Authorization: Bearer <oauth_token>" \
     -H "X-Atlassian-Cloud-Id: <cloud_id>" \
     http://localhost:8000/mcp
```

## Troubleshooting

### Build Issues

**Error: Docker daemon not running**
```bash
# Start Docker service
sudo systemctl start docker
# or on macOS/Windows: Start Docker Desktop
```

**Error: Insufficient disk space**
```bash
# Clean up Docker images
docker system prune -a
# Remove specific images
docker rmi <image_name>
```

### Export/Import Issues

**Error: Export file not found**
```bash
# Verify file exists
ls -la ./exports/
# Check file permissions
chmod 644 <export_file.tar>
```

**Error: Docker load fails**
```bash
# Check file integrity
file <export_file.tar>
# Verify Docker daemon
docker info
```

### Runtime Issues

**Error: Authentication failures**
1. Verify `.env` file contains correct credentials
2. Check network connectivity to Atlassian instances
3. Validate API token permissions
4. Review authentication method compatibility

**Error: Port conflicts**
```bash
# Use different port
docker run -p 8080:8000 mcp-atlassian:latest

# Check port usage
netstat -tulpn | grep 8000
```

**Error: Container exits immediately**
```bash
# Check container logs
docker logs <container_id>

# Run with interactive mode for debugging
docker run --rm -it --entrypoint /bin/sh mcp-atlassian:latest
```

## Advanced Usage

### Custom Docker Compose

Create a `docker-compose.yml` for production deployments:

```yaml
version: '3.8'

services:
  mcp-atlassian:
    image: mcp-atlassian:latest
    container_name: mcp-atlassian
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Environment Overrides

For containerized deployments with OAuth proxy:

```bash
docker run -d \
  --name mcp-atlassian \
  -p 8000:8000 \
  -e IGNORE_HEADER_AUTH=true \
  --env-file .env \
  mcp-atlassian:latest
```

### Performance Tuning

```bash
# Increase memory limits
docker run -d \
  --name mcp-atlassian \
  --memory=1g \
  --memory-swap=2g \
  -p 8000:8000 \
  --env-file .env \
  mcp-atlassian:latest

# Set CPU limits
docker run -d \
  --name mcp-atlassian \
  --cpus=1.0 \
  -p 8000:8000 \
  --env-file .env \
  mcp-atlassian:latest
```

## Security Considerations

1. **Credential Management**: Store sensitive configuration in secure environment files
2. **Network Access**: Limit container network exposure if possible
3. **File Permissions**: Restrict access to configuration files
4. **Image Scanning**: Scan Docker images for vulnerabilities before deployment
5. **Container Hardening**: Use minimal base images and limit container capabilities

## Support

For issues related to:
- **Build/Export Problems**: Check Docker installation and disk space
- **Import Problems**: Verify file integrity and Docker daemon
- **Runtime Issues**: Review configuration and logs
- **Authentication**: Validate credentials and network connectivity

Refer to the main project documentation for additional support information.