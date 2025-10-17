# TEST Project and Space Setup Required

## Overview
The real API tests have been updated to **only use TEST project and TEST space**. Tests will fail if these are not available.

## Required Setup

### Jira TEST Project
You must create a Jira project with the key **TEST**:

1. Go to your Jira instance
2. Create a new project with:
   - **Project Key**: `TEST`
   - **Project Name**: `Test Project for MCP`
   - **Type**: Any (Kanban, Scrum, etc.)
   - **Permissions**: Ensure your test user has full access

### Confluence TEST Space
You must create a Confluence space with the key **TEST**:

1. Go to your Confluence instance
2. Create a new space with:
   - **Space Key**: `TEST`
   - **Space Name**: `Test Space for MCP`
   - **Type**: Standard space
   - **Permissions**: Ensure your test user has full access

## Why This Is Required

The tests have been designed to:
- ✅ **Prevent resource collisions** - TEST project ensures clean isolation
- ✅ **Provide predictable test environment** - Always same project/space names
- ✅ **Avoid polluting production data** - TEST-specific resources only
- ✅ **Enable proper cleanup** - Easy to identify and clean up test resources

## Current Status

Based on the latest check:
- **Jira**: Only `KAN` project exists - **TEST project needed**
- **Confluence**: `SD` space exists - **TEST space needed**

## How to Verify Setup

Run this command to verify your TEST setup:

```bash
uv run pytest tests/integration/test_jira_mcp_live.py::TestJiraMCPFunctions::test_jira_get_issue --integration --use-real-data -v
```

If setup is correct, the test should pass. If not, it will show:
```
ValueError: TEST project not found. Please create TEST project in Jira.
```

or

```
ValueError: TEST space not found. Please create TEST space in Confluence.
```

## Test Resources Created

The tests will automatically create and clean up:
- Issues with prefix `MCP Test Issue` + UUID
- Pages with prefix `MCP Test Page` + UUID
- Comments, labels, and other test resources

All resources are tracked and deleted after each test to keep the TEST environment clean.

## Environment Variables

Make sure your `.env` file contains:
```bash
JIRA_URL=https://your-domain.atlassian.net/
JIRA_USERNAME=your-email@domain.com
JIRA_API_TOKEN=your-api-token

CONFLUENCE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_USERNAME=your-email@domain.com
CONFLUENCE_API_TOKEN=your-api-token
```

**Note**: You don't need to set `JIRA_TEST_PROJECT_KEY` or `CONFLUENCE_TEST_SPACE_KEY` anymore, as the tests now always use `TEST`.