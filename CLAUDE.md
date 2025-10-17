# MCP Atlassian Development Guide

## Quick Start

This project provides MCP (Model Context Protocol) integration for Atlassian Jira and Confluence services. It enables AI assistants to interact with your Atlassian instances in a structured, secure way.

## Key Features

- **Multi-Platform Support**: Works with both Atlassian Cloud and Server/Data Center instances
- **Flexible Authentication**: Supports OAuth 2.0, Personal Access Tokens (PAT), and Basic Authentication
- **Dynamic Token Management**: Header-based authentication for multi-tenant deployments
- **Advanced Content Processing**: Markdown conversion, markup translation, and field handling
- **Complete API Coverage**: Jira issues, projects, workflows; Confluence pages, spaces, search
- **Real-time Capabilities**: Rate limiting, bulk operations, concurrent requests

## Development Environment Setup

This project uses **astral uv** for Python package management and testing.

### Installation & Setup

```bash
# Clone and set up the project
git clone <repository-url>
cd mcp-atlassian
uv sync

# Configure your Atlassian credentials in .env file
cp .env.example .env
# Edit .env with your credentials
```

### Environment Configuration

The `.env` file contains all necessary configuration:

- **JIRA_URL**: Your Jira instance URL
- **JIRA_USERNAME/JIRA_API_TOKEN**: Cloud authentication (email + API token)
- **JIRA_PERSONAL_TOKEN**: Server/DC authentication
- **CONFLUENCE_URL**: Your Confluence instance URL
- **CONFLUENCE_USERNAME/CONFLUENCE_API_TOKEN**: Cloud authentication
- **CONFLUENCE_PERSONAL_TOKEN**: Server/DC authentication
- **OAuth variables**: ATLASSIAN_OAUTH_CLIENT_ID, ATLASSIAN_OAUTH_CLIENT_SECRET, etc.

### Test Configuration for Real API Tests

For integration tests that require real Atlassian data:

```bash
# Add these to your .env file for real API tests
JIRA_TEST_PROJECT_KEY=YOUR_PROJECT_KEY
CONFLUENCE_TEST_SPACE_KEY=YOUR_SPACE_KEY
```

## Testing

### Running the Full Test Suite

```bash
# Unit tests only (fast)
uv run pytest tests/unit/

# Integration tests (medium)
uv run pytest tests/integration/ --integration

# Real API tests with your actual Atlassian instances
uv run pytest tests/integration/test_real_api.py --integration --use-real-data

# All tests combined (comprehensive)
uv run pytest tests/ --integration --use-real-data

# Generate coverage report
uv run pytest tests/ --cov=src/mcp_atlassian --cov-report=html
```

### Test Categories

1. **Unit Tests** (`tests/unit/`): Fast tests for individual components and functions
2. **Integration Tests** (`tests/integration/`): Medium tests for service interactions and workflows
3. **Real API Tests** (`tests/integration/test_real_api.py`): Tests against actual Atlassian APIs

### Test Markers

- `@pytest.mark.integration`: Marks integration tests
- `--integration`: Flag to run integration tests
- `--use-real-data`: Flag to run tests against real Atlassian APIs

## Architecture

### Core Components

- **Jira Integration**: Issue management, search, projects, workflows
- **Confluence Integration**: Page management, spaces, content processing
- **Authentication Layer**: Multi-method auth with automatic fallbacks
- **MCP Server**: FastMCP-based server with tool filtering
- **Content Processing**: Markdown conversion, markup translation, field validation

### Authentication Methods

1. **OAuth 2.0 (3LO)**: Full OAuth flow for Cloud instances
2. **BYOT (Bring Your Own Token)**: Pre-existing OAuth tokens
3. **Personal Access Tokens**: Server/Data Center preferred method
4. **Basic Authentication**: Email + API token (Cloud) or username + password (Server/DC)
5. **Header-Based**: Dynamic authentication per request

### Configuration Priority

Authentication methods are prioritized as follows:
1. OAuth 2.0 configuration (highest)
2. Personal Access Tokens
3. Basic authentication
4. Header-based authentication (per request)

## Special Features

### IGNORE_HEADER_AUTH Environment Variable

For containerized deployments (GCP Cloud Run, AWS ALB, etc.) where OAuth proxy headers are automatically injected:

```yaml
env:
  - name: IGNORE_HEADER_AUTH
    value: "true"  # Forces use of environment variables instead of headers
```

### DISABLE_JIRA_MARKUP_TRANSLATION

To disable automatic markup translation between Jira and Markdown formats:

```yaml
env:
  - name: DISABLE_JIRA_MARKUP_TRANSLATION
    value: "true"  # Preserves original markup format
```

## Contributing

### Pull Request Process

1. Fork and create a feature branch
2. Make your changes with proper test coverage
3. Run the full test suite locally
4. Ensure all tests pass before creating PR
5. Include test data setup if needed for real API tests

### Code Quality Standards

- Use `uv run ruff check` for linting
- Use `uv run ruff format` for code formatting
- Add comprehensive tests for new features
- Follow existing code patterns and conventions

## API Documentation

Reference detailed Atlassian API documentation in `./atlassian_api_docs.txt` for specific endpoint information and usage patterns.

## GitHub CLI Integration

Use `gh` CLI to review and track pull requests:

```bash
# List outstanding PRs
gh pr list --repo sooperset/mcp-atlassian --state open

# View PR details
gh pr view <pr-number> --repo sooperset/mcp-atlassian

# Review changes
gh pr diff <pr-number> --repo sooperset/mcp-atlassian
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**: Verify credentials in `.env` match your Atlassian instance
2. **Rate Limiting**: Check if your Atlassian plan allows sufficient API calls
3. **Network Issues**: Verify proxy settings and SSL configuration
4. **Test Failures**: Ensure test data exists in your Atlassian instances

### Debug Logging

Enable verbose logging for troubleshooting:

```bash
export MCP_VERBOSE=true     # INFO level logging
export MCP_VERY_VERBOSE=true  # DEBUG level logging
```

## Deployment

### Production Considerations

- Use proper secret management for credentials
- Configure rate limiting and retry logic
- Enable monitoring and logging
- Set up appropriate SSL/TLS configurations
- Use container orchestration with proper health checks 
