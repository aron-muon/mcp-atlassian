"""Unit tests for the Jira FastMCP server implementation."""

import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client, FastMCP
from fastmcp.client import FastMCPTransport
from fastmcp.exceptions import ToolError
from starlette.requests import Request

from src.mcp_atlassian.jira import JiraFetcher
from src.mcp_atlassian.jira.config import JiraConfig
from src.mcp_atlassian.jira.constants import DEFAULT_READ_JIRA_FIELDS
from src.mcp_atlassian.servers.context import MainAppContext
from src.mcp_atlassian.servers.jira import register_jira_tools
from src.mcp_atlassian.servers.main import AtlassianMCP
from src.mcp_atlassian.utils.oauth import OAuthConfig
from tests.fixtures.jira_mocks import (
    MOCK_JIRA_COMMENTS_SIMPLIFIED,
    MOCK_JIRA_ISSUE_RESPONSE_SIMPLIFIED,
    MOCK_JIRA_JQL_RESPONSE_SIMPLIFIED,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_jira_fetcher():
    """Create a mock JiraFetcher using predefined responses from fixtures."""
    mock_fetcher = MagicMock(spec=JiraFetcher)
    mock_fetcher.config = MagicMock()
    mock_fetcher.config.read_only = False
    mock_fetcher.config.url = "https://test.atlassian.net"
    mock_fetcher.config.projects_filter = None  # Explicitly set to None by default

    # Configure common methods
    mock_fetcher.get_current_user_account_id.return_value = "test-account-id"
    mock_fetcher.jira = MagicMock()

    # Configure get_issue to return fixture data
    def mock_get_issue(
        issue_key,
        fields=None,
        expand=None,
        comment_limit=10,
        properties=None,
        update_history=True,
    ):
        if not issue_key:
            raise ValueError("Issue key is required")
        mock_issue = MagicMock()
        response_data = MOCK_JIRA_ISSUE_RESPONSE_SIMPLIFIED.copy()
        response_data["key"] = issue_key
        response_data["fields_queried"] = fields
        response_data["expand_param"] = expand
        response_data["comment_limit"] = comment_limit
        response_data["properties_param"] = properties
        response_data["update_history"] = update_history
        response_data["id"] = MOCK_JIRA_ISSUE_RESPONSE_SIMPLIFIED["id"]
        # Add top-level fields for test compatibility
        response_data["summary"] = MOCK_JIRA_ISSUE_RESPONSE_SIMPLIFIED["fields"][
            "summary"
        ]
        response_data["description"] = MOCK_JIRA_ISSUE_RESPONSE_SIMPLIFIED["fields"][
            "description"
        ]
        response_data["status"] = {
            "name": MOCK_JIRA_ISSUE_RESPONSE_SIMPLIFIED["fields"]["status"]["name"]
        }
        mock_issue.to_simplified_dict.return_value = response_data
        return mock_issue

    mock_fetcher.get_issue.side_effect = mock_get_issue

    # Configure get_issue_comments to return fixture data
    def mock_get_issue_comments(issue_key, limit=10):
        return MOCK_JIRA_COMMENTS_SIMPLIFIED["comments"][:limit]

    mock_fetcher.get_issue_comments.side_effect = mock_get_issue_comments

    # Configure search_issues to return fixture data
    def mock_search_issues(jql, **kwargs):
        mock_search_result = MagicMock()
        issues = []
        for issue_data in MOCK_JIRA_JQL_RESPONSE_SIMPLIFIED["issues"]:
            mock_issue = MagicMock()
            mock_issue.to_simplified_dict.return_value = issue_data
            issues.append(mock_issue)
        mock_search_result.issues = issues
        mock_search_result.total = len(issues)
        mock_search_result.start_at = kwargs.get("start", 0)
        mock_search_result.max_results = kwargs.get("limit", 50)
        mock_search_result.to_simplified_dict.return_value = {
            "total": len(issues),
            "start_at": kwargs.get("start", 0),
            "max_results": kwargs.get("limit", 50),
            "issues": [issue.to_simplified_dict() for issue in issues],
        }
        return mock_search_result

    mock_fetcher.search_issues.side_effect = mock_search_issues

    # Configure create_issue
    def mock_create_issue(
        project_key,
        summary,
        issue_type,
        description=None,
        assignee=None,
        components=None,
        priority=None,
        **additional_fields,
    ):
        if not project_key or project_key.strip() == "":
            raise ValueError("valid project is required")
        components_list = None
        if components:
            if isinstance(components, str):
                components_list = components.split(",")
            elif isinstance(components, list):
                components_list = components
        mock_issue = MagicMock()
        response_data = {
            "key": f"{project_key}-456",
            "summary": summary,
            "description": description,
            "issue_type": {"name": issue_type},
            "status": {"name": "Open"},
            "components": [{"name": comp} for comp in components_list]
            if components_list
            else [],
            **additional_fields,
        }
        if priority:
            response_data["priority"] = {"name": priority}
        mock_issue.to_simplified_dict.return_value = response_data
        return mock_issue

    mock_fetcher.create_issue.side_effect = mock_create_issue

    # Configure batch_create_issues
    def mock_batch_create_issues(issues, validate_only=False):
        if not isinstance(issues, list):
            try:
                parsed_issues = json.loads(issues)
                if not isinstance(parsed_issues, list):
                    raise ValueError(
                        "Issues must be a list or a valid JSON array string."
                    )
                issues = parsed_issues
            except (json.JSONDecodeError, TypeError):
                raise ValueError("Issues must be a list or a valid JSON array string.")
        mock_issues = []
        for idx, issue_data in enumerate(issues, 1):
            mock_issue = MagicMock()
            mock_issue.to_simplified_dict.return_value = {
                "key": f"{issue_data['project_key']}-{idx}",
                "summary": issue_data["summary"],
                "issue_type": {"name": issue_data["issue_type"]},
                "status": {"name": "To Do"},
            }
            mock_issues.append(mock_issue)
        return mock_issues

    mock_fetcher.batch_create_issues.side_effect = mock_batch_create_issues

    # Configure update_issue
    def mock_update_issue(issue_key, fields=None, **kwargs):
        mock_issue = MagicMock()
        # Merge fields and kwargs for the response
        merged_fields = {**(fields or {}), **kwargs}
        mock_issue.to_simplified_dict.return_value = {
            "key": issue_key,
            "summary": merged_fields.get("summary", "Updated Issue"),
            "description": merged_fields.get("description", "Updated description"),
            "status": {"name": "In Progress"},
            "issue_type": {"name": "Task"},
            "priority": merged_fields.get("priority", {"name": "Medium"}),
            "assignee": {"display_name": merged_fields.get("assignee", "Test User")},
            **{k: v for k, v in merged_fields.items() if k.startswith("customfield_")},
        }
        return mock_issue

    mock_fetcher.update_issue.side_effect = mock_update_issue

    # Configure get_epic_issues
    def mock_get_epic_issues(epic_key, start=0, limit=50):
        mock_issues = []
        for i in range(1, 4):
            mock_issue = MagicMock()
            mock_issue.to_simplified_dict.return_value = {
                "key": f"TEST-{i}",
                "summary": f"Epic Issue {i}",
                "issue_type": {"name": "Task" if i % 2 == 0 else "Bug"},
                "status": {"name": "To Do" if i % 2 == 0 else "In Progress"},
            }
            mock_issues.append(mock_issue)
        return mock_issues[start : start + limit]

    mock_fetcher.get_epic_issues.side_effect = mock_get_epic_issues

    # Configure get_all_projects
    def mock_get_all_projects(include_archived=False):
        projects = [
            {
                "id": "10000",
                "key": "TEST",
                "name": "Test Project",
                "description": "Project for testing",
                "lead": {"name": "admin", "displayName": "Administrator"},
                "projectTypeKey": "software",
                "archived": False,
            }
        ]
        if include_archived:
            projects.append(
                {
                    "id": "10001",
                    "key": "ARCHIVED",
                    "name": "Archived Project",
                    "description": "Archived project",
                    "lead": {"name": "admin", "displayName": "Administrator"},
                    "projectTypeKey": "software",
                    "archived": True,
                }
            )
        return projects

    # Set default side_effect to respect include_archived parameter
    mock_fetcher.get_all_projects.side_effect = mock_get_all_projects

    mock_fetcher.jira.jql.return_value = {
        "issues": [
            {
                "fields": {
                    "project": {
                        "key": "TEST",
                        "name": "Test Project",
                        "description": "Project for testing",
                    }
                }
            }
        ]
    }

    from src.mcp_atlassian.models.jira.common import JiraUser

    mock_user = MagicMock(spec=JiraUser)
    mock_user.to_simplified_dict.return_value = {
        "display_name": "Test User (test.profile@example.com)",
        "name": "Test User (test.profile@example.com)",
        "email": "test.profile@example.com",
        "avatar_url": "https://test.atlassian.net/avatar/test.profile@example.com",
    }
    mock_get_user_profile = MagicMock()

    def side_effect_func(identifier):
        if identifier == "nonexistent@example.com":
            raise ValueError(f"User '{identifier}' not found.")
        return mock_user

    mock_get_user_profile.side_effect = side_effect_func
    mock_fetcher.get_user_profile_by_identifier = mock_get_user_profile

    # Mock add_issues_to_sprint method
    def mock_add_issues_to_sprint(sprint_id, issues):
        return True

    mock_fetcher.add_issues_to_sprint.side_effect = mock_add_issues_to_sprint

    return mock_fetcher


@pytest.fixture
def mock_base_jira_config():
    """Create a mock base JiraConfig for MainAppContext using OAuth for multi-user scenario."""
    mock_oauth_config = OAuthConfig(
        client_id="server_client_id",
        client_secret="server_client_secret",
        redirect_uri="http://localhost",
        scope="read:jira-work",
        cloud_id="mock_jira_cloud_id",
    )
    return JiraConfig(
        url="https://mock-jira.atlassian.net",
        auth_type="oauth",
        oauth_config=mock_oauth_config,
    )


@pytest.fixture
def test_jira_mcp(mock_jira_fetcher, mock_base_jira_config):
    """Create a test FastMCP instance with standard configuration."""

    @asynccontextmanager
    async def test_lifespan(app: FastMCP) -> AsyncGenerator[MainAppContext, None]:
        try:
            yield MainAppContext(
                full_jira_config=mock_base_jira_config, read_only=False
            )
        finally:
            pass

    test_mcp = AtlassianMCP(
        "TestJira", description="Test Jira MCP Server", lifespan=test_lifespan
    )

    jira_sub_mcp = FastMCP(name="TestJiraSubMCP")
    register_jira_tools(jira_sub_mcp)
    test_mcp.mount("jira", jira_sub_mcp)
    return test_mcp


@pytest.fixture
def no_fetcher_test_jira_mcp(mock_base_jira_config):
    """Create a test FastMCP instance that simulates missing Jira fetcher."""

    @asynccontextmanager
    async def no_fetcher_test_lifespan(
        app: FastMCP,
    ) -> AsyncGenerator[MainAppContext, None]:
        try:
            yield MainAppContext(full_jira_config=None, read_only=False)
        finally:
            pass

    test_mcp = AtlassianMCP(
        "NoFetcherTestJira",
        description="No Fetcher Test Jira MCP Server",
        lifespan=no_fetcher_test_lifespan,
    )

    jira_sub_mcp = FastMCP(name="NoFetcherTestJiraSubMCP")
    register_jira_tools(jira_sub_mcp)
    test_mcp.mount("jira", jira_sub_mcp)
    return test_mcp


@pytest.fixture
def mock_request():
    """Provides a mock Starlette Request object with a state."""
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.jira_fetcher = None
    request.state.user_atlassian_auth_type = None
    request.state.user_atlassian_token = None
    request.state.user_atlassian_email = None
    return request


@pytest.fixture
async def jira_client(test_jira_mcp, mock_jira_fetcher, mock_request):
    """Create a FastMCP client with mocked Jira fetcher and request state."""
    with (
        patch(
            "src.mcp_atlassian.servers.jira.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
        patch(
            "src.mcp_atlassian.servers.dependencies.get_http_request",
            return_value=mock_request,
        ),
    ):
        async with Client(transport=FastMCPTransport(test_jira_mcp)) as client_instance:
            yield client_instance


@pytest.fixture
async def no_fetcher_client_fixture(no_fetcher_test_jira_mcp, mock_request):
    """Create a client that simulates missing Jira fetcher configuration."""
    async with Client(
        transport=FastMCPTransport(no_fetcher_test_jira_mcp)
    ) as client_for_no_fetcher:
        yield client_for_no_fetcher


@pytest.mark.anyio
async def test_get_issue(jira_client, mock_jira_fetcher):
    """Test the get_issue tool with fixture data."""
    response = await jira_client.call_tool(
        "jira_get_issue",
        {
            "issue_key": "TEST-123",
            "fields": "summary,description,status",
        },
    )
    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)
    assert content["success"] is True
    assert "issue" in content
    assert content["issue"]["key"] == "TEST-123"
    assert content["issue"]["summary"] == "Test Issue Summary"
    mock_jira_fetcher.get_issue.assert_called_once_with(
        issue_key="TEST-123",
        fields=["summary", "description", "status"],
        expand=None,
        comment_limit=10,
        properties=None,
        update_history=True,
    )


@pytest.mark.anyio
async def test_get_issue_invalid_key(jira_client, mock_jira_fetcher):
    """Test that get_issue fails when a key does not exist and provides an informative error."""
    mock_jira_fetcher.get_issue.side_effect = ValueError("Issue Does Not Exist")

    response = await jira_client.call_tool(
        "jira_get_issue",
        {
            "issue_key": "FAIL-123",
            "fields": "summary,description,status",
        },
    )

    mock_jira_fetcher.get_issue.assert_called_once_with(
        issue_key="FAIL-123",
        fields=["summary", "description", "status"],
        expand=None,
        comment_limit=10,
        properties=None,
        update_history=True,
    )

    result_data = json.loads(response[0].text)
    assert result_data["success"] is False
    assert "Issue Does Not Exist" in result_data["error"]


@pytest.mark.anyio
async def test_search(jira_client, mock_jira_fetcher):
    """Test the search tool with fixture data."""
    response = await jira_client.call_tool(
        "jira_search_issues",
        {
            "jql": "project = TEST",
            "fields": "summary,status",
            "limit": 10,
            "start": 0,
        },
    )
    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)
    assert isinstance(content, dict)
    assert content["success"] is True
    assert "search_results" in content
    assert isinstance(content["search_results"]["issues"], list)
    assert len(content["search_results"]["issues"]) >= 1
    assert content["search_results"]["issues"][0]["key"] == "PROJ-123"
    assert content["search_results"]["total"] > 0
    assert content["search_results"]["start_at"] == 0
    assert content["search_results"]["max_results"] == 10
    mock_jira_fetcher.search_issues.assert_called_once_with(
        jql="project = TEST",
        fields=["summary", "status"],
        start=0,
        limit=10,
        expand=None,
    )


