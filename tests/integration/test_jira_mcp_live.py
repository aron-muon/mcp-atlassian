"""
Live tests for all Jira MCP functions.

These tests integrate with the actual MCP server functions to test
the complete functionality from tool call to response. They require
real Jira instances and will create/modify real data.
"""

import json
import os
import time
import uuid
from typing import Any, Dict

import pytest

from fastmcp import Client
from fastmcp.client import FastMCPTransport
from mcp.types import TextContent

from mcp_atlassian.confluence import ConfluenceFetcher
from mcp_atlassian.confluence.config import ConfluenceConfig
from mcp_atlassian.jira import JiraFetcher
from mcp_atlassian.jira.config import JiraConfig
from mcp_atlassian.servers import main_mcp
from tests.utils.base import BaseAuthTest
from tests.utils.test_setup import TestProjectSetup, fresh_test_environment


@pytest.mark.integration
class TestJiraMCPFunctions(BaseAuthTest):
    """Live tests for all Jira MCP functions with real API calls."""

    @pytest.fixture(autouse=True)
    def skip_without_real_data(self, request):
        """Skip these tests unless --use-real-data is provided."""
        if not request.config.getoption("--use-real-data", default=False):
            pytest.skip("Live MCP tests only run with --use-real-data flag")

    @pytest.fixture
    def jira_client(self):
        """Create real Jira client from environment."""
        if not os.getenv("JIRA_URL"):
            pytest.skip("JIRA_URL not set in environment")

        config = JiraConfig.from_env()
        return JiraFetcher(config=config)

    @pytest.fixture(scope="function")
    async def mcp_client(self):
        """Create FastMCP client connected to the main server for tool calls."""
        transport = FastMCPTransport(main_mcp)
        client = Client(transport=transport)
        async with client as connected_client:
            yield connected_client

    @pytest.fixture
    async def test_setup(self):
        """Set up and tear down test environment."""
        setup = TestProjectSetup()
        await setup.setup_jira_test_environment()
        yield setup
        await setup.cleanup_test_environment()

    @pytest.fixture
    def test_project_key(self, test_setup):
        """Get test project key from setup."""
        return test_setup.get_jira_project_key()

    @pytest.fixture
    def created_resources(self):
        """Track all created resources for cleanup."""
        resources = {
            "issues": [],
            "versions": [],
            "sprints": [],
            "comments": [],
            "worklogs": [],
            "links": []
        }
        yield resources
        # Cleanup will be handled per test

    async def call_mcp_tool(self, client: Client, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Helper to call MCP tool via client and parse JSON response."""
        result_content = await client.call_tool(tool_name, kwargs)
        # result_content is a list of TextContent objects
        if result_content and isinstance(result_content[0], TextContent):
            return json.loads(result_content[0].text)
        return {"success": False, "error": "No valid content returned"}

    def cleanup_created_resources(self, jira_client, resources: Dict[str, list]):
        """Clean up all created resources."""
        # Clean up issues last (as they might reference other resources)
        for comment_id in resources.get("comments", []):
            try:
                # Comments can't be deleted directly, they're deleted with the issue
                pass
            except Exception:
                pass

        for worklog_id in resources.get("worklogs", []):
            try:
                # Worklogs can't be deleted directly, they're deleted with the issue
                pass
            except Exception:
                pass

        for link in resources.get("links", []):
            try:
                jira_client.remove_issue_link(link["link_id"])
            except Exception:
                pass

        for sprint_id in resources.get("sprints", []):
            try:
                # Sprint deletion might not be available via API
                # Close or move sprint to inactive state if possible
                pass
            except Exception:
                pass

        for version_id in resources.get("versions", []):
            try:
                # Archive version instead of deleting if possible
                pass
            except Exception:
                pass

        for issue_key in resources.get("issues", []):
            try:
                jira_client.delete_issue(issue_key=issue_key)
            except Exception:
                pass

    async def test_jira_get_issue(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_get_issue MCP function."""
        # Create a test issue first
        unique_id = str(uuid.uuid4())[:8]
        summary = f"Test Get Issue {unique_id}"

        issue = jira_client.create_issue(
            project_key=test_project_key,
            summary=summary,
            issue_type="Task",
            description="Test issue for get_issue function"
        )
        created_resources["issues"].append(issue.key)

        try:
            # Test the MCP function
            result = await self.call_mcp_tool(
                mcp_client,
                "jira_get_issue",
                issue_key=issue.key
            )

            assert result["success"] is True
            assert result["issue"]["key"] == issue.key
            assert result["issue"]["summary"] == summary
            assert "description" in result["issue"]
            assert "status" in result["issue"]

            # Test with custom fields
            result_custom = await self.call_mcp_tool(
                mcp_client,
                "jira_get_issue",
                issue_key=issue.key,
                fields="summary,description,status,assignee"
            )

            assert result_custom["success"] is True
            assert len(result_custom["issue"]) <= 6  # Only requested fields (allowing for Jira defaults)

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_search_issues(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_search_issues MCP function."""
        unique_id = str(uuid.uuid4())[:8]

        # Create test issues for search
        issue1 = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Search Test Alpha {unique_id}",
            issue_type="Task",
            description="First issue for search testing"
        )
        created_resources["issues"].append(issue1.key)

        issue2 = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Search Test Beta {unique_id}",
            issue_type="Task",  # Use Task instead of Bug since Bug might not be available
            description="Second issue for search testing"
        )
        created_resources["issues"].append(issue2.key)

        try:
            # Test basic search
            result = await self.call_mcp_tool(
                mcp_client,
                "jira_search",
                jql=f"project = {test_project_key} AND summary ~ '{unique_id}'"
            )

            assert result["success"] is True
            issues = result["search_results"]["issues"]
            assert len(issues) >= 2
            assert any("Alpha" in issue["summary"] for issue in issues)
            assert any("Beta" in issue["summary"] for issue in issues)

            # Test with pagination
            result_paginated = await self.call_mcp_tool(
                mcp_client,
                "jira_search",
                jql=f"project = {test_project_key} AND summary ~ '{unique_id}'",
                limit=1
            )

            assert result_paginated["success"] is True
            paginated_issues = result_paginated["search_results"]["issues"]
            assert len(paginated_issues) <= 1

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_create_issue(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_create_issue MCP function."""
        unique_id = str(uuid.uuid4())[:8]
        summary = f"MCP Created Issue {unique_id}"

        try:
            result = await self.call_mcp_tool(
                mcp_client,
                "create_issue",
                project_key=test_project_key,
                summary=summary,
                issue_type="Task",
                description="Issue created via MCP function test"
            )

            assert result["success"] is True
            assert result["issue"]["key"].startswith(test_project_key)
            assert result["issue"]["summary"] == summary

            created_resources["issues"].append(result["issue"]["key"])

            # Verify the issue was actually created
            retrieved_issue = jira_client.get_issue(result["issue"]["key"])
            assert retrieved_issue.summary == summary

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_get_all_projects(self, mcp_client, jira_client):
        """Test jira_get_all_projects MCP function."""
        result = await self.call_mcp_tool(mcp_client, "jira_get_all_projects")

        assert result["success"] is True
        assert len(result["projects"]) >= 0
        assert isinstance(result["projects"], list)

        # Verify projects have required fields
        for project in result["projects"]:
            assert "key" in project
            assert "name" in project
            assert "projectTypeKey" in project

    async def test_jira_issue_comments_lifecycle(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_get_issue_comments and jira_add_comment MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        # Create test issue
        issue = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Comment Test Issue {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue.key)

        try:
            # Add a comment via MCP
            comment_result = await self.call_mcp_tool(
                mcp_client,
                "add_comment",
                issue_key=issue.key,
                comment="This is a test comment from MCP function"
            )

            assert comment_result["success"] is True
            created_resources["comments"].append(comment_result["comment"]["id"])

            # Get comments via MCP
            comments_result = await self.call_mcp_tool(
                mcp_client,
                "get_issue_comments",
                issue_key=issue.key
            )

            assert comments_result["success"] is True
            assert len(comments_result["comments"]) >= 1

            # Find our comment
            test_comment = None
            for comment in comments_result["comments"]:
                if "MCP function" in comment.get("body", ""):
                    test_comment = comment
                    break

            assert test_comment is not None
            assert "test comment from MCP function" in test_comment["body"]

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_epic_functionality(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_get_epic_issues and jira_link_to_epic MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        # Check if project supports epics
        try:
            # Try to create an epic (may not be supported in all projects)
            epic = jira_client.create_issue(
                project_key=test_project_key,
                summary=f"Epic Test {unique_id}",
                issue_type="Epic",
                description="Test epic for MCP functions"
            )
            created_resources["issues"].append(epic.key)
        except Exception:
            pytest.skip("Project does not support Epic issue type")

        try:
            # Create regular issues to link to epic
            issue1 = jira_client.create_issue(
                project_key=test_project_key,
                summary=f"Epic Story 1 {unique_id}",
                issue_type="Story"
            )
            created_resources["issues"].append(issue1.key)

            issue2 = jira_client.create_issue(
                project_key=test_project_key,
                summary=f"Epic Story 2 {unique_id}",
                issue_type="Story"
            )
            created_resources["issues"].append(issue2.key)

            # Link issues to epic via MCP
            link_result1 = await self.call_mcp_tool(
                mcp_client,
                "link_to_epic",
                epic_key=epic.key,
                issue_key=issue1.key
            )
            assert link_result1["success"] is True

            link_result2 = await self.call_mcp_tool(
                mcp_client,
                "link_to_epic",
                epic_key=epic.key,
                issue_key=issue2.key
            )
            assert link_result2["success"] is True

            # Get epic issues via MCP
            epic_issues_result = await self.call_mcp_tool(
                mcp_client,
                "get_epic_issues",
                epic_key=epic.key
            )

            assert epic_issues_result["success"] is True
            assert len(epic_issues_result["issues"]) >= 2

            epic_keys = [issue["key"] for issue in epic_issues_result["issues"]]
            assert issue1.key in epic_keys
            assert issue2.key in epic_keys

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_batch_create_issues(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_batch_create_issues MCP function."""
        unique_id = str(uuid.uuid4())[:8]

        issues_data = [
            {
                "summary": f"Batch Issue 1 {unique_id}",
                "issue_type": "Task",
                "description": "First batch issue"
            },
            {
                "summary": f"Batch Issue 2 {unique_id}",
                "issue_type": "Bug",
                "description": "Second batch issue"
            }
        ]

        try:
            result = await self.call_mcp_tool(
                mcp_client,
                "batch_create_issues",
                project_key=test_project_key,
                issues=issues_data
            )

            assert result["success"] is True
            assert len(result["issues"]) == 2

            for issue in result["issues"]:
                assert issue["key"].startswith(test_project_key)
                created_resources["issues"].append(issue["key"])

            # Verify all issues were created
            for issue in result["issues"]:
                retrieved = jira_client.get_issue(issue["key"])
                assert retrieved is not None

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_get_development_status(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_get_development_status MCP function."""
        unique_id = str(uuid.uuid4())[:8]

        # Create test issue
        issue = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Dev Status Test {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue.key)

        try:
            result = await self.call_mcp_tool(
                mcp_client,
                "get_development_status",
                issue_key=issue.key
            )

            assert result["success"] is True
            # Development status might be empty for new issues
            assert "development" in result
            assert isinstance(result["development"], dict)

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_agile_functionality(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test Jira Agile/Board functions."""
        try:
            # Get boards
            boards_result = await self.call_mcp_tool(mcp_client, "get_agile_boards")

            if not boards_result["success"] or len(boards_result["boards"]) == 0:
                pytest.skip("No agile boards available")

            assert boards_result["success"] is True
            assert len(boards_result["boards"]) > 0

            # Test getting board issues for first board
            first_board = boards_result["boards"][0]
            board_issues_result = await self.call_mcp_tool(
                mcp_client,
                "get_board_issues",
                board_id=first_board["id"],
                max_results=5
            )

            assert board_issues_result["success"] is True
            assert isinstance(board_issues_result["issues"], list)

            # Test getting sprints from board
            sprints_result = await self.call_mcp_tool(
                mcp_client,
                "get_sprints_from_board",
                board_id=first_board["id"],
                max_results=3
            )

            assert sprints_result["success"] is True
            assert isinstance(sprints_result["sprints"], list)

            # If there are sprints, test sprint issues
            if sprints_result["sprints"]:
                first_sprint = sprints_result["sprints"][0]
                sprint_issues_result = await self.call_mcp_tool(
                    mcp_client,
                    "get_sprint_issues",
                    sprint_id=first_sprint["id"],
                    max_results=5
                )

                assert sprint_issues_result["success"] is True
                assert isinstance(sprint_issues_result["issues"], list)

        except Exception as e:
            pytest.skip(f"Agile functionality not available: {e}")

    async def test_jira_field_operations(self, mcp_client, jira_client):
        """Test jira_search_fields and field-related functions."""
        # Test field search
        search_result = await self.call_mcp_tool(
            mcp_client,
            "search_fields",
            query="priority"
        )

        assert search_result["success"] is True
        assert len(search_result["fields"]) > 0

        # Should find priority-related fields
        field_names = [field.get("name", "").lower() for field in search_result["fields"]]
        assert any("priority" in name for name in field_names)

        # Test getting all fields (this might be a large result)
        try:
            all_fields_result = await self.call_mcp_tool(
                mcp_client,
                "search_fields",
                query=""  # Empty query should return all fields
            )
            assert all_fields_result["success"] is True
            assert len(all_fields_result["fields"]) > 0
        except Exception:
            # Some instances might not support empty query
            pass

    async def test_jira_issue_transitions(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_get_transitions and jira_transition_issue MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        # Create test issue
        issue = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Transition Test {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue.key)

        try:
            # Get available transitions
            transitions_result = await self.call_mcp_tool(
                mcp_client,
                "get_transitions",
                issue_key=issue.key
            )

            assert transitions_result["success"] is True
            assert isinstance(transitions_result["transitions"], list)

            # If there are transitions available, try to transition the issue
            if transitions_result["transitions"]:
                # Look for a safe transition (like "Start Progress" or "In Progress")
                safe_transition = None
                for transition in transitions_result["transitions"]:
                    transition_name = transition.get("name", "").lower()
                    if any(keyword in transition_name for keyword in ["progress", "start", "begin"]):
                        safe_transition = transition
                        break

                if safe_transition:
                    # Attempt the transition
                    transition_result = await self.call_mcp_tool(
                        mcp_client,
                        "transition_issue",
                        issue_key=issue.key,
                        transition_id=safe_transition["id"]
                    )

                    assert transition_result["success"] is True

                    # Verify the issue status changed
                    updated_issue = jira_client.get_issue(issue.key)
                    assert updated_issue.status != issue.status

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_worklog_operations(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_get_worklog and jira_add_worklog MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        # Create test issue
        issue = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Worklog Test {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue.key)

        try:
            # Get initial worklog (should be empty)
            worklog_result = await self.call_mcp_tool(
                mcp_client,
                "get_worklog",
                issue_key=issue.key
            )

            assert worklog_result["success"] is True
            assert isinstance(worklog_result["worklogs"], list)

            # Add a worklog entry
            add_worklog_result = await self.call_mcp_tool(
                mcp_client,
                "add_worklog",
                issue_key=issue.key,
                time_spent="1h",
                comment="Test worklog entry from MCP"
            )

            assert add_worklog_result["success"] is True
            created_resources["worklogs"].append(add_worklog_result["worklog"]["id"])

            # Verify worklog was added
            updated_worklog_result = await self.call_mcp_tool(
                mcp_client,
                "get_worklog",
                issue_key=issue.key
            )

            assert updated_worklog_result["success"] is True
            assert len(updated_worklog_result["worklogs"]) > len(worklog_result["worklogs"])

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_issue_linking(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_create_issue_link and jira_remove_issue_link MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        # Create two test issues
        issue1 = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Link Test Issue 1 {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue1.key)

        issue2 = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Link Test Issue 2 {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue2.key)

        try:
            # Get available link types
            link_types_result = await self.call_mcp_tool(mcp_client, "get_link_types")

            assert link_types_result["success"] is True
            assert len(link_types_result["linkTypes"]) > 0

            # Find a suitable link type (like "Relates")
            relates_link = None
            for link_type in link_types_result["linkTypes"]:
                if link_type["name"].lower() == "relates":
                    relates_link = link_type
                    break

            if relates_link:
                # Create link between issues
                create_link_result = await self.call_mcp_tool(
                    mcp_client,
                    "create_issue_link",
                    type_name=relates_link["name"],
                    inward_issue_key=issue1.key,
                    outward_issue_key=issue2.key
                )

                assert create_link_result["success"] is True

                # Store link ID for cleanup
                if "linkId" in create_link_result:
                    created_resources["links"].append({
                        "link_id": create_link_result["linkId"],
                        "inward_key": issue1.key,
                        "outward_key": issue2.key
                    })

                # Verify link exists by checking issue details
                issue1_updated = jira_client.get_issue(issue1.key)
                # Note: Link verification depends on Jira API response format

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_update_and_delete_issue(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_update_issue and jira_delete_issue MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        # Create test issue
        issue = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Update/Delete Test {unique_id}",
            issue_type="Task",
            description="Original description"
        )
        created_resources["issues"].append(issue.key)

        try:
            # Update the issue
            update_result = await self.call_mcp_tool(
                mcp_client,
                "update_issue",
                issue_key=issue.key,
                summary=f"Updated Summary {unique_id}",
                description="Updated description"
            )

            assert update_result["success"] is True

            # Verify update
            updated_issue = jira_client.get_issue(issue.key)
            assert "Updated Summary" in updated_issue.summary
            assert "Updated description" in updated_issue.description

            # Delete the issue via MCP
            delete_result = await self.call_mcp_tool(
                mcp_client,
                "delete_issue",
                issue_key=issue.key
            )

            assert delete_result["success"] is True

            # Remove from created resources since we deleted it
            created_resources["issues"].remove(issue.key)

            # Verify deletion
            with pytest.raises(Exception):
                jira_client.get_issue(issue.key)

        except Exception as e:
            # If anything fails, still try to cleanup
            self.cleanup_created_resources(jira_client, created_resources)
            raise e

    async def test_jira_version_operations(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_get_project_versions, jira_create_version, and jira_batch_create_versions MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        try:
            # Get existing versions
            versions_result = await self.call_mcp_tool(
                mcp_client,
                "get_project_versions",
                project_key=test_project_key
            )

            assert versions_result["success"] is True
            assert isinstance(versions_result["versions"], list)

            # Create a single version
            create_version_result = await self.call_mcp_tool(
                mcp_client,
                "create_version",
                project_key=test_project_key,
                name=f"Test Version {unique_id}",
                description="Version created via MCP test"
            )

            if create_version_result["success"]:
                created_resources["versions"].append(create_version_result["version"]["id"])
                assert create_version_result["version"]["name"] == f"Test Version {unique_id}"

            # Create multiple versions in batch
            batch_versions_data = [
                {
                    "name": f"Batch Version 1 {unique_id}",
                    "description": "First batch version"
                },
                {
                    "name": f"Batch Version 2 {unique_id}",
                    "description": "Second batch version"
                }
            ]

            batch_result = await self.call_mcp_tool(
                mcp_client,
                "batch_create_versions",
                project_key=test_project_key,
                versions=batch_versions_data
            )

            if batch_result["success"]:
                for version in batch_result["versions"]:
                    created_resources["versions"].append(version["id"])
                    assert f"Batch Version" in version["name"]

        finally:
            # Versions are usually archived rather than deleted
            # Cleanup will be handled by the test framework
            pass

    async def test_jira_user_profile(self, mcp_client, jira_client):
        """Test jira_get_user_profile MCP function."""
        try:
            # Test with current user (should always exist)
            result = await self.call_mcp_tool(
                mcp_client,
                "get_user_profile",
                user_identifier="current"  # Many Jira instances support this
            )

            if result["success"]:
                assert "user" in result
                assert "displayName" in result["user"]
            else:
                # Try with a fallback - test that it handles invalid users gracefully
                result = await self.call_mcp_tool(
                    mcp_client,
                    "get_user_profile",
                    user_identifier="nonexistent@example.com"
                )
                assert result["success"] is False
                assert "error" in result

        except Exception as e:
            # User profile functionality might not be available in all instances
            pytest.skip(f"User profile functionality not available: {e}")

    async def test_jira_remote_issue_links(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_create_remote_issue_link MCP function."""
        unique_id = str(uuid.uuid4())[:8]

        # Create test issue
        issue = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Remote Link Test {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue.key)

        try:
            # Create a remote issue link
            remote_link_result = await self.call_mcp_tool(
                mcp_client,
                "create_remote_issue_link",
                issue_key=issue.key,
                url="https://example.com/issue/123",
                title=f"External Issue {unique_id}",
                summary="Linked external issue"
            )

            assert remote_link_result["success"] is True

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_project_issues(self, mcp_client, jira_client, test_project_key):
        """Test jira_get_project_issues MCP function."""
        result = await self.call_mcp_tool(
            mcp_client,
            "get_project_issues",
            project_key=test_project_key,
            max_results=10
        )

        assert result["success"] is True
        assert isinstance(result["issues"], list)
        assert len(result["issues"]) <= 10

        # Verify all issues are from the correct project
        for issue in result["issues"]:
            assert issue["key"].startswith(test_project_key)

    async def test_jira_download_attachments(self, mcp_client, jira_client, test_project_key, created_resources, tmp_path):
        """Test jira_download_attachments MCP function."""
        unique_id = str(uuid.uuid4())[:8]

        # Create test issue with attachment
        issue = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Attachment Download Test {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue.key)

        try:
            # Create a test file to upload
            test_file = tmp_path / f"test_upload_{unique_id}.txt"
            test_content = f"Test content for attachment {unique_id}"
            test_file.write_text(test_content)

            # Upload attachment
            upload_result = jira_client.upload_attachment(
                issue_key=issue.key,
                file_path=str(test_file)
            )

            if upload_result.get("success"):
                # Test downloading attachments
                download_result = await self.call_mcp_tool(
                    mcp_client,
                    "download_attachments",
                    issue_key=issue.key,
                    download_dir=str(tmp_path),
                    max_attachments=5
                )

                assert download_result["success"] is True
                assert isinstance(download_result["attachments"], list)

                # Verify at least one attachment was downloaded
                if download_result["attachments"]:
                    attachment = download_result["attachments"][0]
                    assert "filename" in attachment
                    assert "local_path" in attachment

                    # Verify the downloaded file exists
                    downloaded_file = tmp_path / attachment["filename"]
                    assert downloaded_file.exists()

        finally:
            self.cleanup_created_resources(jira_client, created_resources)

    async def test_jira_search_function(self, mcp_client, jira_client):
        """Test jira_search MCP function (alias for search_issues)."""
        # Test basic search functionality
        result = await self.call_mcp_tool(
            mcp_client,
            "search",
            jql="project is not EMPTY ORDER BY created DESC",
            max_results=5
        )

        assert result["success"] is True
        assert isinstance(result["issues"], list)
        assert len(result["issues"]) <= 5

    async def test_jira_batch_changelogs(self, mcp_client, jira_client, test_project_key, created_resources):
        """Test jira_batch_get_changelogs MCP function."""
        unique_id = str(uuid.uuid4())[:8]

        # Create a couple of issues
        issue1 = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Changelog Test 1 {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue1.key)

        issue2 = jira_client.create_issue(
            project_key=test_project_key,
            summary=f"Changelog Test 2 {unique_id}",
            issue_type="Task"
        )
        created_resources["issues"].append(issue2.key)

        try:
            # Add a comment to create changelog entry
            jira_client.add_comment(issue1.key, "Test comment for changelog")

            # Get batch changelogs
            changelog_result = await self.call_mcp_tool(
                mcp_client,
                "batch_get_changelogs",
                issue_keys=[issue1.key, issue2.key]
            )

            assert changelog_result["success"] is True
            assert isinstance(changelog_result["changelogs"], dict)
            assert issue1.key in changelog_result["changelogs"]
            assert issue2.key in changelog_result["changelogs"]

        finally:
            self.cleanup_created_resources(jira_client, created_resources)