## Why
The JIRA MCP tool has critical issues that prevent basic JIRA operations from working correctly, including broken field validation, deprecated API usage, and missing essential functionality like user search and proper assignment handling.

## What Changes
- Fix priority field handling to use correct API format with IDs instead of names
- Implement proper field validation for issue creation using current API endpoints
- Replace deprecated `/rest/api/3/issue/createmeta` endpoint (deprecated 2024-06-03)
- Add dedicated user search and assignment functionality
- Implement project metadata retrieval for comprehensive validation
- Fix issue update operations with proper field formats
- Add enhanced transition and status handling

## Impact
- **Affected specs**: New capabilities required - jira-crud, jira-user-management, jira-project-metadata
- **Affected code**: JiraCreateIssueTool, JiraUpdateIssueTool, and related MCP tools
- **Breaking changes**: API endpoint deprecations and field format corrections