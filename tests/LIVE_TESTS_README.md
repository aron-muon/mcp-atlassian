# Live MCP Tests

This directory contains comprehensive live tests for all Jira and Confluence MCP functions. These tests interact with real Atlassian instances to verify complete end-to-end functionality.

## Overview

The live tests are designed to validate every MCP function by:

1. **Creating real resources** (issues, pages, comments, etc.)
2. **Calling the actual MCP server functions**
3. **Verifying the responses and behavior**
4. **Cleaning up created resources** to avoid test pollution

## Test Coverage

### Jira MCP Functions Tested

- `jira_get_issue` - Retrieve detailed issue information
- `jira_search_issues` - Search using JQL with pagination
- `jira_create_issue` - Create new issues
- `jira_get_all_projects` - List accessible projects
- `jira_get_issue_comments` - Retrieve issue comments
- `jira_add_comment` - Add comments to issues
- `jira_get_epic_issues` - Get issues belonging to epics
- `jira_batch_create_issues` - Create multiple issues
- `jira_get_development_status` - Get development information
- `jira_add_issues_to_sprint` - Sprint management
- `jira_search_fields` - Field search functionality
- `jira_get_project_issues` - Get project issues
- `jira_get_transitions` - Workflow transitions
- `jira_get_worklog` / `jira_add_worklog` - Time tracking
- `jira_get_agile_boards` / `jira_get_board_issues` - Agile boards
- `jira_get_sprints_from_board` / `jira_get_sprint_issues` - Sprint operations
- `jira_get_link_types` / `jira_create_issue_link` - Issue linking
- `jira_update_issue` / `jira_delete_issue` - Issue lifecycle
- `jira_transition_issue` - Status transitions
- `jira_create_version` / `jira_batch_create_versions` - Version management
- `jira_get_user_profile` - User information
- `jira_download_attachments` - Attachment handling
- `jira_remote_issue_link` - Remote linking
- `jira_batch_get_changelogs` - Change log operations

### Confluence MCP Functions Tested

- `confluence_search` - Content search with CQL
- `confluence_get_page` - Page retrieval by ID or title
- `confluence_get_page_children` - Page hierarchy
- `confluence_get_comments` / `confluence_add_comment` - Comments
- `confluence_get_labels` / `confluence_add_label` - Labels
- `confluence_create_page` / `confluence_update_page` / `confluence_delete_page` - Page lifecycle
- `confluence_search_user` / `confluence_get_user_details` - User functions
- `confluence_list_page_versions` / `confluence_get_page_version` - Versioning
- `confluence_move_page` - Page organization
- Content format handling (Markdown, Wiki markup, Storage format)

## Setup Requirements

### Environment Variables

Create a `.env` file in the project root with the following:

```bash
# Jira Configuration
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_TEST_PROJECT_KEY=TEST

# Confluence Configuration
CONFLUENCE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_USERNAME=your-email@example.com
CONFLUENCE_API_TOKEN=your-api-token
CONFLUENCE_TEST_SPACE_KEY=TEST

# Optional: OAuth Configuration
ATLASSIAN_OAUTH_CLIENT_ID=your-client-id
ATLASSIAN_OAUTH_CLIENT_SECRET=your-client-secret
ATLASSIAN_OAUTH_REDIRECT_URI=http://localhost:8080/callback
ATLASSIAN_OAUTH_CLOUD_ID=your-cloud-id
```

### Test Project/Space Setup

1. **Jira Test Project**: Create a test project in Jira with the key specified in `JIRA_TEST_PROJECT_KEY`
   - Ensure it supports common issue types (Task, Story, Bug, Epic)
   - Configure workflows to allow status transitions for testing

2. **Confluence Test Space**: Create a test space in Confluence with the key specified in `CONFLUENCE_TEST_SPACE_KEY`
   - Ensure you have permissions to create, edit, and delete pages
   - Test with a space that doesn't contain critical content

### API Tokens