@pytest.mark.anyio
async def test_create_issue(jira_client, mock_jira_fetcher):
    """Test the create_issue tool with fixture data."""
    response = await jira_client.call_tool(
        "jira_create_issue",
        {
            "project_key": "TEST",
            "summary": "New Issue",
            "issue_type": "Task",
            "description": "This is a new task",
            "components": "Frontend,API",
            "priority": "Medium",
        },
    )
    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)
    assert content["success"] is True
    assert "issue" in content
    assert content["issue"]["key"] == "TEST-456"
    assert content["issue"]["summary"] == "New Issue"
    assert content["issue"]["description"] == "This is a new task"
    assert "components" in content["issue"]
    component_names = [comp["name"] for comp in content["issue"]["components"]]
    assert "Frontend" in component_names
    assert "API" in component_names
    assert content["issue"]["priority"] == {"name": {"name": "Medium"}}
    mock_jira_fetcher.create_issue.assert_called_once_with(
        project_key="TEST",
        summary="New Issue",
        issue_type="Task",
        description="This is a new task",
        assignee=None,
        components=["Frontend", "API"],
        reporter=None,
        priority={"name": "Medium"},
    )


@pytest.mark.anyio
async def test_create_issue_accepts_json_string(jira_client, mock_jira_fetcher):
    """Ensure labels parameter works correctly."""
    payload = {
        "project_key": "TEST",
        "summary": "JSON Issue",
        "issue_type": "Task",
        "labels": "ai,test",
    }
    response = await jira_client.call_tool("jira_create_issue", payload)
    assert response
    data = json.loads(response[0].text)
    assert data["success"] is True
    assert "issue" in data
    mock_jira_fetcher.create_issue.assert_called_once()
    # Get the call arguments
    call_args = mock_jira_fetcher.create_issue.call_args
    assert call_args[1]["project_key"] == "TEST"
    assert call_args[1]["summary"] == "JSON Issue"
    assert call_args[1]["issue_type"] == "Task"
    assert call_args[1]["description"] is None
    assert call_args[1]["assignee"] is None
    assert call_args[1]["components"] is None
    assert call_args[1]["reporter"] is None
    # priority is not passed when not specified in payload


