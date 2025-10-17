# Offline Docker Deployment for MCP Atlassian

This directory contains the complete offline deployment solution for MCP Atlassian Docker containers.

## 🚀 Quick Start

1. **Build the Docker image:**
   ```bash
   ./scripts/docker-build.sh mcp-atlassian latest
   ```

2. **Export for offline deployment:**
   ```bash
   ./scripts/docker-save.sh mcp-atlassian latest ./exports
   ```

3. **Transfer to offline system and load:**
   ```bash
   ./scripts/docker-load.sh ./exports/mcp-atlassian_latest_*.tar
   ```

4. **Configure and run:**
   ```bash
   cp .env.offline .env
   # Edit .env with your credentials
   docker run -d -p 8000:8000 --env-file .env mcp-atlassian:latest
   ```

## 📁 Files Overview

### Scripts
- `scripts/docker-build.sh` - Builds the Docker image locally
- `scripts/docker-save.sh` - Exports image as portable tar file
- `scripts/docker-load.sh` - Imports image on offline system

### Configuration
- `.env.offline` - Environment template for offline deployment
- `.env.example` - Full example with all configuration options

### Documentation
- `docs/OFFLINE_DEPLOYMENT.md` - Comprehensive deployment guide
- `README_OFFLINE.md` - This quick start guide

## 🔧 Detailed Process

### Build System Requirements
- Docker installed and running
- Internet access for downloading base images and dependencies
- ~2GB free disk space for build process

### Target System Requirements
- Docker installed and running
- No internet access required
- ~1GB free disk space for imported image
- Proper environment configuration

### Step-by-Step Instructions

#### 1. Building the Image
```bash
# Clone the repository
git clone <repository-url>
cd mcp-atlassian

# Build with default settings
./scripts/docker-build.sh

# Or build with custom name/tag
./scripts/docker-build.sh my-mcp-atlassian v1.0
```

The build process:
- Downloads Alpine Linux base image
- Installs Python 3.10 and uv package manager
- Builds all project dependencies from pyproject.toml
- Creates minimal runtime image
- Cleans up build artifacts

#### 2. Exporting for Offline Use
```bash
# Export to default ./exports directory
./scripts/docker-save.sh mcp-atlassian latest

# Export to custom directory
./scripts/docker-save.sh mcp-atlassian latest /path/to/exports

# Export custom image
./scripts/docker-save.sh my-mcp-atlassian v1.0 ./offline-bundle
```

This creates:
- `<image>_<tag>_<timestamp>.tar` - Complete Docker image
- `<image>_<tag>_<timestamp>_metadata.json` - Image information

#### 3. Transfer Files
Copy the exported files to the offline system:
- USB drive or external storage
- Network file share
- Air-gapped network transfer
- Any physical media transfer method

#### 4. Loading on Offline System
```bash
# Load with automatic naming
./scripts/docker-load.sh ./exports/mcp-atlassian_latest_*.tar

# Load with custom name
./scripts/docker-load.sh ./exports/mcp-atlassian_latest_*.tar my-offline-mcp
```

#### 5. Configuration and Deployment

**Basic Configuration:**
```bash
# Copy the offline template
cp .env.offline .env

# Edit with your credentials
nano .env
```

**Run Container:**
```bash
# Development run
docker run --rm -it -p 8000:8000 --env-file .env mcp-atlassian:latest

# Production run
docker run -d \
  --name mcp-atlassian \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  mcp-atlassian:latest
```

## 🛠️ Testing the Build Process

To test the build process locally:

```bash
# Test the complete build and export
./scripts/docker-build.sh test-mcp-atlassian test
./scripts/docker-save.sh test-mcp-atlassian test ./test-exports

# Verify the export file
ls -la ./test-exports/

# Test loading (if Docker available)
./scripts/docker-load.sh ./test-exports/test-mcp-atlassian_test_*.tar test-loaded
```

## 📋 Configuration Examples

### Atlassian Cloud (API Token)
```env
JIRA_URL=https://your-company.atlassian.net
JIRA_USERNAME=your.email@company.com
JIRA_API_TOKEN=your_api_token

CONFLUENCE_URL=https://your-company.atlassian.net/wiki
CONFLUENCE_USERNAME=your.email@company.com
CONFLUENCE_API_TOKEN=your_api_token
```

### Atlassian Server/DC (Personal Access Token)
```env
JIRA_URL=https://jira.your-company.com
JIRA_PERSONAL_TOKEN=your_pat_token

CONFLUENCE_URL=https://confluence.your-company.com
CONFLUENCE_PERSONAL_TOKEN=your_pat_token
```

### OAuth 2.0 Configuration
```env
ATLASSIAN_OAUTH_CLIENT_ID=your_client_id
ATLASSIAN_OAUTH_CLIENT_SECRET=your_client_secret
ATLASSIAN_OAUTH_CLOUD_ID=your_cloud_id
ATLASSIAN_OAUTH_ACCESS_TOKEN=your_access_token
```

## 🔒 Security Considerations

1. **Credentials**: Store sensitive configuration securely
2. **Network**: Limit container exposure if possible
3. **File Permissions**: Restrict access to .env files
4. **Image Scanning**: Scan images before deployment
5. **Container Hardening**: Use minimal capabilities

## 🚨 Troubleshooting

### Common Issues

**Docker daemon not running:**
```bash
# Start Docker service
sudo systemctl start docker
# or start Docker Desktop on macOS/Windows
```

**Insufficient disk space:**
```bash
# Clean Docker cache
docker system prune -a
```

**Authentication failures:**
1. Verify .env file contents
2. Check API token permissions
3. Test connectivity to Atlassian instances
4. Review authentication method compatibility

**Port conflicts:**
```bash
# Use different port
docker run -p 8080:8000 mcp-atlassian:latest
```

### Getting Help

For issues:
1. Check container logs: `docker logs <container_id>`
2. Review configuration in .env file
3. Verify Docker installation and permissions
4. Consult the full documentation in `docs/OFFLINE_DEPLOYMENT.md`

## 📊 File Sizes and Transfer Planning

Typical file sizes:
- **Docker Image**: 500MB - 1.5GB (depending on base image size)
- **Metadata File**: ~2KB
- **Configuration**: ~5KB

Transfer planning:
- **USB 2.0**: ~2-5 minutes for 1GB
- **USB 3.0**: ~30 seconds for 1GB
- **Network Share**: Depends on network bandwidth
- **Physical Media**: Depends on transfer method

## 🔄 Automation Options

### Build and Export Script
```bash
#!/bin/bash
IMAGE_NAME="mcp-atlassian"
VERSION="latest"
EXPORT_DIR="./offline-deploy"

# Build
./scripts/docker-build.sh $IMAGE_NAME $VERSION

# Export
./scripts/docker-save.sh $IMAGE_NAME $VERSION $EXPORT_DIR

echo "Deployment package ready in: $EXPORT_DIR"
```

### Docker Compose for Production
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
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

This solution provides a complete, production-ready method for deploying MCP Atlassian in offline environments while maintaining all functionality and security features.