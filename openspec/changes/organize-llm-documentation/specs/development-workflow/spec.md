## ADDED Requirements

### Requirement: Repository Structure Understanding
The system SHALL provide a clear repository map for autonomous coding agents to understand the project structure.

#### Scenario: Agent navigates repository structure
- **WHEN** an LLM agent needs to understand the project layout
- **THEN** the system SHALL provide a clear mapping of directories and their purposes

### Requirement: Development Environment Setup
The system SHALL provide a mandatory development workflow using uv package manager.

#### Scenario: Agent sets up development environment
- **WHEN** an agent needs to set up the development environment
- **THEN** the system SHALL require running `uv sync --frozen --all-extras --dev` to install dependencies
- **AND** the system SHALL require running `pre-commit install` to setup hooks
- **AND** the system SHALL require running `pre-commit run --all-files` for linting and formatting
- **AND** the system SHALL require running `uv run pytest` to run the test suite
- **AND** the system SHALL enforce that tests must pass and lint/typing must be clean before committing

### Requirement: MCP Architecture Patterns
The system SHALL follow consistent MCP patterns for tool naming and architecture.

#### Scenario: Agent creates new MCP tools
- **WHEN** implementing new MCP functionality
- **THEN** the system SHALL use `{service}_{action}` naming convention (e.g., `jira_create_issue`)
- **AND** the system SHALL organize functionality into focused mixins extending base clients
- **AND** the system SHALL ensure all data structures extend `ApiModel` base class
- **AND** the system SHALL support multiple authentication methods (API tokens, PAT tokens, OAuth 2.0)

### Requirement: Development Rules Compliance
The system SHALL enforce strict development rules for all code changes.

#### Scenario: Agent writes code
- **WHEN** making any code changes
- **THEN** the system SHALL require using only `uv` for package management, never `pip`
- **AND** the system SHALL require working on feature branches, never on `main`
- **AND** the system SHALL require type hints for all functions
- **AND** the system SHALL require tests for new features and regression tests for bug fixes
- **AND** the system SHALL require using commit trailers for attribution without mentioning tools/AI

### Requirement: Code Style Conventions
The system SHALL maintain consistent code style and conventions.

#### Scenario: Agent formats code
- **WHEN** writing or formatting Python code
- **THEN** the system SHALL require Python ≥ 3.10
- **AND** the system SHALL enforce 88 characters maximum line length
- **AND** the system SHALL require absolute imports sorted by ruff
- **AND** the system SHALL require `snake_case` function naming and `PascalCase` class naming
- **AND** the system SHALL require Google-style docstrings for all public APIs
- **AND** the system SHALL require specific exceptions only for error handling

### Requirement: Development Guidelines
The system SHALL follow specific development guidelines for consistency and quality.

#### Scenario: Agent implements features
- **WHEN** implementing any changes
- **THEN** the system SHALL require doing exactly what was asked, nothing more or less
- **AND** the system SHALL require never creating files unless absolutely necessary
- **AND** the system SHALL require preferring to edit existing files
- **AND** the system SHALL require following established patterns and maintaining consistency
- **AND** the system SHALL require running `pre-commit run --all-files` before committing
- **AND** the system SHALL require fixing bugs immediately when reported

### Requirement: Quick Reference Commands
The system SHALL provide quick reference commands for common operations.

#### Scenario: Agent needs command reference
- **WHEN** an agent needs to run common operations
- **THEN** the system SHALL provide server commands (`uv run mcp-atlassian`, `uv run mcp-atlassian --oauth-setup`, `uv run mcp-atlassian -v`)
- **AND** the system SHALL provide Git workflow commands (`git checkout -b feature/description`, `git checkout -b fix/issue-description`)
- **AND** the system SHALL provide commit commands with trailers (`git commit --trailer "Reported-by:<name>"`, `git commit --trailer "Github-Issue:#<number>"`)

### Requirement: Project Setup and Configuration
The system SHALL provide comprehensive project setup using astral uv.

#### Scenario: Agent sets up project environment
- **WHEN** setting up the development environment
- **THEN** the system SHALL require cloning and running `uv sync` for installation
- **AND** the system SHALL require configuring Atlassian credentials in `.env` file
- **AND** the system SHALL support multiple authentication methods (OAuth 2.0, Personal Access Tokens, Basic Authentication)

### Requirement: Testing Strategy
The system SHALL provide comprehensive testing with multiple categories.

#### Scenario: Agent runs tests
- **WHEN** running the test suite
- **THEN** the system SHALL support unit tests (`tests/unit/`) for fast component testing
- **AND** the system SHALL support integration tests (`tests/integration/`) for service interactions
- **AND** the system SHALL support real API tests (`tests/integration/test_real_api.py`) with actual Atlassian instances
- **AND** the system SHALL require adding test data setup for real API tests (`JIRA_TEST_PROJECT_KEY`, `CONFLUENCE_TEST_SPACE_KEY`)

### Requirement: Architecture Understanding
The system SHALL provide clear architecture documentation for core components.

#### Scenario: Agent understands architecture
- **WHEN** working with the codebase architecture
- **THEN** the system SHALL document Jira Integration (issue management, search, projects, workflows)
- **AND** the system SHALL document Confluence Integration (page management, spaces, content processing)
- **AND** the system SHALL document Authentication Layer (multi-method auth with automatic fallbacks)
- **AND** the system SHALL document MCP Server (FastMCP-based server with tool filtering)
- **AND** the system SHALL document Content Processing (markdown conversion, markup translation, field validation)

### Requirement: Authentication Configuration
The system SHALL support flexible authentication with proper priority handling.

#### Scenario: Agent configures authentication
- **WHEN** setting up authentication
- **THEN** the system SHALL prioritize OAuth 2.0 configuration (highest)
- **AND** the system SHALL support Personal Access Tokens
- **AND** the system SHALL support Basic authentication
- **AND** the system SHALL support Header-based authentication (per request)
- **AND** the system SHALL document IGNORE_HEADER_AUTH for containerized deployments
- **AND** the system SHALL document DISABLE_JIRA_MARKUP_TRANSLATION for markup preservation

### Requirement: Code Quality Standards
The system SHALL maintain high code quality standards.

#### Scenario: Agent ensures code quality
- **WHEN** preparing code for commit
- **THEN** the system SHALL require running `uv run ruff check` for linting
- **AND** the system SHALL require running `uv run ruff format` for code formatting
- **AND** the system SHALL require comprehensive tests for new features
- **AND** the system SHALL require following existing code patterns and conventions

### Requirement: GitHub CLI Integration
The system SHALL provide GitHub CLI integration for pull request management.

#### Scenario: Agent manages pull requests
- **WHEN** working with GitHub pull requests
- **THEN** the system SHALL support `gh pr list --repo sooperset/mcp-atlassian --state open` to list outstanding PRs
- **AND** the system SHALL support `gh pr view <pr-number> --repo sooperset/mcp-atlassian` to view PR details
- **AND** the system SHALL support `gh pr diff <pr-number> --repo sooperset/mcp-atlassian` to review changes

### Requirement: Debug Logging Configuration
The system SHALL provide configurable debug logging for troubleshooting.

#### Scenario: Agent needs to debug issues
- **WHEN** troubleshooting authentication or API issues
- **THEN** the system SHALL support `export MCP_VERBOSE=true` for INFO level logging
- **AND** the system SHALL support `export MCP_VERY_VERBOSE=true` for DEBUG level logging