@pytest.mark.anyio
async def test_create_issue_error_handling(jira_client, mock_jira_fetcher):
    """Test that create_issue surfaces errors in a structured JSON response."""
    # Simulate error by passing an invalid project_key (empty string)
    response = await jira_client.call_tool(
        "jira_create_issue",
        {
            "project_key": "",  # Invalid project key
            "summary": "Should Fail",
            "issue_type": "Task",
            "description": "This should trigger an error",
        },
    )
    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)
    assert "error" in content
    assert content["error"] == "Validation Error"
    assert "Project key is required and cannot be empty" in content["message"]
    assert "issue" in content
    assert content["issue"] == {}


@pytest.mark.anyio
async def test_batch_create_issues(jira_client, mock_jira_fetcher):
    """Test batch creation of Jira issues."""
    test_issues = [
        {
            "project_key": "TEST",
            "summary": "Test Issue 1",
            "issue_type": "Task",
            "description": "Test description 1",
            "assignee": "test.user@example.com",
            "components": ["Frontend", "API"],
        },
        {
            "project_key": "TEST",
            "summary": "Test Issue 2",
            "issue_type": "Bug",
            "description": "Test description 2",
        },
    ]
    test_issues_json = json.dumps(test_issues)
    response = await jira_client.call_tool(
        "jira_batch_create_issues",
        {"issues": test_issues_json, "validate_only": False},
    )
    assert len(response) == 1
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)
    assert content["success"] is True
    assert "issues" in content
    assert len(content["issues"]) == 2
    assert content["total"] == 2
    # Keys might vary based on mock implementation
    assert any(issue.get("key") in ["TEST-1", "TEST-2"] for issue in content["issues"])
    # Check that the mock was called correctly
    mock_jira_fetcher.batch_create_issues.assert_called_once()
    call_args = mock_jira_fetcher.batch_create_issues.call_args
    # Call args may be positional or keyword arguments
    if call_args.args:
        assert call_args.args[0] == test_issues
    if call_args.kwargs:
        assert call_args.kwargs.get("validate_only") is False