Generate API tokens from your Atlassian account:
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Create a new token with appropriate permissions
3. Use the token in your `.env` file

## Running the Tests

### Using the Test Runner (Recommended)

```bash
# Check environment setup
python tests/run_live_tests.py --check-only

# Run all tests
python tests/run_live_tests.py

# Run only Jira tests
python tests/run_live_tests.py --jira-only

# Run only Confluence tests
python tests/run_live_tests.py --confluence-only

# Run with verbose output
python tests/run_live_tests.py --verbose
```

### Using Pytest Directly

```bash
# Run all live tests
uv run pytest tests/integration/test_jira_mcp_live.py tests/integration/test_confluence_mcp_live.py --integration --use-real-data

# Run only Jira tests
uv run pytest tests/integration/test_jira_mcp_live.py --integration --use-real-data

# Run only Confluence tests
uv run pytest tests/integration/test_confluence_mcp_live.py --integration --use-real-data

# Run with verbose output
uv run pytest tests/integration/test_*_mcp_live.py --integration --use-real-data -v
```

## Test Isolation and Cleanup

The tests implement comprehensive resource management:

### Resource Tracking
- Each test class tracks created resources (issues, pages, comments, etc.)
- Resources are stored in dictionaries with categorized lists
- Unique identifiers (UUIDs) are used to avoid conflicts

### Cleanup Strategy
- **Immediate cleanup**: Resources are deleted as soon as they're no longer needed
- **Exception handling**: Cleanup continues even if individual deletions fail
- **Test isolation**: Each test uses unique identifiers to prevent interference
- **Hierarchical cleanup**: Parent resources are cleaned up after children

### Error Handling
- Tests continue even if some cleanup operations fail
- Detailed error reporting helps identify issues
- Graceful handling of missing functionality (e.g., features not available in all instances)

## Test Output

The tests provide detailed output including:

- ✅ Success indicators for passed operations
- ❌ Error indicators for failed operations
- 📊 Resource counts and verification results
- ⚠️ Warnings for skipped functionality
- 🧪 Test progress and timing information

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   ```
   ValueError: Missing required JIRA_URL environment variable
   ```
   - Verify your `.env` file is properly configured
   - Check that API tokens are valid and have sufficient permissions

2. **Permission Errors**
   ```
   HTTPError: 403 Client Error: Forbidden
   ```
   - Ensure your user has permissions to create/modify content in the test project/space
   - Verify API tokens have the required scopes

3. **Missing Test Data**
   ```
   Project does not support Epic issue type
   ```
   - Configure your test project with standard issue types
   - Some tests will skip functionality that's not available

4. **Rate Limiting**
   ```
   HTTPError: 429 Client Error: Too Many Requests
   ```
   - Tests include retry logic for rate limiting
   - Consider running tests in smaller batches if issues persist

### Debug Mode

Enable verbose logging to troubleshoot issues:

```bash
export MCP_VERBOSE=true
export MCP_VERY_VERBOSE=true
python tests/run_live_tests.py --verbose
```

## Best Practices

1. **Use Dedicated Test Environment**: Create a separate Jira project and Confluence space for testing
2. **Regular Cleanup**: Run tests regularly to prevent resource accumulation
3. **Monitor API Usage**: Be aware of Atlassian API rate limits
4. **Backup Important Data**: Never run live tests against production data
5. **Test Isolation**: Each test creates unique resources to avoid conflicts

## Contributing

When adding new live tests:

1. Follow the existing pattern for resource tracking and cleanup
2. Use unique identifiers (UUIDs) for all created resources
3. Implement proper error handling and validation
4. Add comprehensive assertions for all MCP function responses
5. Update this README with new test coverage

## Safety Considerations

- ⚠️ **These tests modify real data** - always use a dedicated test environment
- 🔒 **API tokens have elevated permissions** - store them securely
- 📝 **Test operations are logged** - review test output for unexpected changes
- 🧹 **Automatic cleanup** - but verify no orphaned resources remain
- 📊 **Resource usage** - monitor API consumption during testing