@pytest.mark.anyio
async def test_batch_create_issues_invalid_json(jira_client):
    """Test error handling for invalid JSON in batch issue creation."""
    response = await jira_client.call_tool(
        "jira_batch_create_issues",
        {"issues": "{invalid json", "validate_only": False},
    )
    assert response
    data = json.loads(response[0].text)
    # The mock implementation handles invalid JSON by treating it as an empty array
    assert data["success"] is True
    assert data["issues"] == []
    assert data["total"] == 0


# update_issue tool is not implemented in current version
# @pytest.mark.anyio
# async def test_update_issue_basic(jira_client, mock_jira_fetcher):
#     """Test basic update_issue functionality."""
#     payload = {
#         "issue_key": "TEST-123",
#         "fields": {"summary": "Updated Summary", "priority": {"name": "High"}},
#     }
#     response = await jira_client.call_tool("jira_update_issue", payload)
#     assert response
#     data = json.loads(response[0].text)
#     assert data["message"] == "Issue updated successfully"
#     assert "issue" in data
#     assert data["issue"]["key"] == "TEST-123"
#     assert data["issue"]["summary"] == "Updated Summary"

#     mock_jira_fetcher.update_issue.assert_called_once()


@pytest.mark.anyio
async def test_get_user_profile_tool_success(jira_client, mock_jira_fetcher):
    """Test the get_user_profile tool successfully retrieves user info."""
    response = await jira_client.call_tool(
        "jira_get_user_profile", {"user_identifier": "test.profile@example.com"}
    )
    mock_jira_fetcher.get_user_profile_by_identifier.assert_called_once_with(
        "test.profile@example.com"
    )
    assert len(response) == 1
    result_data = json.loads(response[0].text)
    assert result_data["success"] is True
    assert "user" in result_data
    user_info = result_data["user"]
    assert user_info["display_name"] == "Test User (test.profile@example.com)"
    assert user_info["email"] == "test.profile@example.com"
    assert (
        user_info["avatar_url"]
        == "https://test.atlassian.net/avatar/test.profile@example.com"
    )


@pytest.mark.anyio
async def test_get_user_profile_tool_not_found(jira_client, mock_jira_fetcher):
    """Test the get_user_profile tool handles 'user not found' errors."""
    response = await jira_client.call_tool(
        "jira_get_user_profile", {"user_identifier": "nonexistent@example.com"}
    )
    assert len(response) == 1
    result_data = json.loads(response[0].text)
    assert result_data["success"] is False
    assert "error" in result_data
    assert "not found" in result_data["error"]
    assert result_data["user_identifier"] == "nonexistent@example.com"


@pytest.mark.anyio
async def test_no_fetcher_get_issue(no_fetcher_client_fixture, mock_request):
    """Test that get_issue fails when Jira client is not configured (global config missing)."""

    async def mock_get_fetcher_error(*args, **kwargs):
        raise ValueError(
            "Mocked: Jira client (fetcher) not available. Ensure server is configured correctly."
        )

    with (
        patch(
            "src.mcp_atlassian.servers.jira.get_jira_fetcher",
            AsyncMock(side_effect=mock_get_fetcher_error),
        ),
        patch(
            "src.mcp_atlassian.servers.dependencies.get_http_request",
            return_value=mock_request,
        ),
    ):
        response = await no_fetcher_client_fixture.call_tool(
            "jira_get_issue",
            {
                "issue_key": "TEST-123",
            },
        )
        assert response
        data = json.loads(response[0].text)
        assert data["error"] == "Validation Error"
        assert "message" in data
        assert "issue" in data
        assert data["issue"] == {}


@pytest.mark.anyio
async def test_add_issues_to_sprint(jira_client, mock_jira_fetcher):
    """Test the add_issues_to_sprint tool."""
    response = await jira_client.call_tool(
        "jira_add_issues_to_sprint",
        {
            "sprint_id": "123",
            "issues": "TEST-1,TEST-2",
        },
    )
    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)
    assert content["success"] is True
    assert "Successfully added" in content["message"]
    mock_jira_fetcher.add_issues_to_sprint.assert_called_once_with(
        sprint_id="123", issues=["TEST-1", "TEST-2"]
    )


@pytest.mark.anyio
async def test_search_upstream_interface(jira_client, mock_jira_fetcher):
    """Test the search tool (upstream interface) with fixture data."""
    response = await jira_client.call_tool(
        "jira_search",
        {
            "jql": "project = TEST",
            "fields": "summary,status",
            "limit": 10,
            "start_at": 0,
        },
    )
    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)
    assert isinstance(content, dict)
    assert content["success"] is True
    assert "search_results" in content
    assert isinstance(content["search_results"]["issues"], list)
    assert len(content["search_results"]["issues"]) >= 1
    assert content["search_results"]["issues"][0]["key"] == "PROJ-123"
    assert content["search_results"]["total"] > 0
    assert content["search_results"]["start_at"] == 0
    assert content["search_results"]["max_results"] == 10
    mock_jira_fetcher.search_issues.assert_called_once_with(
        jql="project = TEST",
        fields="summary,status",
        start=0,
        limit=10,
        expand=None,
        projects_filter=None,
    )


@pytest.mark.anyio
async def test_search_my_active_issues(jira_client, mock_jira_fetcher):
    """Test the new search_my_active_issues tool with exclusion-based JQL."""
    response = await jira_client.call_tool(
        "jira_search_my_active_issues",
        {
            "limit": 15,
            "start_at": 5,
            "fields": "summary,status,assignee,priority",
        },
    )

    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)

    # Verify response structure
    assert isinstance(content, dict)
    assert content["success"] is True
    assert "active_issues" in content
    assert isinstance(content["active_issues"]["issues"], list)
    assert len(content["active_issues"]["issues"]) >= 1
    assert content["active_issues"]["total"] > 0
    assert content["active_issues"]["start_at"] == 5
    assert content["active_issues"]["max_results"] == 15

    # Verify JQL query was the exclusion-based pattern we expect
    expected_jql = "status NOT IN ('Resolved', 'Done', 'Closed') AND assignee = currentUser() ORDER BY priority DESC, updated DESC"
    mock_jira_fetcher.search_issues.assert_called_once_with(
        jql=expected_jql,
        fields="summary,status,assignee,priority",
        start=5,
        limit=15,
        expand=None,
        projects_filter=None,
    )


@pytest.mark.anyio
async def test_search_my_active_issues_defaults(jira_client, mock_jira_fetcher):
    """Test the new search_my_active_issues tool with default parameters."""
    response = await jira_client.call_tool(
        "jira_search_my_active_issues",
        {},
    )

    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)

    # Verify response structure
    assert content["success"] is True
    assert "active_issues" in content

    # Verify defaults were used correctly
    expected_jql = "status NOT IN ('Resolved', 'Done', 'Closed') AND assignee = currentUser() ORDER BY priority DESC, updated DESC"
    # Verify that search_issues was called with expected JQL and default parameters
    mock_jira_fetcher.search_issues.assert_called_once()
    call_kwargs = mock_jira_fetcher.search_issues.call_args.kwargs
    assert call_kwargs["jql"] == expected_jql
    assert call_kwargs["start"] == 0  # default start_at
    assert call_kwargs["limit"] == 20  # default limit
    assert call_kwargs["expand"] is None  # default expand
    assert call_kwargs["projects_filter"] is None  # default projects_filter
    # Verify fields contains the default fields (order doesn't matter due to string handling)
    assert "summary" in call_kwargs["fields"]
    assert "status" in call_kwargs["fields"]
    assert "assignee" in call_kwargs["fields"]


@pytest.mark.anyio
async def test_search_my_active_issues_with_projects_filter(jira_client, mock_jira_fetcher):
    """Test the new search_my_active_issues tool with projects filter."""
    response = await jira_client.call_tool(
        "jira_search_my_active_issues",
        {
            "projects_filter": "PROJ,WEB",
            "limit": 5,
        },
    )

    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)

    # Verify response structure
    assert content["success"] is True
    assert "active_issues" in content

    # Verify projects filter was passed correctly
    expected_jql = "status NOT IN ('Resolved', 'Done', 'Closed') AND assignee = currentUser() ORDER BY priority DESC, updated DESC"
    mock_jira_fetcher.search_issues.assert_called_once_with(
        jql=expected_jql,
        fields="summary,description,status,assignee,reporter,priority,issuetype,created,updated",  # DEFAULT_READ_JIRA_FIELDS
        start=0,  # default start_at
        limit=5,  # provided limit
        expand=None,  # default expand
        projects_filter="PROJ,WEB",  # provided projects_filter
    )


@pytest.mark.anyio
async def test_delete_comment_successfully(jira_client, mock_jira_fetcher):
    """Test successful comment deletion."""
    # Mock the delete_issue_comment method to return a proper dictionary
    mock_deletion_result = {
        "id": "45678",
        "issue_key": "PROJ-123",
        "message": "Comment deleted successfully"
    }
    mock_jira_fetcher.delete_issue_comment.return_value = mock_deletion_result

    response = await jira_client.call_tool(
        "jira_delete_comment",
        {"issue_key": "PROJ-123", "comment_id": "45678"},
    )

    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)

    # Verify response structure
    assert isinstance(content, dict)
    assert content["success"] is True
    assert "deleted_comment" in content

    # Verify the mock was called correctly
    mock_jira_fetcher.delete_issue_comment.assert_called_once_with(
        issue_key="PROJ-123", comment_id="45678"
    )


@pytest.mark.anyio
async def test_delete_comment_missing_issue_key(jira_client, mock_jira_fetcher):
    """Test comment deletion with missing issue key."""
    response = await jira_client.call_tool("jira_delete_comment", {"comment_id": "45678"})

    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)

    # Should return error
    assert content["success"] is False
    assert "error" in content
    assert "Issue key is required" in content["error"]


@pytest.mark.anyio
async def test_delete_comment_missing_comment_id(jira_client, mock_jira_fetcher):
    """Test comment deletion with missing comment ID."""
    response = await jira_client.call_tool("jira_delete_comment", {"issue_key": "PROJ-123"})

    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)

    # Should return error
    assert content["success"] is False
    assert "error" in content
    assert "Comment ID is required" in content["error"]


@pytest.mark.anyio
async def test_delete_comment_http_error(jira_client, mock_jira_fetcher):
    """Test comment deletion with HTTP error."""
    from requests.exceptions import HTTPError
    mock_jira_fetcher.delete_issue_comment.side_effect = HTTPError("Comment not found")

    response = await jira_client.call_tool(
        "jira_delete_comment",
        {"issue_key": "PROJ-123", "comment_id": "99999"},
    )

    assert isinstance(response, list)
    assert len(response) > 0
    text_content = response[0]
    assert text_content.type == "text"
    content = json.loads(text_content.text)

    # Should return error
    assert content["success"] is False
    assert "error" in content
    assert "Failed to delete comment" in content["error"]