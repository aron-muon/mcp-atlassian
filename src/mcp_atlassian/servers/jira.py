"""Jira FastMCP server instance and tool definitions."""

import json
import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field
from requests.exceptions import HTTPError

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.jira.constants import DEFAULT_READ_JIRA_FIELDS
from mcp_atlassian.models.jira.common import JiraUser
from mcp_atlassian.servers.dependencies import get_jira_fetcher
from mcp_atlassian.utils.decorators import check_write_access, handle_tool_errors

logger = logging.getLogger(__name__)


def register_jira_tools(jira_mcp: FastMCP) -> None:
    @jira_mcp.tool(tags={"jira", "read"})
    async def get_user_profile(
        ctx: Context,
        user_identifier: Annotated[
            str,
            Field(
                description="Identifier for the user (e.g., email address 'user@example.com', username 'johndoe', account ID 'accountid:...', or key for Server/DC)."
            ),
        ],
    ) -> str:
        """
        Retrieve profile information for a specific Jira user.

        Args:
            ctx: The FastMCP context.
            user_identifier: User identifier (email, username, key, or account ID).

        Returns:
            JSON string representing the Jira user profile object, or an error object if not found.

        Raises:
            ValueError: If the Jira client is not configured or available.
        """
        jira = await get_jira_fetcher(ctx)
        try:
            user: JiraUser = jira.get_user_profile_by_identifier(user_identifier)
            result = user.to_simplified_dict()
            response_data = {"success": True, "user": result}
        except Exception as e:
            error_message = ""
            log_level = logging.ERROR
            if isinstance(e, ValueError) and "not found" in str(e).lower():
                log_level = logging.WARNING
                error_message = str(e)
            elif isinstance(e, MCPAtlassianAuthenticationError):
                error_message = f"Authentication/Permission Error: {str(e)}"
            elif isinstance(e, OSError | HTTPError):
                error_message = f"Network or API Error: {str(e)}"
            else:
                error_message = (
                    "An unexpected error occurred while fetching the user profile."
                )
                logger.exception(
                    f"Unexpected error in get_user_profile for '{user_identifier}':"
                )
            error_result = {
                "success": False,
                "error": str(e),
                "user_identifier": user_identifier,
            }
            logger.log(
                log_level,
                f"get_user_profile failed for '{user_identifier}': {error_message}",
            )
            response_data = error_result
        return json.dumps(response_data, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_issue(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="Jira issue key (e.g., 'PROJ-123')")
        ],
        fields: Annotated[
            str,
            Field(
                description=(
                    "(Optional) Comma-separated list of fields to return (e.g., 'summary,status,customfield_10010'). "
                    "You may also provide a single field as a string (e.g., 'duedate'). "
                    "Use '*all' for all fields (including custom fields), or omit for essential fields only."
                ),
                default=",".join(DEFAULT_READ_JIRA_FIELDS),
            ),
        ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
        expand: Annotated[
            str | None,
            Field(
                description=(
                    "(Optional) Fields to expand. Examples: 'renderedFields' (for rendered content), "
                    "'transitions' (for available status transitions), 'changelog' (for history)"
                ),
                default=None,
            ),
        ] = None,
        comment_limit: Annotated[
            int,
            Field(
                description="Maximum number of comments to include (0 or null for no comments)",
                default=10,
                ge=0,
                le=100,
            ),
        ] = 10,
        properties: Annotated[
            str | None,
            Field(
                description="(Optional) A comma-separated list of issue properties to return",
                default=None,
            ),
        ] = None,
        update_history: Annotated[
            bool,
            Field(
                description="Whether to update the issue view history for the requesting user",
                default=True,
            ),
        ] = True,
    ) -> str:
        """Get details of a specific Jira issue including its Epic links and relationship information.

        Args:
            ctx: The FastMCP context.
            issue_key: Jira issue key.
            fields: Comma-separated list of fields to return (e.g., 'summary,status,customfield_10010'), a single field as a string (e.g., 'duedate'), '*all' for all fields, or omitted for essentials.
            expand: Optional fields to expand.
            comment_limit: Maximum number of comments.
            properties: Issue properties to return.
            update_history: Whether to update issue view history.

        Returns:
            JSON string representing the Jira issue object.

        Raises:
            ValueError: If the Jira client is not configured or available.
        """
        jira = await get_jira_fetcher(ctx)
        fields_list: str | list[str] | None = fields
        if fields and fields != "*all":
            fields_list = [f.strip() for f in fields.split(",")]

        issue = jira.get_issue(
            issue_key=issue_key,
            fields=fields_list,
            expand=expand,
            comment_limit=comment_limit,
            properties=properties.split(",") if properties else None,
            update_history=update_history,
        )
        result = issue.to_simplified_dict()
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def search(
        ctx: Context,
        jql: Annotated[
            str,
            Field(
                description=(
                    "JQL query string (Jira Query Language). Examples:\n"
                    '- Find Epics: "issuetype = Epic AND project = PROJ"\n'
                    '- Find issues in Epic: "parent = PROJ-123"\n'
                    "- Find by status: \"status = 'In Progress' AND project = PROJ\"\n"
                    '- Find by assignee: "assignee = currentUser()"\n'
                    '- Find recently updated: "updated >= -7d AND project = PROJ"\n'
                    '- Find by label: "labels = frontend AND project = PROJ"\n'
                    '- Find by priority: "priority = High AND project = PROJ"'
                )
            ),
        ],
        fields: Annotated[
            str,
            Field(
                description=(
                    "(Optional) Comma-separated fields to return in the results. "
                    "Use '*all' for all fields, or specify individual fields like 'summary,status,assignee,priority'"
                ),
                default=",".join(DEFAULT_READ_JIRA_FIELDS),
            ),
        ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
        limit: Annotated[
            int,
            Field(description="Maximum number of results (1-50)", default=10, ge=1),
        ] = 10,
        start_at: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based)", default=0, ge=0
            ),
        ] = 0,
        projects_filter: Annotated[
            str | None,
            Field(
                description=(
                    "(Optional) Comma-separated list of project keys to filter results by. "
                    "Overrides the environment variable JIRA_PROJECTS_FILTER if provided."
                ),
                default=None,
            ),
        ] = None,
        expand: Annotated[
            str | None,
            Field(
                description=(
                    "(Optional) fields to expand. Examples: 'renderedFields', 'transitions', 'changelog'"
                ),
                default=None,
            ),
        ] = None,
    ) -> str:
        """Search Jira issues using JQL (Jira Query Language).

        Args:
            ctx: The FastMCP context.
            jql: JQL query string.
            fields: Comma-separated fields to return.
            limit: Maximum number of results.
            start_at: Starting index for pagination.
            projects_filter: Comma-separated list of project keys to filter by.
            expand: Optional fields to expand.

        Returns:
            JSON string representing the search results including pagination info.
        """
        jira = await get_jira_fetcher(ctx)
        fields_list: str | list[str] | None = fields
        if fields and fields != "*all":
            fields_list = [f.strip() for f in fields.split(",")]

        search_result = jira.search_issues(
            jql=jql,
            fields=fields_list,
            limit=limit,
            start=start_at,
            expand=expand,
            projects_filter=projects_filter,
        )
        result = search_result.to_simplified_dict()
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def search_fields(
        ctx: Context,
        keyword: Annotated[
            str,
            Field(
                description="Keyword for fuzzy search. If left empty, lists the first 'limit' available fields in their default order.",
                default="",
            ),
        ] = "",
        limit: Annotated[
            int, Field(description="Maximum number of results", default=10, ge=1)
        ] = 10,
        refresh: Annotated[
            bool,
            Field(description="Whether to force refresh the field list", default=False),
        ] = False,
    ) -> str:
        """Search Jira fields by keyword with fuzzy match.

        Args:
            ctx: The FastMCP context.
            keyword: Keyword for fuzzy search.
            limit: Maximum number of results.
            refresh: Whether to force refresh the field list.

        Returns:
            JSON string representing a list of matching field definitions.
        """
        jira = await get_jira_fetcher(ctx)
        result = jira.search_fields(keyword, limit=limit, refresh=refresh)
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_project_issues(
        ctx: Context,
        project_key: Annotated[str, Field(description="The project key")],
        limit: Annotated[
            int,
            Field(
                description="Maximum number of results (1-50)", default=10, ge=1, le=50
            ),
        ] = 10,
        start_at: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based)", default=0, ge=0
            ),
        ] = 0,
    ) -> str:
        """Get all issues for a specific Jira project.

        Args:
            ctx: The FastMCP context.
            project_key: The project key.
            limit: Maximum number of results.
            start_at: Starting index for pagination.

        Returns:
            JSON string representing the search results including pagination info.
        """
        jira = await get_jira_fetcher(ctx)
        search_result = jira.get_project_issues(
            project_key=project_key, start=start_at, limit=limit
        )
        result = search_result.to_simplified_dict()
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_transitions(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="Jira issue key (e.g., 'PROJ-123')")
        ],
    ) -> str:
        """Get available status transitions for a Jira issue.

        Args:
            ctx: The FastMCP context.
            issue_key: Jira issue key.

        Returns:
            JSON string representing a list of available transitions.
        """
        jira = await get_jira_fetcher(ctx)
        # Underlying method returns list[dict] in the desired format
        transitions = jira.get_available_transitions(issue_key)
        return json.dumps(transitions, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_worklog(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="Jira issue key (e.g., 'PROJ-123')")
        ],
    ) -> str:
        """Get worklog entries for a Jira issue.

        Args:
            ctx: The FastMCP context.
            issue_key: Jira issue key.

        Returns:
            JSON string representing the worklog entries.
        """
        jira = await get_jira_fetcher(ctx)
        worklogs = jira.get_worklogs(issue_key)
        result = {"worklogs": worklogs}
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def download_attachments(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="Jira issue key (e.g., 'PROJ-123')")
        ],
        target_dir: Annotated[
            str, Field(description="Directory where attachments should be saved")
        ],
    ) -> str:
        """Download attachments from a Jira issue.

        Args:
            ctx: The FastMCP context.
            issue_key: Jira issue key.
            target_dir: Directory to save attachments.

        Returns:
            JSON string indicating the result of the download operation.
        """
        jira = await get_jira_fetcher(ctx)
        result = jira.download_issue_attachments(
            issue_key=issue_key, target_dir=target_dir
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_agile_boards(
        ctx: Context,
        board_name: Annotated[
            str | None,
            Field(description="(Optional) The name of board, support fuzzy search"),
        ] = None,
        project_key: Annotated[
            str | None,
            Field(description="(Optional) Jira project key (e.g., 'PROJ-123')"),
        ] = None,
        board_type: Annotated[
            str | None,
            Field(
                description="(Optional) The type of jira board (e.g., 'scrum', 'kanban')"
            ),
        ] = None,
        start_at: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based)", default=0, ge=0
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of results (1-50)", default=10, ge=1, le=50
            ),
        ] = 10,
    ) -> str:
        """Get jira agile boards by name, project key, or type.

        Args:
            ctx: The FastMCP context.
            board_name: Name of the board (fuzzy search).
            project_key: Project key.
            board_type: Board type ('scrum' or 'kanban').
            start_at: Starting index.
            limit: Maximum results.

        Returns:
            JSON string representing a list of board objects.
        """
        jira = await get_jira_fetcher(ctx)
        boards = jira.get_all_agile_boards_model(
            board_name=board_name,
            project_key=project_key,
            board_type=board_type,
            start=start_at,
            limit=limit,
        )
        result = [board.to_simplified_dict() for board in boards]
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_board_issues(
        ctx: Context,
        board_id: Annotated[
            str, Field(description="The id of the board (e.g., '1001')")
        ],
        jql: Annotated[
            str,
            Field(
                description=(
                    "JQL query string (Jira Query Language). Examples:\n"
                    '- Find Epics: "issuetype = Epic AND project = PROJ"\n'
                    '- Find issues in Epic: "parent = PROJ-123"\n'
                    "- Find by status: \"status = 'In Progress' AND project = PROJ\"\n"
                    '- Find by assignee: "assignee = currentUser()"\n'
                    '- Find recently updated: "updated >= -7d AND project = PROJ"\n'
                    '- Find by label: "labels = frontend AND project = PROJ"\n'
                    '- Find by priority: "priority = High AND project = PROJ"'
                )
            ),
        ],
        fields: Annotated[
            str,
            Field(
                description=(
                    "Comma-separated fields to return in the results. "
                    "Use '*all' for all fields, or specify individual "
                    "fields like 'summary,status,assignee,priority'"
                ),
                default=",".join(DEFAULT_READ_JIRA_FIELDS),
            ),
        ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
        start_at: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based)", default=0, ge=0
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of results (1-50)", default=10, ge=1, le=50
            ),
        ] = 10,
        expand: Annotated[
            str,
            Field(
                description="Optional fields to expand in the response (e.g., 'changelog').",
                default="version",
            ),
        ] = "version",
    ) -> str:
        """Get all issues linked to a specific board filtered by JQL.

        Args:
            ctx: The FastMCP context.
            board_id: The ID of the board.
            jql: JQL query string to filter issues.
            fields: Comma-separated fields to return.
            start_at: Starting index for pagination.
            limit: Maximum number of results.
            expand: Optional fields to expand.

        Returns:
            JSON string representing the search results including pagination info.
        """
        jira = await get_jira_fetcher(ctx)
        fields_list: str | list[str] | None = fields
        if fields and fields != "*all":
            fields_list = [f.strip() for f in fields.split(",")]

        search_result = jira.get_board_issues(
            board_id=board_id,
            jql=jql,
            fields=fields_list,
            start=start_at,
            limit=limit,
            expand=expand,
        )
        result = search_result.to_simplified_dict()
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_sprints_from_board(
        ctx: Context,
        board_id: Annotated[str, Field(description="The id of board (e.g., '1000')")],
        state: Annotated[
            str | None,
            Field(description="Sprint state (e.g., 'active', 'future', 'closed')"),
        ] = None,
        start_at: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based)", default=0, ge=0
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of results (1-50)", default=10, ge=1, le=50
            ),
        ] = 10,
    ) -> str:
        """Get jira sprints from board by state.

        Args:
            ctx: The FastMCP context.
            board_id: The ID of the board.
            state: Sprint state ('active', 'future', 'closed'). If None, returns all sprints.
            start_at: Starting index.
            limit: Maximum results.

        Returns:
            JSON string representing a list of sprint objects.
        """
        jira = await get_jira_fetcher(ctx)
        sprints = jira.get_all_sprints_from_board_model(
            board_id=board_id, state=state, start=start_at, limit=limit
        )
        result = [sprint.to_simplified_dict() for sprint in sprints]
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_sprint_issues(
        ctx: Context,
        sprint_id: Annotated[
            str, Field(description="The id of sprint (e.g., '10001')")
        ],
        fields: Annotated[
            str,
            Field(
                description=(
                    "Comma-separated fields to return in the results. "
                    "Use '*all' for all fields, or specify individual "
                    "fields like 'summary,status,assignee,priority'"
                ),
                default=",".join(DEFAULT_READ_JIRA_FIELDS),
            ),
        ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
        start_at: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based)", default=0, ge=0
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of results (1-50)", default=10, ge=1, le=50
            ),
        ] = 10,
    ) -> str:
        """Get jira issues from sprint.

        Args:
            ctx: The FastMCP context.
            sprint_id: The ID of the sprint.
            fields: Comma-separated fields to return.
            start_at: Starting index.
            limit: Maximum results.

        Returns:
            JSON string representing the search results including pagination info.
        """
        jira = await get_jira_fetcher(ctx)
        fields_list: str | list[str] | None = fields
        if fields and fields != "*all":
            fields_list = [f.strip() for f in fields.split(",")]

        search_result = jira.get_sprint_issues(
            sprint_id=sprint_id, fields=fields_list, start=start_at, limit=limit
        )
        result = search_result.to_simplified_dict()
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_link_types(ctx: Context) -> str:
        """Get all available issue link types.

        Args:
            ctx: The FastMCP context.

        Returns:
            JSON string representing a list of issue link type objects.
        """
        jira = await get_jira_fetcher(ctx)
        link_types = jira.get_issue_link_types()
        formatted_link_types = [
            link_type.to_simplified_dict() for link_type in link_types
        ]
        return json.dumps(formatted_link_types, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def create_issue(
        ctx: Context,
        project_key: Annotated[
            str,
            Field(
                description=(
                    "The JIRA project key (e.g. 'PROJ', 'DEV', 'SUPPORT'). "
                    "This is the prefix of issue keys in your project. "
                    "Never assume what it might be, always ask the user."
                )
            ),
        ],
        summary: Annotated[str, Field(description="Summary/title of the issue")],
        issue_type: Annotated[
            str,
            Field(
                description=(
                    "Issue type (e.g. 'Task', 'Bug', 'Story', 'Epic', 'Subtask'). "
                    "The available types depend on your project configuration. "
                    "For subtasks, use 'Subtask' (not 'Sub-task') and include parent in additional_fields."
                ),
            ),
        ],
        assignee: Annotated[
            str | None,
            Field(
                description="(Optional) Assignee's user identifier (string): Email, display name, or account ID (e.g., 'user@example.com', 'John Doe', 'accountid:...')",
                default=None,
            ),
        ] = None,
        description: Annotated[
            str | None, Field(description="Issue description", default=None)
        ] = None,
        components: Annotated[
            str | None,
            Field(
                description="(Optional) Comma-separated list of component names to assign (e.g., 'Frontend,API')",
                default=None,
            ),
        ] = None,
        additional_fields: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "(Optional) Dictionary of additional fields to set. Examples:\n"
                    "- Set priority: {'priority': {'name': 'High'}}\n"
                    "- Add labels: {'labels': ['frontend', 'urgent']}\n"
                    "- Link to parent (for any issue type): {'parent': 'PROJ-123'}\n"
                    "- Set Fix Version/s: {'fixVersions': [{'id': '10020'}]}\n"
                    "- Custom fields: {'customfield_10010': 'value'}"
                ),
                default=None,
            ),
        ] = None,
    ) -> str:
        """Create a new Jira issue with optional Epic link or parent for subtasks.

        Args:
            ctx: The FastMCP context.
            project_key: The JIRA project key.
            summary: Summary/title of the issue.
            issue_type: Issue type (e.g., 'Task', 'Bug', 'Story', 'Epic', 'Subtask').
            assignee: Assignee's user identifier (string): Email, display name, or account ID (e.g., 'user@example.com', 'John Doe', 'accountid:...').
            description: Issue description.
            components: Comma-separated list of component names.
            additional_fields: Dictionary of additional fields.

        Returns:
            JSON string representing the created issue object.

        Raises:
            ValueError: If in read-only mode or Jira client is unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        # Parse components from comma-separated string to list
        components_list = None
        if components and isinstance(components, str):
            components_list = [
                comp.strip() for comp in components.split(",") if comp.strip()
            ]

        # Use additional_fields directly as dict
        extra_fields = additional_fields or {}
        if not isinstance(extra_fields, dict):
            raise ValueError("additional_fields must be a dictionary.")

        issue = jira.create_issue(
            project_key=project_key,
            summary=summary,
            issue_type=issue_type,
            description=description,
            assignee=assignee,
            components=components_list,
            **extra_fields,
        )
        result = issue.to_simplified_dict()
        return json.dumps(
            {"message": "Issue created successfully", "issue": result},
            indent=2,
            ensure_ascii=False,
        )

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def batch_create_issues(
        ctx: Context,
        issues: Annotated[
            str,
            Field(
                description=(
                    "JSON array of issue objects. Each object should contain:\n"
                    "- project_key (required): The project key (e.g., 'PROJ')\n"
                    "- summary (required): Issue summary/title\n"
                    "- issue_type (required): Type of issue (e.g., 'Task', 'Bug')\n"
                    "- description (optional): Issue description\n"
                    "- assignee (optional): Assignee username or email\n"
                    "- components (optional): Array of component names\n"
                    "Example: [\n"
                    '  {"project_key": "PROJ", "summary": "Issue 1", "issue_type": "Task"},\n'
                    '  {"project_key": "PROJ", "summary": "Issue 2", "issue_type": "Bug", "components": ["Frontend"]}\n'
                    "]"
                )
            ),
        ],
        validate_only: Annotated[
            bool,
            Field(
                description="If true, only validates the issues without creating them",
                default=False,
            ),
        ] = False,
    ) -> str:
        """Create multiple Jira issues in a batch.

        Args:
            ctx: The FastMCP context.
            issues: JSON array string of issue objects.
            validate_only: If true, only validates without creating.

        Returns:
            JSON string indicating success and listing created issues (or validation result).

        Raises:
            ValueError: If in read-only mode, Jira client unavailable, or invalid JSON.
        """
        jira = await get_jira_fetcher(ctx)
        # Parse issues from JSON string
        try:
            issues_list = json.loads(issues)
            if not isinstance(issues_list, list):
                raise ValueError("Input 'issues' must be a JSON array string.")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in issues")
        except Exception as e:
            raise ValueError(f"Invalid input for issues: {e}") from e

        # Create issues in batch
        created_issues = jira.batch_create_issues(
            issues_list, validate_only=validate_only
        )

        message = (
            "Issues validated successfully"
            if validate_only
            else "Issues created successfully"
        )
        result = {
            "message": message,
            "issues": [issue.to_simplified_dict() for issue in created_issues],
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def batch_get_changelogs(
        ctx: Context,
        issue_ids_or_keys: Annotated[
            list[str],
            Field(
                description="List of Jira issue IDs or keys, e.g. ['PROJ-123', 'PROJ-124']"
            ),
        ],
        fields: Annotated[
            list[str] | None,
            Field(
                description="(Optional) Filter the changelogs by fields, e.g. ['status', 'assignee']. Default to None for all fields.",
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description=(
                    "Maximum number of changelogs to return in result for each issue. "
                    "Default to -1 for all changelogs. "
                    "Notice that it only limits the results in the response, "
                    "the function will still fetch all the data."
                ),
                default=-1,
            ),
        ] = -1,
    ) -> str:
        """Get changelogs for multiple Jira issues (Cloud only).

        Args:
            ctx: The FastMCP context.
            issue_ids_or_keys: List of issue IDs or keys.
            fields: List of fields to filter changelogs by. None for all fields.
            limit: Maximum changelogs per issue (-1 for all).

        Returns:
            JSON string representing a list of issues with their changelogs.

        Raises:
            NotImplementedError: If run on Jira Server/Data Center.
            ValueError: If Jira client is unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        # Ensure this runs only on Cloud, as per original function docstring
        if not jira.config.is_cloud:
            raise NotImplementedError(
                "Batch get issue changelogs is only available on Jira Cloud."
            )

        # Call the underlying method
        issues_with_changelogs = jira.batch_get_changelogs(
            issue_ids_or_keys=issue_ids_or_keys, fields=fields
        )

        # Format the response
        results = []
        limit_val = None if limit == -1 else limit
        for issue in issues_with_changelogs:
            results.append(
                {
                    "issue_id": issue.id,
                    "changelogs": [
                        changelog.to_simplified_dict()
                        for changelog in issue.changelogs[:limit_val]
                    ],
                }
            )
        return json.dumps(results, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def update_issue(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="Jira issue key (e.g., 'PROJ-123')")
        ],
        fields: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Dictionary of fields to update. For 'assignee', provide a string identifier (email, name, or accountId). "
                    "Example: `{'assignee': 'user@example.com', 'summary': 'New Summary'}`"
                )
            ),
        ],
        additional_fields: Annotated[
            dict[str, Any] | None,
            Field(
                description="(Optional) Dictionary of additional fields to update. Use this for custom fields or more complex updates.",
                default=None,
            ),
        ] = None,
        attachments: Annotated[
            str | None,
            Field(
                description=(
                    "(Optional) JSON string array or comma-separated list of file paths to attach to the issue. "
                    "Example: '/path/to/file1.txt,/path/to/file2.txt' or ['/path/to/file1.txt','/path/to/file2.txt']"
                ),
                default=None,
            ),
        ] = None,
    ) -> str:
        """Update an existing Jira issue including changing status, adding Epic links, updating fields, etc.

        Args:
            ctx: The FastMCP context.
            issue_key: Jira issue key.
            fields: Dictionary of fields to update.
            additional_fields: Optional dictionary of additional fields.
            attachments: Optional JSON array string or comma-separated list of file paths.

        Returns:
            JSON string representing the updated issue object and attachment results.

        Raises:
            ValueError: If in read-only mode or Jira client unavailable, or invalid input.
        """
        jira = await get_jira_fetcher(ctx)
        # Use fields directly as dict
        if not isinstance(fields, dict):
            raise ValueError("fields must be a dictionary.")
        update_fields = fields

        # Use additional_fields directly as dict
        extra_fields = additional_fields or {}
        if not isinstance(extra_fields, dict):
            raise ValueError("additional_fields must be a dictionary.")

        # Parse attachments
        attachment_paths = []
        if attachments:
            if isinstance(attachments, str):
                try:
                    parsed = json.loads(attachments)
                    if isinstance(parsed, list):
                        attachment_paths = [str(p) for p in parsed]
                    else:
                        raise ValueError("attachments JSON string must be an array.")
                except json.JSONDecodeError:
                    # Assume comma-separated if not valid JSON array
                    attachment_paths = [
                        p.strip() for p in attachments.split(",") if p.strip()
                    ]
            else:
                raise ValueError(
                    "attachments must be a JSON array string or comma-separated string."
                )

        # Combine fields and additional_fields
        all_updates = {**update_fields, **extra_fields}
        if attachment_paths:
            all_updates["attachments"] = attachment_paths

        try:
            issue = jira.update_issue(issue_key=issue_key, **all_updates)
            result = issue.to_simplified_dict()
            if (
                hasattr(issue, "custom_fields")
                and "attachment_results" in issue.custom_fields
            ):
                result["attachment_results"] = issue.custom_fields["attachment_results"]
            return json.dumps(
                {"message": "Issue updated successfully", "issue": result},
                indent=2,
                ensure_ascii=False,
            )
        except Exception as e:
            logger.error(f"Error updating issue {issue_key}: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to update issue {issue_key}: {str(e)}")

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def delete_issue(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Jira issue key (e.g. PROJ-123)")],
    ) -> str:
        """Delete an existing Jira issue.

        Args:
            ctx: The FastMCP context.
            issue_key: Jira issue key.

        Returns:
            JSON string indicating success.

        Raises:
            ValueError: If in read-only mode or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        deleted = jira.delete_issue(issue_key)
        result = {"message": f"Issue {issue_key} has been deleted successfully."}
        # The underlying method raises on failure, so if we reach here, it's success.
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def add_comment(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="Jira issue key (e.g., 'PROJ-123')")
        ],
        comment: Annotated[str, Field(description="Comment text in Markdown format")],
    ) -> str:
        """Add a comment to a Jira issue.

        Args:
            ctx: The FastMCP context.
            issue_key: Jira issue key.
            comment: Comment text in Markdown.

        Returns:
            JSON string representing the added comment object.

        Raises:
            ValueError: If in read-only mode or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        # add_comment returns dict
        result = jira.add_comment(issue_key, comment)
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def add_worklog(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="Jira issue key (e.g., 'PROJ-123')")
        ],
        time_spent: Annotated[
            str,
            Field(
                description=(
                    "Time spent in Jira format. Examples: "
                    "'1h 30m' (1 hour and 30 minutes), '1d' (1 day), '30m' (30 minutes), '4h' (4 hours)"
                )
            ),
        ],
        comment: Annotated[
            str | None,
            Field(description="(Optional) Comment for the worklog in Markdown format"),
        ] = None,
        started: Annotated[
            str | None,
            Field(
                description=(
                    "(Optional) Start time in ISO format. If not provided, the current time will be used. "
                    "Example: '2023-08-01T12:00:00.000+0000'"
                )
            ),
        ] = None,
        # Add original_estimate and remaining_estimate as per original tool
        original_estimate: Annotated[
            str | None,
            Field(description="(Optional) New value for the original estimate"),
        ] = None,
        remaining_estimate: Annotated[
            str | None,
            Field(description="(Optional) New value for the remaining estimate"),
        ] = None,
    ) -> str:
        """Add a worklog entry to a Jira issue.

        Args:
            ctx: The FastMCP context.
            issue_key: Jira issue key.
            time_spent: Time spent in Jira format.
            comment: Optional comment in Markdown.
            started: Optional start time in ISO format.
            original_estimate: Optional new original estimate.
            remaining_estimate: Optional new remaining estimate.


        Returns:
            JSON string representing the added worklog object.

        Raises:
            ValueError: If in read-only mode or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        # add_worklog returns dict
        worklog_result = jira.add_worklog(
            issue_key=issue_key,
            time_spent=time_spent,
            comment=comment,
            started=started,
            original_estimate=original_estimate,
            remaining_estimate=remaining_estimate,
        )
        result = {"message": "Worklog added successfully", "worklog": worklog_result}
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def link_to_epic(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="The key of the issue to link (e.g., 'PROJ-123')")
        ],
        epic_key: Annotated[
            str, Field(description="The key of the epic to link to (e.g., 'PROJ-456')")
        ],
    ) -> str:
        """Link an existing issue to an epic.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to link.
            epic_key: The key of the epic to link to.

        Returns:
            JSON string representing the updated issue object.

        Raises:
            ValueError: If in read-only mode or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        issue = jira.link_issue_to_epic(issue_key, epic_key)
        result = {
            "message": f"Issue {issue_key} has been linked to epic {epic_key}.",
            "issue": issue.to_simplified_dict(),
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def create_issue_link(
        ctx: Context,
        link_type: Annotated[
            str,
            Field(
                description="The type of link to create (e.g., 'Duplicate', 'Blocks', 'Relates to')"
            ),
        ],
        inward_issue_key: Annotated[
            str, Field(description="The key of the inward issue (e.g., 'PROJ-123')")
        ],
        outward_issue_key: Annotated[
            str, Field(description="The key of the outward issue (e.g., 'PROJ-456')")
        ],
        comment: Annotated[
            str | None, Field(description="(Optional) Comment to add to the link")
        ] = None,
        comment_visibility: Annotated[
            dict[str, str] | None,
            Field(
                description="(Optional) Visibility settings for the comment (e.g., {'type': 'group', 'value': 'jira-users'})",
                default=None,
            ),
        ] = None,
    ) -> str:
        """Create a link between two Jira issues.

        Args:
            ctx: The FastMCP context.
            link_type: The type of link (e.g., 'Blocks').
            inward_issue_key: The key of the source issue.
            outward_issue_key: The key of the target issue.
            comment: Optional comment text.
            comment_visibility: Optional dictionary for comment visibility.

        Returns:
            JSON string indicating success or failure.

        Raises:
            ValueError: If required fields are missing, invalid input, in read-only mode, or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        if not all([link_type, inward_issue_key, outward_issue_key]):
            raise ValueError(
                "link_type, inward_issue_key, and outward_issue_key are required."
            )

        link_data = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_issue_key},
            "outwardIssue": {"key": outward_issue_key},
        }

        if comment:
            comment_obj = {"body": comment}
            if comment_visibility and isinstance(comment_visibility, dict):
                if "type" in comment_visibility and "value" in comment_visibility:
                    comment_obj["visibility"] = comment_visibility
                else:
                    logger.warning("Invalid comment_visibility dictionary structure.")
            link_data["comment"] = comment_obj

        result = jira.create_issue_link(link_data)
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def create_remote_issue_link(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to add the link to (e.g., 'PROJ-123')"
            ),
        ],
        url: Annotated[
            str,
            Field(
                description="The URL to link to (e.g., 'https://example.com/page' or Confluence page URL)"
            ),
        ],
        title: Annotated[
            str,
            Field(
                description="The title/name of the link (e.g., 'Documentation Page', 'Confluence Page')"
            ),
        ],
        summary: Annotated[
            str | None, Field(description="(Optional) Description of the link")
        ] = None,
        relationship: Annotated[
            str | None,
            Field(
                description="(Optional) Relationship description (e.g., 'causes', 'relates to', 'documentation')"
            ),
        ] = None,
        icon_url: Annotated[
            str | None, Field(description="(Optional) URL to a 16x16 icon for the link")
        ] = None,
    ) -> str:
        """Create a remote issue link (web link or Confluence link) for a Jira issue.

        This tool allows you to add web links and Confluence links to Jira issues.
        The links will appear in the issue's "Links" section and can be clicked to navigate to external resources.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to add the link to.
            url: The URL to link to (can be any web page or Confluence page).
            title: The title/name that will be displayed for the link.
            summary: Optional description of what the link is for.
            relationship: Optional relationship description.
            icon_url: Optional URL to a 16x16 icon for the link.

        Returns:
            JSON string indicating success or failure.

        Raises:
            ValueError: If required fields are missing, invalid input, in read-only mode, or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key:
            raise ValueError("issue_key is required.")
        if not url:
            raise ValueError("url is required.")
        if not title:
            raise ValueError("title is required.")

        # Build the remote link data structure
        link_object = {
            "url": url,
            "title": title,
        }

        if summary:
            link_object["summary"] = summary

        if icon_url:
            link_object["icon"] = {"url16x16": icon_url, "title": title}

        link_data = {"object": link_object}

        if relationship:
            link_data["relationship"] = relationship

        result = jira.create_remote_issue_link(issue_key, link_data)
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def remove_issue_link(
        ctx: Context,
        link_id: Annotated[str, Field(description="The ID of the link to remove")],
    ) -> str:
        """Remove a link between two Jira issues.

        Args:
            ctx: The FastMCP context.
            link_id: The ID of the link to remove.

        Returns:
            JSON string indicating success.

        Raises:
            ValueError: If link_id is missing, in read-only mode, or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        if not link_id:
            raise ValueError("link_id is required")

        result = jira.remove_issue_link(link_id)  # Returns dict on success
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def transition_issue(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="Jira issue key (e.g., 'PROJ-123')")
        ],
        transition_id: Annotated[
            str,
            Field(
                description=(
                    "ID of the transition to perform. Use the jira_get_transitions tool first "
                    "to get the available transition IDs for the issue. Example values: '11', '21', '31'"
                )
            ),
        ],
        fields: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "(Optional) Dictionary of fields to update during the transition. "
                    "Some transitions require specific fields to be set (e.g., resolution). "
                    "Example: {'resolution': {'name': 'Fixed'}}"
                ),
                default=None,
            ),
        ] = None,
        comment: Annotated[
            str | None,
            Field(
                description=(
                    "(Optional) Comment to add during the transition. "
                    "This will be visible in the issue history."
                ),
            ),
        ] = None,
    ) -> str:
        """Transition a Jira issue to a new status.

        Args:
            ctx: The FastMCP context.
            issue_key: Jira issue key.
            transition_id: ID of the transition.
            fields: Optional dictionary of fields to update during transition.
            comment: Optional comment for the transition.

        Returns:
            JSON string representing the updated issue object.

        Raises:
            ValueError: If required fields missing, invalid input, in read-only mode, or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not transition_id:
            raise ValueError("issue_key and transition_id are required.")

        # Use fields directly as dict
        update_fields = fields or {}
        if not isinstance(update_fields, dict):
            raise ValueError("fields must be a dictionary.")

        issue = jira.transition_issue(
            issue_key=issue_key,
            transition_id=transition_id,
            fields=update_fields,
            comment=comment,
        )

        result = {
            "message": f"Issue {issue_key} transitioned successfully",
            "issue": issue.to_simplified_dict() if issue else None,
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def create_sprint(
        ctx: Context,
        board_id: Annotated[str, Field(description="The id of board (e.g., '1000')")],
        sprint_name: Annotated[
            str, Field(description="Name of the sprint (e.g., 'Sprint 1')")
        ],
        start_date: Annotated[
            str, Field(description="Start time for sprint (ISO 8601 format)")
        ],
        end_date: Annotated[
            str, Field(description="End time for sprint (ISO 8601 format)")
        ],
        goal: Annotated[
            str | None, Field(description="(Optional) Goal of the sprint")
        ] = None,
    ) -> str:
        """Create Jira sprint for a board.

        Args:
            ctx: The FastMCP context.
            board_id: Board ID.
            sprint_name: Sprint name.
            start_date: Start date (ISO format).
            end_date: End date (ISO format).
            goal: Optional sprint goal.

        Returns:
            JSON string representing the created sprint object.

        Raises:
            ValueError: If in read-only mode or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        sprint = jira.create_sprint(
            board_id=board_id,
            sprint_name=sprint_name,
            start_date=start_date,
            end_date=end_date,
            goal=goal,
        )
        return json.dumps(sprint.to_simplified_dict(), indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def update_sprint(
        ctx: Context,
        sprint_id: Annotated[
            str, Field(description="The id of sprint (e.g., '10001')")
        ],
        sprint_name: Annotated[
            str | None, Field(description="(Optional) New name for the sprint")
        ] = None,
        state: Annotated[
            str | None,
            Field(
                description="(Optional) New state for the sprint (future|active|closed)"
            ),
        ] = None,
        start_date: Annotated[
            str | None, Field(description="(Optional) New start date for the sprint")
        ] = None,
        end_date: Annotated[
            str | None, Field(description="(Optional) New end date for the sprint")
        ] = None,
        goal: Annotated[
            str | None, Field(description="(Optional) New goal for the sprint")
        ] = None,
    ) -> str:
        """Update jira sprint.

        Args:
            ctx: The FastMCP context.
            sprint_id: The ID of the sprint.
            sprint_name: Optional new name.
            state: Optional new state (future|active|closed).
            start_date: Optional new start date.
            end_date: Optional new end date.
            goal: Optional new goal.

        Returns:
            JSON string representing the updated sprint object or an error message.

        Raises:
            ValueError: If in read-only mode or Jira client unavailable.
        """
        jira = await get_jira_fetcher(ctx)
        sprint = jira.update_sprint(
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            state=state,
            start_date=start_date,
            end_date=end_date,
            goal=goal,
        )

        if sprint is None:
            error_payload = {
                "error": f"Failed to update sprint {sprint_id}. Check logs for details."
            }
            return json.dumps(error_payload, indent=2, ensure_ascii=False)
        else:
            return json.dumps(sprint.to_simplified_dict(), indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_project_versions(
        ctx: Context,
        project_key: Annotated[
            str, Field(description="Jira project key (e.g., 'PROJ')")
        ],
    ) -> str:
        """Get all fix versions for a specific Jira project."""
        jira = await get_jira_fetcher(ctx)
        versions = jira.get_project_versions(project_key)
        return json.dumps(versions, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "read"})
    async def get_all_projects(
        ctx: Context,
        include_archived: Annotated[
            bool,
            Field(
                description="Whether to include archived projects in the results",
                default=False,
            ),
        ] = False,
    ) -> str:
        """Get all Jira projects accessible to the current user.

        Args:
            ctx: The FastMCP context.
            include_archived: Whether to include archived projects.

        Returns:
            JSON string representing a list of project objects accessible to the user.
            Project keys are always returned in uppercase.
            If JIRA_PROJECTS_FILTER is configured, only returns projects matching those keys.

        Raises:
            ValueError: If the Jira client is not configured or available.
        """
        try:
            jira = await get_jira_fetcher(ctx)
            projects = jira.get_all_projects(include_archived=include_archived)
        except (MCPAtlassianAuthenticationError, HTTPError, OSError, ValueError) as e:
            error_message = ""
            log_level = logging.ERROR
            if isinstance(e, MCPAtlassianAuthenticationError):
                error_message = f"Authentication/Permission Error: {str(e)}"
            elif isinstance(e, OSError | HTTPError):
                error_message = f"Network or API Error: {str(e)}"
            elif isinstance(e, ValueError):
                error_message = f"Configuration Error: {str(e)}"

            error_result = {
                "success": False,
                "error": error_message,
            }
            logger.log(log_level, f"get_all_projects failed: {error_message}")
            return json.dumps(error_result, indent=2, ensure_ascii=False)

        # Ensure all project keys are uppercase
        for project in projects:
            if "key" in project:
                project["key"] = project["key"].upper()

        # Apply project filter if configured
        if jira.config.projects_filter:
            # Split projects filter by commas and handle possible whitespace
            allowed_project_keys = {
                p.strip().upper() for p in jira.config.projects_filter.split(",")
            }
            projects = [
                project
                for project in projects
                if project.get("key") in allowed_project_keys
            ]

        return json.dumps(projects, indent=2, ensure_ascii=False)

    @jira_mcp.tool(tags={"jira", "write"})
    @check_write_access
    async def create_version(
        ctx: Context,
        project_key: Annotated[
            str, Field(description="Jira project key (e.g., 'PROJ')")
        ],
        name: Annotated[str, Field(description="Name of the version")],
        start_date: Annotated[
            str | None, Field(description="Start date (YYYY-MM-DD)", default=None)
        ] = None,
        release_date: Annotated[
            str | None, Field(description="Release date (YYYY-MM-DD)", default=None)
        ] = None,
        description: Annotated[
            str | None, Field(description="Description of the version", default=None)
        ] = None,
    ) -> str:
        """Create a new fix version in a Jira project.

        Args:
            ctx: The FastMCP context.
            project_key: The project key.
            name: Name of the version.
            start_date: Start date (optional).
            release_date: Release date (optional).
            description: Description (optional).

        Returns:
            JSON string of the created version object.
        """
        jira = await get_jira_fetcher(ctx)
        try:
            version = jira.create_project_version(
                project_key=project_key,
                name=name,
                start_date=start_date,
                release_date=release_date,
                description=description,
            )
            return json.dumps(version, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(
                f"Error creating version in project {project_key}: {str(e)}",
                exc_info=True,
            )
            return json.dumps(
                {"success": False, "error": str(e)}, indent=2, ensure_ascii=False
            )

    @jira_mcp.tool(name="batch_create_versions", tags={"jira", "write"})
    @check_write_access
    async def batch_create_versions(
        ctx: Context,
        project_key: Annotated[
            str, Field(description="Jira project key (e.g., 'PROJ')")
        ],
        versions: Annotated[
            str,
            Field(
                description=(
                    "JSON array of version objects. Each object should contain:\n"
                    "- name (required): Name of the version\n"
                    "- startDate (optional): Start date (YYYY-MM-DD)\n"
                    "- releaseDate (optional): Release date (YYYY-MM-DD)\n"
                    "- description (optional): Description of the version\n"
                    "Example: [\n"
                    '  {"name": "v1.0", "startDate": "2025-01-01", "releaseDate": "2025-02-01", "description": "First release"},\n'
                    '  {"name": "v2.0"}\n'
                    "]"
                )
            ),
        ],
    ) -> str:
        """Batch create multiple versions in a Jira project.

        Args:
            ctx: The FastMCP context.
            project_key: The project key.
            versions: JSON array string of version objects.

        Returns:
            JSON array of results, each with success flag, version or error.
        """
        jira = await get_jira_fetcher(ctx)
        try:
            version_list = json.loads(versions)
            if not isinstance(version_list, list):
                raise ValueError("Input 'versions' must be a JSON array string.")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in versions")
        except Exception as e:
            raise ValueError(f"Invalid input for versions: {e}") from e

        results = []
        if not version_list:
            return json.dumps(results, indent=2, ensure_ascii=False)

        for idx, v in enumerate(version_list):
            # Defensive: ensure v is a dict and has a name
            if not isinstance(v, dict) or not v.get("name"):
                results.append(
                    {
                        "success": False,
                        "error": f"Item {idx}: Each version must be an object with at least a 'name' field.",
                    }
                )
                continue
            try:
                version = jira.create_project_version(
                    project_key=project_key,
                    name=v["name"],
                    start_date=v.get("startDate"),
                    release_date=v.get("releaseDate"),
                    description=v.get("description"),
                )
                results.append({"success": True, "version": version})
            except Exception as e:
                logger.error(
                    f"Error creating version in batch for project {project_key}: {str(e)}",
                    exc_info=True,
                )
                results.append({"success": False, "error": str(e), "input": v})
        return json.dumps(results, indent=2, ensure_ascii=False)


jira_mcp = FastMCP(
    name="Jira MCP Service",
    description="Provides tools for interacting with Atlassian Jira.",
)
<<<<<<< HEAD


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="user", service_name="Jira")
async def get_user_profile(
    ctx: Context,
    user_identifier: Annotated[
        str,
        Field(
            description="Identifier for the user (e.g., email address 'user@example.com', username 'johndoe', account ID 'accountid:...', or key for Server/DC)."
        ),
    ],
) -> str:
    """
    Retrieve profile information for a specific Jira user.

    Args:
        ctx: The FastMCP context.
        user_identifier: User identifier (email, username, key, or account ID).

    Returns:
        JSON string representing the Jira user profile object, or an error object if not found.

    Raises:
        ValueError: If the Jira client is not configured or available.
    """
    jira = await get_jira_fetcher(ctx)
    try:
        user: JiraUser = jira.get_user_profile_by_identifier(user_identifier)
        result = user.to_simplified_dict()
        response_data = {"success": True, "user": result}
    except Exception as e:
        error_message = ""
        log_level = logging.ERROR
        if isinstance(e, ValueError) and "not found" in str(e).lower():
            log_level = logging.WARNING
            error_message = str(e)
        elif isinstance(e, MCPAtlassianAuthenticationError):
            error_message = f"Authentication/Permission Error: {str(e)}"
        elif isinstance(e, OSError | HTTPError):
            error_message = f"Network or API Error: {str(e)}"
        else:
            error_message = (
                "An unexpected error occurred while fetching the user profile."
            )
            logger.exception(
                f"Unexpected error in get_user_profile for '{user_identifier}':"
            )
        error_result = {
            "success": False,
            "error": str(e),
            "user_identifier": user_identifier,
        }
        logger.log(
            log_level,
            f"get_user_profile failed for '{user_identifier}': {error_message}",
        )
        response_data = error_result
    return json.dumps(response_data, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="issue", service_name="Jira")
async def get_issue(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    fields: Annotated[
        str,
        Field(
            description=(
                "(Optional) Comma-separated list of fields to return (e.g., 'summary,status,customfield_10010'). "
                "You may also provide a single field as a string (e.g., 'duedate'). "
                "Use '*all' for all fields (including custom fields), or omit for essential fields only."
            ),
            default=",".join(DEFAULT_READ_JIRA_FIELDS),
        ),
    ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
    expand: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Fields to expand. Examples: 'renderedFields' (for rendered content), "
                "'transitions' (for available status transitions), 'changelog' (for history)"
            ),
            default=None,
        ),
    ] = None,
    comment_limit: Annotated[
        int,
        Field(
            description="Maximum number of comments to include (0 or null for no comments)",
            default=10,
            ge=0,
            le=100,
        ),
    ] = 10,
    properties: Annotated[
        str | None,
        Field(
            description="(Optional) A comma-separated list of issue properties to return",
            default=None,
        ),
    ] = None,
    update_history: Annotated[
        bool,
        Field(
            description="Whether to update the issue view history for the requesting user",
            default=True,
        ),
    ] = True,
) -> str:
    """Get details of a specific Jira issue including its Epic links and relationship information.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        fields: Comma-separated list of fields to return (e.g., 'summary,status,customfield_10010'), a single field as a string (e.g., 'duedate'), '*all' for all fields, or omitted for essentials.
        expand: Optional fields to expand.
        comment_limit: Maximum number of comments.
        properties: Issue properties to return.
        update_history: Whether to update issue view history.

    Returns:
        JSON string representing the Jira issue object.

    Raises:
        ValueError: If the Jira client is not configured or available.
    """
    jira = await get_jira_fetcher(ctx)
    fields_list: str | list[str] | None = fields
    if fields and fields != "*all":
        fields_list = [f.strip() for f in fields.split(",")]

    issue = jira.get_issue(
        issue_key=issue_key,
        fields=fields_list,
        expand=expand,
        comment_limit=comment_limit,
        properties=properties.split(",") if properties else None,
        update_history=update_history,
    )
    # Get development status and include it in the result
    result = issue.to_simplified_dict()

    # Add development status information automatically
    try:
        dev_status = await _get_development_status_helper(ctx, issue_key, issue.id)
        if dev_status:
            result["development_status"] = dev_status
    except Exception as e:
        logger.warning(
            f"Could not retrieve development status for {issue_key}: {str(e)}"
        )

    return json.dumps(result, indent=2, ensure_ascii=False)


async def _get_development_status_helper(
    ctx: Context,
    issue_key: str,
    issue_id: str,
    application_type: str = "GitHub",
    data_type: str = "branch",
) -> dict | None:
    """
    Helper function to get development status information for an issue.

    Args:
        ctx: The FastMCP context
        issue_key: The issue key
        issue_id: The issue ID
        application_type: Source control application type
        data_type: Type of development data to retrieve

    Returns:
        Dictionary containing development status information, or None if not available
    """
    jira = await get_jira_fetcher(ctx)

    try:
        logger.debug(f"🔍 Getting development status for {issue_key} (ID: {issue_id})")

        # Use the internal dev-status API endpoint
        url = f"{jira.config.url}/rest/dev-status/latest/issue/detail"
        params = {
            "issueId": issue_id,
            "applicationType": application_type,
            "dataType": data_type,
        }

        logger.debug(f"🌐 Making dev-status API call to: {url}")

        # Make the API call using the same authentication as other calls
        response = jira.jira._session.get(url, params=params)

        logger.debug(f"📡 Dev-status API response: {response.status_code}")

        if response.status_code == 200:
            dev_data = response.json()

            # Extract and format the development information
            result: dict[str, Any] = {
                "application_type": application_type,
                "data_type": data_type,
                "branches": [],
                "repositories": [],
                "pull_requests": [],
                "commits": [],
            }

            # Process the detailed development information
            if "detail" in dev_data:
                for detail in dev_data["detail"]:
                    # Process branches
                    if "branches" in detail:
                        for branch in detail["branches"]:
                            branch_info = {
                                "name": branch.get("name"),
                                "url": branch.get("url"),
                                "repository": branch.get("repository", {}).get("name"),
                                "repository_url": branch.get("repository", {}).get(
                                    "url"
                                ),
                                "last_commit": branch.get("lastCommit", {}).get(
                                    "message"
                                ),
                                "last_commit_id": branch.get("lastCommit", {}).get(
                                    "id"
                                ),
                            }
                            result["branches"].append(branch_info)

                    # Process repositories
                    if "repositories" in detail:
                        for repo in detail["repositories"]:
                            repo_info = {
                                "name": repo.get("name"),
                                "url": repo.get("url"),
                                "avatar": repo.get("avatar"),
                                "commits": repo.get("commits", 0),
                            }
                            result["repositories"].append(repo_info)

                    # Process pull requests
                    if "pullRequests" in detail:
                        for pr in detail["pullRequests"]:
                            pr_info = {
                                "id": pr.get("id"),
                                "name": pr.get("name"),
                                "url": pr.get("url"),
                                "status": pr.get("status"),
                                "source_branch": pr.get("source", {}).get("branch"),
                                "destination_branch": pr.get("destination", {}).get(
                                    "branch"
                                ),
                                "repository": pr.get("source", {})
                                .get("repository", {})
                                .get("name"),
                            }
                            result["pull_requests"].append(pr_info)

                    # Process commits
                    if "commits" in detail:
                        for commit in detail["commits"]:
                            commit_info = {
                                "id": commit.get("id"),
                                "displayId": commit.get("displayId"),
                                "message": commit.get("message"),
                                "author": commit.get("author", {}).get("name"),
                                "authorTimestamp": commit.get("authorTimestamp"),
                                "url": commit.get("url"),
                                "repository": commit.get("repository", {}).get("name"),
                            }
                            result["commits"].append(commit_info)

            # Add summary information
            result["summary"] = {
                "total_branches": len(result["branches"]),
                "total_repositories": len(result["repositories"]),
                "total_pull_requests": len(result["pull_requests"]),
                "total_commits": len(result["commits"]),
            }

            # Only return the result if we found any development data
            if any(
                [
                    result["branches"],
                    result["repositories"],
                    result["pull_requests"],
                    result["commits"],
                ]
            ):
                logger.debug(
                    f"✅ Found dev status for {issue_key}: {result['summary']}"
                )
                return result
            else:
                logger.debug(f"📭 No development data found for {issue_key}")
                return None

        else:
            logger.debug(
                f"❌ Dev status API returned {response.status_code} for {issue_key}"
            )
            return None

    except Exception as e:
        logger.debug(f"💥 Error getting development status for {issue_key}: {str(e)}")
        return None


@jira_mcp.tool(tags={"jira", "read"})
async def get_development_status(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'SMS-8')")],
    application_type: Annotated[
        str,
        Field(
            description="Source control application type (e.g., 'GitHub', 'Bitbucket', 'GitLab')",
            default="GitHub",
        ),
    ] = "GitHub",
    data_type: Annotated[
        str,
        Field(
            description="Type of development data to retrieve ('branch', 'pullrequest', 'commit')",
            default="branch",
        ),
    ] = "branch",
) -> str:
    """Get development status information for a Jira issue including branch names, commits, and pull requests.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        application_type: Source control application type.
        data_type: Type of development data to retrieve.

    Returns:
        JSON string representing the development status information.

    Raises:
        ValueError: If the Jira client is not configured or available.
    """
    jira = await get_jira_fetcher(ctx)

    try:
        # First get the issue to get the issue ID
        issue = jira.get_issue(issue_key=issue_key, fields=["id"])
        issue_id = issue.id

        logger.info(f"🔍 Getting development status for {issue_key} (ID: {issue_id})")

        # Use the internal dev-status API endpoint
        url = f"{jira.config.url}/rest/dev-status/latest/issue/detail"
        params = {
            "issueId": issue_id,
            "applicationType": application_type,
            "dataType": data_type,
        }

        logger.info(f"🌐 Making dev-status API call to: {url}")
        logger.info(f"📋 Params: {params}")

        # Make the API call using the same authentication as other calls
        response = jira.jira._session.get(url, params=params)

        logger.info(f"📡 Dev-status API response: {response.status_code}")

        if response.status_code == 200:
            dev_data = response.json()
            logger.info(
                f"📄 Dev-status response data keys: {list(dev_data.keys()) if dev_data else 'None'}"
            )

            # Extract and format the development information
            result: dict[str, Any] = {
                "success": True,
                "issue_key": issue_key,
                "issue_id": issue_id,
                "application_type": application_type,
                "data_type": data_type,
                "branches": [],
                "repositories": [],
                "pull_requests": [],
                "commits": [],
            }

            # Process the detailed development information
            if "detail" in dev_data:
                logger.info(f"📈 Processing {len(dev_data['detail'])} detail items")
                for detail in dev_data["detail"]:
                    # Process branches
                    if "branches" in detail:
                        logger.info(f"🌿 Found {len(detail['branches'])} branches")
                        for branch in detail["branches"]:
                            branch_info = {
                                "name": branch.get("name"),
                                "url": branch.get("url"),
                                "repository": branch.get("repository", {}).get("name"),
                                "repository_url": branch.get("repository", {}).get(
                                    "url"
                                ),
                                "last_commit": branch.get("lastCommit", {}).get(
                                    "message"
                                ),
                                "last_commit_id": branch.get("lastCommit", {}).get(
                                    "id"
                                ),
                            }
                            result["branches"].append(branch_info)
                            logger.info(f"✅ Added branch: {branch_info['name']}")

                    # Process repositories
                    if "repositories" in detail:
                        for repo in detail["repositories"]:
                            repo_info = {
                                "name": repo.get("name"),
                                "url": repo.get("url"),
                                "avatar": repo.get("avatar"),
                                "commits": repo.get("commits", 0),
                            }
                            result["repositories"].append(repo_info)

                    # Process pull requests
                    if "pullRequests" in detail:
                        for pr in detail["pullRequests"]:
                            pr_info = {
                                "id": pr.get("id"),
                                "name": pr.get("name"),
                                "url": pr.get("url"),
                                "status": pr.get("status"),
                                "source_branch": pr.get("source", {}).get("branch"),
                                "destination_branch": pr.get("destination", {}).get(
                                    "branch"
                                ),
                                "repository": pr.get("source", {})
                                .get("repository", {})
                                .get("name"),
                            }
                            result["pull_requests"].append(pr_info)

                    # Process commits
                    if "commits" in detail:
                        for commit in detail["commits"]:
                            commit_info = {
                                "id": commit.get("id"),
                                "displayId": commit.get("displayId"),
                                "message": commit.get("message"),
                                "author": commit.get("author", {}).get("name"),
                                "authorTimestamp": commit.get("authorTimestamp"),
                                "url": commit.get("url"),
                                "repository": commit.get("repository", {}).get("name"),
                            }
                            result["commits"].append(commit_info)

            # Add summary information
            result["summary"] = {
                "total_branches": len(result["branches"]),
                "total_repositories": len(result["repositories"]),
                "total_pull_requests": len(result["pull_requests"]),
                "total_commits": len(result["commits"]),
            }

            logger.info(
                f"🎉 Successfully extracted dev status for {issue_key}: {len(result['branches'])} branches, {len(result['repositories'])} repos"
            )
            return json.dumps(result, indent=2, ensure_ascii=False)

        else:
            error_result = {
                "success": False,
                "issue_key": issue_key,
                "issue_id": issue_id,
                "error": f"API returned status {response.status_code}",
                "response_text": response.text[:500] if response.text else None,
            }
            logger.warning(
                f"❌ Dev status API returned {response.status_code} for {issue_key}: {response.text[:200]}"
            )
            return json.dumps(error_result, indent=2, ensure_ascii=False)

    except Exception as e:
        error_result = {
            "success": False,
            "issue_key": issue_key,
            "error": str(e),
            "error_type": type(e).__name__,
        }
        logger.error(f"💥 Error getting development status for {issue_key}: {str(e)}")
        import traceback

        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        return json.dumps(error_result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="issues", service_name="Jira")
async def search(
    ctx: Context,
    jql: Annotated[
        str,
        Field(
            description=(
                "JQL query string (Jira Query Language). Examples:\n"
                '- Find Epics: "issuetype = Epic AND project = PROJ"\n'
                '- Find issues in Epic: "parent = PROJ-123"\n'
                "- Find by status: \"status = 'In Progress' AND project = PROJ\"\n"
                '- Find by assignee: "assignee = currentUser()"\n'
                '- Find recently updated: "updated >= -7d AND project = PROJ"\n'
                '- Find by label: "labels = frontend AND project = PROJ"\n'
                '- Find by priority: "priority = High AND project = PROJ"'
            )
        ),
    ],
    fields: Annotated[
        str,
        Field(
            description=(
                "(Optional) Comma-separated fields to return in the results. "
                "Use '*all' for all fields, or specify individual fields like 'summary,status,assignee,priority'"
            ),
            default=",".join(DEFAULT_READ_JIRA_FIELDS),
        ),
    ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1),
    ] = 10,
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    projects_filter: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Comma-separated list of project keys to filter results by. "
                "Overrides the environment variable JIRA_PROJECTS_FILTER if provided."
            ),
            default=None,
        ),
    ] = None,
    expand: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) fields to expand. Examples: 'renderedFields', 'transitions', 'changelog'"
            ),
            default=None,
        ),
    ] = None,
) -> str:
    """Search Jira issues using JQL (Jira Query Language).

    Args:
        ctx: The FastMCP context.
        jql: JQL query string.
        fields: Comma-separated fields to return.
        limit: Maximum number of results.
        start_at: Starting index for pagination.
        projects_filter: Comma-separated list of project keys to filter by.
        expand: Optional fields to expand.

    Returns:
        JSON string representing the search results including pagination info.
    """
    jira = await get_jira_fetcher(ctx)
    fields_list: str | list[str] | None = fields
    if fields and fields != "*all":
        fields_list = [f.strip() for f in fields.split(",")]

    search_result = jira.search_issues(
        jql=jql,
        fields=fields_list,
        limit=limit,
        start=start_at,
        expand=expand,
        projects_filter=projects_filter,
    )
    result = search_result.to_simplified_dict()
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="fields", service_name="Jira")
async def search_fields(
    ctx: Context,
    keyword: Annotated[
        str,
        Field(
            description="Keyword for fuzzy search. If left empty, lists the first 'limit' available fields in their default order.",
            default="",
        ),
    ] = "",
    limit: Annotated[
        int, Field(description="Maximum number of results", default=10, ge=1)
    ] = 10,
    refresh: Annotated[
        bool,
        Field(description="Whether to force refresh the field list", default=False),
    ] = False,
) -> str:
    """Search Jira fields by keyword with fuzzy match.

    Args:
        ctx: The FastMCP context.
        keyword: Keyword for fuzzy search.
        limit: Maximum number of results.
        refresh: Whether to force refresh the field list.

    Returns:
        JSON string representing a list of matching field definitions.
    """
    jira = await get_jira_fetcher(ctx)
    result = jira.search_fields(keyword, limit=limit, refresh=refresh)
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="issues", service_name="Jira")
async def get_project_issues(
    ctx: Context,
    project_key: Annotated[str, Field(description="The project key")],
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
) -> str:
    """Get all issues for a specific Jira project.

    Args:
        ctx: The FastMCP context.
        project_key: The project key.
        limit: Maximum number of results.
        start_at: Starting index for pagination.

    Returns:
        JSON string representing the search results including pagination info.
    """
    jira = await get_jira_fetcher(ctx)
    search_result = jira.get_project_issues(
        project_key=project_key, start=start_at, limit=limit
    )
    result = search_result.to_simplified_dict()
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="transitions", service_name="Jira")
async def get_transitions(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
) -> str:
    """Get available status transitions for a Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.

    Returns:
        JSON string representing a list of available transitions.
    """
    jira = await get_jira_fetcher(ctx)
    # Underlying method returns list[dict] in the desired format
    transitions = jira.get_available_transitions(issue_key)
    return json.dumps(transitions, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
<<<<<<< HEAD
@handle_tool_errors(default_return_key="worklogs", service_name="Jira")
=======
async def get_comments(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    limit: Annotated[
        int,
        Field(
            description="Maximum number of comments to retrieve",
            default=50,
            ge=1,
            le=1000,
        ),
    ] = 50,
) -> str:
    """Get comments for a specific Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        limit: Maximum number of comments to retrieve (1-1000, default 50).

    Returns:
        JSON string representing the comments with author, creation date, and content.
    """
    jira = await get_jira_fetcher(ctx)
    comments = jira.get_issue_comments(issue_key=issue_key, limit=limit)
    result = {
        "issue_key": issue_key,
        "total_comments": len(comments),
        "comments": comments,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
>>>>>>> suparious/main
async def get_worklog(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
) -> str:
    """Get worklog entries for a Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.

    Returns:
        JSON string representing the worklog entries.
    """
    jira = await get_jira_fetcher(ctx)
    worklogs = jira.get_worklogs(issue_key)
    result = {"worklogs": worklogs}
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="result", service_name="Jira")
async def download_attachments(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    target_dir: Annotated[
        str, Field(description="Directory where attachments should be saved")
    ],
) -> str:
    """Download attachments from a Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        target_dir: Directory to save attachments.

    Returns:
        JSON string indicating the result of the download operation.
    """
    jira = await get_jira_fetcher(ctx)
    result = jira.download_issue_attachments(issue_key=issue_key, target_dir=target_dir)
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="boards", service_name="Jira")
async def get_agile_boards(
    ctx: Context,
    board_name: Annotated[
        str | None,
        Field(description="(Optional) The name of board, support fuzzy search"),
    ] = None,
    project_key: Annotated[
        str | None, Field(description="(Optional) Jira project key (e.g., 'PROJ-123')")
    ] = None,
    board_type: Annotated[
        str | None,
        Field(
            description="(Optional) The type of jira board (e.g., 'scrum', 'kanban')"
        ),
    ] = None,
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
) -> str:
    """Get jira agile boards by name, project key, or type.

    Args:
        ctx: The FastMCP context.
        board_name: Name of the board (fuzzy search).
        project_key: Project key.
        board_type: Board type ('scrum' or 'kanban').
        start_at: Starting index.
        limit: Maximum results.

    Returns:
        JSON string representing a list of board objects.
    """
    jira = await get_jira_fetcher(ctx)
    boards = jira.get_all_agile_boards_model(
        board_name=board_name,
        project_key=project_key,
        board_type=board_type,
        start=start_at,
        limit=limit,
    )
    result = [board.to_simplified_dict() for board in boards]
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="issues", service_name="Jira")
async def get_board_issues(
    ctx: Context,
    board_id: Annotated[str, Field(description="The id of the board (e.g., '1001')")],
    jql: Annotated[
        str,
        Field(
            description=(
                "JQL query string (Jira Query Language). Examples:\n"
                '- Find Epics: "issuetype = Epic AND project = PROJ"\n'
                '- Find issues in Epic: "parent = PROJ-123"\n'
                "- Find by status: \"status = 'In Progress' AND project = PROJ\"\n"
                '- Find by assignee: "assignee = currentUser()"\n'
                '- Find recently updated: "updated >= -7d AND project = PROJ"\n'
                '- Find by label: "labels = frontend AND project = PROJ"\n'
                '- Find by priority: "priority = High AND project = PROJ"'
            )
        ),
    ],
    fields: Annotated[
        str,
        Field(
            description=(
                "Comma-separated fields to return in the results. "
                "Use '*all' for all fields, or specify individual "
                "fields like 'summary,status,assignee,priority'"
            ),
            default=",".join(DEFAULT_READ_JIRA_FIELDS),
        ),
    ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
    expand: Annotated[
        str,
        Field(
            description="Optional fields to expand in the response (e.g., 'changelog').",
            default="version",
        ),
    ] = "version",
) -> str:
    """Get all issues linked to a specific board filtered by JQL.

    Args:
        ctx: The FastMCP context.
        board_id: The ID of the board.
        jql: JQL query string to filter issues.
        fields: Comma-separated fields to return.
        start_at: Starting index for pagination.
        limit: Maximum number of results.
        expand: Optional fields to expand.

    Returns:
        JSON string representing the search results including pagination info.
    """
    jira = await get_jira_fetcher(ctx)
    fields_list: str | list[str] | None = fields
    if fields and fields != "*all":
        fields_list = [f.strip() for f in fields.split(",")]

    search_result = jira.get_board_issues(
        board_id=board_id,
        jql=jql,
        fields=fields_list,
        start=start_at,
        limit=limit,
        expand=expand,
    )
    result = search_result.to_simplified_dict()
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="sprints", service_name="Jira")
async def get_sprints_from_board(
    ctx: Context,
    board_id: Annotated[str, Field(description="The id of board (e.g., '1000')")],
    state: Annotated[
        str | None,
        Field(description="Sprint state (e.g., 'active', 'future', 'closed')"),
    ] = None,
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
) -> str:
    """Get jira sprints from board by state.

    Args:
        ctx: The FastMCP context.
        board_id: The ID of the board.
        state: Sprint state ('active', 'future', 'closed'). If None, returns all sprints.
        start_at: Starting index.
        limit: Maximum results.

    Returns:
        JSON string representing a list of sprint objects.
    """
    jira = await get_jira_fetcher(ctx)
    sprints = jira.get_all_sprints_from_board_model(
        board_id=board_id, state=state, start=start_at, limit=limit
    )
    result = [sprint.to_simplified_dict() for sprint in sprints]
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="sprint_issues", service_name="Jira")
async def get_sprint_issues(
    ctx: Context,
    sprint_id: Annotated[str, Field(description="The id of sprint (e.g., '10001')")],
    fields: Annotated[
        str,
        Field(
            description=(
                "Comma-separated fields to return in the results. "
                "Use '*all' for all fields, or specify individual "
                "fields like 'summary,status,assignee,priority'"
            ),
            default=",".join(DEFAULT_READ_JIRA_FIELDS),
        ),
    ] = ",".join(DEFAULT_READ_JIRA_FIELDS),
    start_at: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
    ] = 10,
) -> str:
    """Get jira issues from sprint.

    Args:
        ctx: The FastMCP context.
        sprint_id: The ID of the sprint.
        fields: Comma-separated fields to return.
        start_at: Starting index.
        limit: Maximum results.

    Returns:
        JSON string representing the search results including pagination info.
    """
    jira = await get_jira_fetcher(ctx)
    fields_list: str | list[str] | None = fields
    if fields and fields != "*all":
        fields_list = [f.strip() for f in fields.split(",")]

    search_result = jira.get_sprint_issues(
        sprint_id=sprint_id, fields=fields_list, start=start_at, limit=limit
    )
    result = search_result.to_simplified_dict()
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="link_types", service_name="Jira")
async def get_link_types(ctx: Context) -> str:
    """Get all available issue link types.

    Args:
        ctx: The FastMCP context.

    Returns:
        JSON string representing a list of issue link type objects.
    """
    jira = await get_jira_fetcher(ctx)
    link_types = jira.get_issue_link_types()
    formatted_link_types = [link_type.to_simplified_dict() for link_type in link_types]
    return json.dumps(formatted_link_types, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="issue", service_name="Jira")
async def create_issue(
    ctx: Context,
    project_key: Annotated[
        str,
        Field(
            description=(
                "The JIRA project key (e.g. 'PROJ', 'DEV', 'SUPPORT'). "
                "This is the prefix of issue keys in your project. "
                "Never assume what it might be, always ask the user."
            )
        ),
    ],
    summary: Annotated[str, Field(description="Summary/title of the issue")],
    issue_type: Annotated[
        str,
        Field(
            description=(
                "Issue type (e.g. 'Task', 'Bug', 'Story', 'Epic', 'Subtask'). "
                "The available types depend on your project configuration. "
                "For subtasks, use 'Subtask' (not 'Sub-task') and include parent in additional_fields."
            ),
        ),
    ],
    assignee: Annotated[
        str | None,
        Field(
            description="(Optional) Assignee's user identifier (string): Email, display name, or account ID (e.g., 'user@example.com', 'John Doe', 'accountid:...')",
            default=None,
        ),
    ] = None,
    description: Annotated[
        str | None, Field(description="Issue description", default=None)
    ] = None,
    components: Annotated[
        str | None,
        Field(
            description="(Optional) Comma-separated list of component names to assign (e.g., 'Frontend,API')",
            default=None,
        ),
    ] = None,
    additional_fields: Annotated[
        dict[str, Any] | str | None,
        Field(
            description=(
                "(Optional) Dictionary of additional fields to set. Examples:\n"
                "- Set priority: {'priority': {'name': 'High'}}\n"
                "- Add labels: {'labels': ['frontend', 'urgent']}\n"
                "- Link to parent (for any issue type): {'parent': 'PROJ-123'}\n"
                "- Set Fix Version/s: {'fixVersions': [{'id': '10020'}]}\n"
                "- Custom fields: {'customfield_10010': 'value'}"
            ),
            default=None,
        ),
    ] = None,
) -> str:
    """Create a new Jira issue with optional Epic link or parent for subtasks.

    Args:
        ctx: The FastMCP context.
        project_key: The JIRA project key.
        summary: Summary/title of the issue.
        issue_type: Issue type (e.g., 'Task', 'Bug', 'Story', 'Epic', 'Subtask').
        assignee: Assignee's user identifier (string): Email, display name, or account ID (e.g., 'user@example.com', 'John Doe', 'accountid:...').
        description: Issue description.
        components: Comma-separated list of component names.
        additional_fields: Dictionary or JSON string of additional fields.

    Returns:
        JSON string representing the created issue object.

    Raises:
        ValueError: If in read-only mode or Jira client is unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    # Parse components from comma-separated string to list
    components_list = None
    if components and isinstance(components, str):
        components_list = [
            comp.strip() for comp in components.split(",") if comp.strip()
        ]

<<<<<<< HEAD
    # Use additional_fields directly as dict
    # Accept either dict or JSON string for additional fields
    if additional_fields is None:
        extra_fields: dict[str, Any] = {}
    elif isinstance(additional_fields, dict):
        extra_fields = additional_fields
    elif isinstance(additional_fields, str):
        try:
            extra_fields = json.loads(additional_fields)
            if not isinstance(extra_fields, dict):
                raise ValueError(
                    "Parsed additional_fields is not a JSON object (dict)."
                )
        except json.JSONDecodeError as e:
            raise ValueError(f"additional_fields is not valid JSON: {e}") from e
    else:
        raise ValueError("additional_fields must be a dictionary or JSON string.")

    try:
=======
    try:
        # Ensure description is a string, not None
        description_str = description if description is not None else ""
>>>>>>> anders/fix-throw-error
        issue = jira.create_issue(
            project_key=project_key,
            summary=summary,
            issue_type=issue_type,
<<<<<<< HEAD
            description=description,
            assignee=assignee,
            components=components_list,
            **extra_fields,
=======
            description=description_str,
            assignee=assignee,
            components=components_list,
            **(additional_fields or {}),
>>>>>>> anders/fix-throw-error
        )
        result = issue.to_simplified_dict()
        return json.dumps(
            {"message": "Issue created successfully", "issue": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
<<<<<<< HEAD
        # Enhanced error handling with detailed information
        error_msg = f"Failed to create JIRA issue: {str(e)}"

        # Extract JIRA API error details if available
        if hasattr(e, "response") and hasattr(e.response, "text"):
            try:
                jira_error = json.loads(e.response.text)
                error_msg += (
                    f"\n\nJIRA API Response:\n{json.dumps(jira_error, indent=2)}"
                )
            except Exception:
                error_msg += f"\n\nJIRA API Response (raw):\n{e.response.text}"

        # Try creating with individual fields if batch creation failed
        if extra_fields:
            logger.warning(
                f"Batch create failed, attempting individual field fallback for project {project_key}"
            )

            # First create with core fields only
            try:
                core_issue = jira.create_issue(
                    project_key=project_key,
                    summary=summary,
                    issue_type=issue_type,
                    description=description,
                    assignee=assignee,
                    components=components_list,
                )

                # Then attempt to update with additional fields using our enhanced update function
                success_fields = []
                failed_fields = []

                for field_name, field_value in extra_fields.items():
                    try:
                        jira.update_issue(core_issue.key, **{field_name: field_value})
                        success_fields.append(field_name)
                    except Exception as field_error:
                        failed_fields.append(
                            {
                                "field": field_name,
                                "value": field_value,
                                "error": str(field_error),
                                "suggestion": analyze_field_format(
                                    field_name, field_value
                                ),
                            }
                        )

                # Return partial success with details
                result = core_issue.to_simplified_dict()
                response_data = {
                    "message": "Issue created with partial field updates",
                    "issue": result,
                    "field_update_results": {
                        "successful_fields": success_fields,
                        "failed_fields": failed_fields,
                    },
                }

                if failed_fields:
                    response_data["troubleshooting"] = (
                        "Some additional fields failed to update. Check field names, types, and permissions."
                    )

                return json.dumps(response_data, indent=2, ensure_ascii=False)

            except Exception as fallback_error:
                error_msg += f"\n\nFallback creation also failed: {str(fallback_error)}"

        # Add field format analysis for debugging
        if extra_fields:
            error_msg += "\n\nField Analysis:"
            for field_name, field_value in extra_fields.items():
                suggestion = analyze_field_format(field_name, field_value)
                error_msg += f"\n- {field_name}: {suggestion}"

        logger.error(f"JIRA create_issue failed: {error_msg}")

        # Return structured error response instead of raising exception
        # This ensures detailed error information reaches the MCP client
        error_response = {
            "success": False,
            "error": "Issue creation failed",
            "details": error_msg,
            "troubleshooting_guide": "Check field names, required fields, and permissions in your JIRA project",
        }

        # Parse JIRA API errors if available
        if hasattr(e, "response") and hasattr(e.response, "text"):
            try:
                jira_error_details = json.loads(e.response.text)
                error_response["jira_api_response"] = jira_error_details
            except Exception:
                error_response["jira_api_response_raw"] = e.response.text

        # Add field analysis for debugging
        if extra_fields:
            error_response["field_analysis"] = {}
            for field_name, field_value in extra_fields.items():
                error_response["field_analysis"][field_name] = analyze_field_format(
                    field_name, field_value
                )

        return json.dumps(error_response, indent=2, ensure_ascii=False)
=======
        logger.error(
            f"Error creating issue in project {project_key}: {str(e)}", exc_info=True
        )
        # Surface the error directly to the agent in a structured way
        return json.dumps({"error": str(e)})
>>>>>>> anders/fix-throw-error


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="issues", service_name="Jira")
async def batch_create_issues(
    ctx: Context,
    issues: Annotated[
        str,
        Field(
            description=(
                "JSON array of issue objects. Each object should contain:\n"
                "- project_key (required): The project key (e.g., 'PROJ')\n"
                "- summary (required): Issue summary/title\n"
                "- issue_type (required): Type of issue (e.g., 'Task', 'Bug')\n"
                "- description (optional): Issue description\n"
                "- assignee (optional): Assignee username or email\n"
                "- components (optional): Array of component names\n"
                "Example: [\n"
                '  {"project_key": "PROJ", "summary": "Issue 1", "issue_type": "Task"},\n'
                '  {"project_key": "PROJ", "summary": "Issue 2", "issue_type": "Bug", "components": ["Frontend"]}\n'
                "]"
            )
        ),
    ],
    validate_only: Annotated[
        bool,
        Field(
            description="If true, only validates the issues without creating them",
            default=False,
        ),
    ] = False,
) -> str:
    """Create multiple Jira issues in a batch.

    Args:
        ctx: The FastMCP context.
        issues: JSON array string of issue objects.
        validate_only: If true, only validates without creating.

    Returns:
        JSON string indicating success and listing created issues (or validation result).

    Raises:
        ValueError: If in read-only mode, Jira client unavailable, or invalid JSON.
    """
    jira = await get_jira_fetcher(ctx)
    # Parse issues from JSON string
    try:
        issues_list = json.loads(issues)
        if not isinstance(issues_list, list):
            raise ValueError("Input 'issues' must be a JSON array string.")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in issues")
    except Exception as e:
        raise ValueError(f"Invalid input for issues: {e}") from e

    # Create issues in batch
    created_issues = jira.batch_create_issues(issues_list, validate_only=validate_only)

    message = (
        "Issues validated successfully"
        if validate_only
        else "Issues created successfully"
    )
    result = {
        "message": message,
        "issues": [issue.to_simplified_dict() for issue in created_issues],
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="changelogs", service_name="Jira")
async def batch_get_changelogs(
    ctx: Context,
    issue_ids_or_keys: Annotated[
        list[str],
        Field(
            description="List of Jira issue IDs or keys, e.g. ['PROJ-123', 'PROJ-124']"
        ),
    ],
    fields: Annotated[
        list[str] | None,
        Field(
            description="(Optional) Filter the changelogs by fields, e.g. ['status', 'assignee']. Default to None for all fields.",
            default=None,
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            description=(
                "Maximum number of changelogs to return in result for each issue. "
                "Default to -1 for all changelogs. "
                "Notice that it only limits the results in the response, "
                "the function will still fetch all the data."
            ),
            default=-1,
        ),
    ] = -1,
) -> str:
    """Get changelogs for multiple Jira issues (Cloud only).

    Args:
        ctx: The FastMCP context.
        issue_ids_or_keys: List of issue IDs or keys.
        fields: List of fields to filter changelogs by. None for all fields.
        limit: Maximum changelogs per issue (-1 for all).

    Returns:
        JSON string representing a list of issues with their changelogs.

    Raises:
        NotImplementedError: If run on Jira Server/Data Center.
        ValueError: If Jira client is unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    # Ensure this runs only on Cloud, as per original function docstring
    if not jira.config.is_cloud:
        raise NotImplementedError(
            "Batch get issue changelogs is only available on Jira Cloud."
        )

    # Call the underlying method
    issues_with_changelogs = jira.batch_get_changelogs(
        issue_ids_or_keys=issue_ids_or_keys, fields=fields
    )

    # Format the response
    results = []
    limit_val = None if limit == -1 else limit
    for issue in issues_with_changelogs:
        results.append(
            {
                "issue_id": issue.id,
                "changelogs": [
                    changelog.to_simplified_dict()
                    for changelog in issue.changelogs[:limit_val]
                ],
            }
        )
    return json.dumps(results, indent=2, ensure_ascii=False)


def try_individual_field_updates(
    jira: Any, issue_key: str, failed_fields: dict[str, Any]
) -> dict[str, Any]:
    """Attempt to update fields individually to identify specific failures."""
    results: dict[str, dict[str, Any]] = {}
    successful_updates = {}

    for field_name, field_value in failed_fields.items():
        try:
            single_field_update = {field_name: field_value}
            jira.update_issue(issue_key=issue_key, **single_field_update)
            results[field_name] = {"status": "success"}
            successful_updates[field_name] = field_value
        except Exception as field_error:
            results[field_name] = {
                "status": "failed",
                "error": str(field_error),
                "error_type": type(field_error).__name__,
                "format_analysis": analyze_field_format(field_name, field_value),
            }

            # Try to extract JIRA-specific error details for individual fields
            if hasattr(field_error, "response") and field_error.response is not None:
                results[field_name].update(
                    {
                        "http_status": getattr(
                            field_error.response, "status_code", None
                        ),
                        "jira_response": getattr(field_error.response, "text", None),
                    }
                )

    return {
        "individual_results": results,
        "successful_updates": successful_updates,
        "failed_count": len([r for r in results.values() if r["status"] == "failed"]),
        "success_count": len([r for r in results.values() if r["status"] == "success"]),
    }


def analyze_field_format(field_id: str, field_value: Any) -> dict[str, Any]:
    """Analyze field value and suggest potential format fixes."""
    analysis = {
        "field_id": field_id,
        "current_value": field_value,
        "current_type": type(field_value).__name__,
        "suggestions": [],
    }

    # Check for boolean-like string values that might need object format
    if isinstance(field_value, str):
        lower_val = field_value.lower()
        if lower_val in ["yes", "no", "true", "false"]:
            analysis["suggestions"].extend(
                [
                    f"Try boolean object format: {{'value': '{field_value}'}}",
                    f"Try boolean direct format: {lower_val in ['true', 'yes']}",
                ]
            )

        # Check for select/option fields that might need object format
        if "customfield" in field_id:
            analysis["suggestions"].extend(
                [
                    f"Try select object format: {{'value': '{field_value}'}}",
                    f"Try select with ID format: {{'id': '{field_value}'}}",
                ]
            )

        # Check for user fields
        if "@" in field_value or "user" in field_id.lower():
            analysis["suggestions"].extend(
                [
                    f"Try user object format: {{'name': '{field_value}'}}",
                    f"Try user object format: {{'accountId': '{field_value}'}}",
                ]
            )

    # Check for numeric values that might need string format
    elif isinstance(field_value, int | float):
        analysis["suggestions"].append(f"Try string format: '{field_value}'")

    # Check for very large numbers that might be ranking/ordering fields
    if isinstance(field_value, int) and field_value > 1000000000:
        analysis["suggestions"].extend(
            [
                "This looks like a ranking/ordering field - consider if it should be auto-managed by JIRA",
                "Try string format for large numbers",
            ]
        )

    return analysis


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="issue", service_name="Jira")
async def update_issue(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    fields: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Dictionary of fields to update. For 'assignee', provide a string identifier (email, name, or accountId). "
                "Example: `{'assignee': 'user@example.com', 'summary': 'New Summary'}`"
            ),
        ),
    ],
<<<<<<< HEAD
=======
    additional_fields: Annotated[
        dict[str, Any] | str | None,
        Field(
            description="(Optional) Dictionary of additional fields to update. Use this for custom fields or more complex updates.",
            default=None,
        ),
    ] = None,
>>>>>>> fix/pydantic-validation-update-issue
    attachments: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) JSON string array or comma-separated list of file paths to attach to the issue. "
                "Example: '/path/to/file1.txt,/path/to/file2.txt' or ['/path/to/file1.txt','/path/to/file2.txt']"
            ),
            default=None,
        ),
    ] = None,
) -> str:
    """Update an existing Jira issue including changing status, adding Epic links, updating fields, etc.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        fields: (Required) Dictionary of fields to update.
        attachments: Optional JSON array string or comma-separated list of file paths.

    Returns:
        JSON string representing the updated issue object and attachment results.

    Raises:
        ValueError: If in read-only mode or Jira client unavailable, or invalid input.
    """
    jira = await get_jira_fetcher(ctx)
    # Use fields directly as dict
    if not isinstance(fields, dict):
        raise ValueError("fields must be a dictionary.")
    update_fields = fields

<<<<<<< HEAD
=======
    # Accept either dict or JSON string for additional fields
    if additional_fields is None:
        extra_fields: dict[str, Any] = {}
    elif isinstance(additional_fields, dict):
        extra_fields = additional_fields
    elif isinstance(additional_fields, str):
        try:
            extra_fields = json.loads(additional_fields)
            if not isinstance(extra_fields, dict):
                raise ValueError(
                    "Parsed additional_fields is not a JSON object (dict)."
                )
        except json.JSONDecodeError as e:
            raise ValueError(f"additional_fields is not valid JSON: {e}") from e
    else:
        raise ValueError("additional_fields must be a dictionary or JSON string.")

>>>>>>> fix/pydantic-validation-update-issue
    # Parse attachments
    attachment_paths = []
    if attachments:
        if isinstance(attachments, str):
            try:
                parsed = json.loads(attachments)
                if isinstance(parsed, list):
                    attachment_paths = [str(p) for p in parsed]
                else:
                    raise ValueError("attachments JSON string must be an array.")
            except json.JSONDecodeError:
                # Assume comma-separated if not valid JSON array
                attachment_paths = [
                    p.strip() for p in attachments.split(",") if p.strip()
                ]
        else:
            raise ValueError(
                "attachments must be a JSON array string or comma-separated string."
            )

    # Combine fields and additional_fields
    all_updates = {**update_fields}
    if attachment_paths:
        all_updates["attachments"] = attachment_paths

    try:
        issue = jira.update_issue(issue_key=issue_key, **all_updates)
        result = issue.to_simplified_dict()
        if (
            hasattr(issue, "custom_fields")
            and "attachment_results" in issue.custom_fields
        ):
            result["attachment_results"] = issue.custom_fields["attachment_results"]
        return json.dumps(
            {"message": "Issue updated successfully", "issue": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        # Enhanced error details for debugging
        error_details = {
            "error_type": type(e).__name__,
            "message": str(e),
            "issue_key": issue_key,
            "attempted_updates": {
                "fields": update_fields,
                "additional_fields": extra_fields,
                "attachment_paths": attachment_paths,
            },
        }

        # Try to extract JIRA-specific error information
        if hasattr(e, "response") and e.response is not None:
            error_details.update(
                {
                    "http_status": getattr(e.response, "status_code", None),
                    "jira_response": getattr(e.response, "text", None),
                }
            )

        # Try to extract more detailed error info from common JIRA exception types
        if hasattr(e, "status_code"):
            error_details["http_status"] = e.status_code
        if hasattr(e, "text"):
            error_details["jira_response"] = e.text

        logger.error(
            f"Error updating issue {issue_key}: {json.dumps(error_details, indent=2)}",
            exc_info=True,
        )

        # If we have additional fields and the batch update failed, try individual field updates
        if extra_fields:
            logger.info(
                f"Batch update failed for {issue_key}, attempting individual field updates..."
            )

            # First try to update standard fields only (if any)
            standard_update_success = False
            if update_fields:
                try:
                    jira.update_issue(issue_key=issue_key, **update_fields)
                    standard_update_success = True
                    logger.info(f"Standard fields updated successfully for {issue_key}")
                except Exception as std_error:
                    logger.warning(
                        f"Standard fields also failed for {issue_key}: {str(std_error)}"
                    )

            # Try individual additional field updates
            individual_results = try_individual_field_updates(
                jira, issue_key, extra_fields
            )

            # If some individual updates succeeded, return partial success
            if individual_results["success_count"] > 0 or standard_update_success:
                response = {
                    "message": "Partial update completed with some failures",
                    "issue_key": issue_key,
                    "batch_error": error_details,
                    "individual_field_results": individual_results,
                    "standard_fields_updated": standard_update_success,
                }

                # Try to get the updated issue for the response
                try:
                    updated_issue = jira.get_issue(issue_key=issue_key)
                    response["issue"] = updated_issue.to_simplified_dict()
                except Exception:
                    response["issue"] = {
                        "key": issue_key,
                        "note": "Could not retrieve updated issue details",
                    }

                return json.dumps(response, indent=2, ensure_ascii=False)

        # If no fallback succeeded or no additional fields, return structured error response
        # instead of raising exception to ensure detailed error info reaches MCP client
        error_response = {
            "success": False,
            "error": f"Failed to update issue {issue_key}",
            "details": error_details,
            "troubleshooting_guide": "Check field names, required fields, and permissions in your JIRA project",
        }

        # Add field analysis for debugging if we had extra fields
        if extra_fields:
            error_response["field_analysis"] = {}
            for field_name, field_value in extra_fields.items():
                error_response["field_analysis"][field_name] = analyze_field_format(
                    field_name, field_value
                )

        return json.dumps(error_response, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="result", service_name="Jira")
async def delete_issue(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g. PROJ-123)")],
) -> str:
    """Delete an existing Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.

    Returns:
        JSON string indicating success.

    Raises:
        ValueError: If in read-only mode or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    deleted = jira.delete_issue(issue_key)
    result = {"message": f"Issue {issue_key} has been deleted successfully."}
    # The underlying method raises on failure, so if we reach here, it's success.
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="comment", service_name="Jira")
async def add_comment(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    comment: Annotated[str, Field(description="Comment text in Markdown format")],
    visibility: Annotated[
        dict[str, str],
        Field(
            description="""(Optional) Comment visibility (e.g. {"type":"group","value":"jira-users"})"""
        ),
    ] = None,
) -> str:
    """Add a comment to a Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        comment: Comment text in Markdown.
        visibility: (Optional) Comment visibility (e.g. {"type":"group","value":"jira-users"}).

    Returns:
        JSON string representing the added comment object.

    Raises:
        ValueError: If in read-only mode or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    # add_comment returns dict
    result = jira.add_comment(issue_key, comment, visibility)
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="worklog", service_name="Jira")
async def add_worklog(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    time_spent: Annotated[
        str,
        Field(
            description=(
                "Time spent in Jira format. Examples: "
                "'1h 30m' (1 hour and 30 minutes), '1d' (1 day), '30m' (30 minutes), '4h' (4 hours)"
            )
        ),
    ],
    comment: Annotated[
        str | None,
        Field(description="(Optional) Comment for the worklog in Markdown format"),
    ] = None,
    started: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Start time in ISO format. If not provided, the current time will be used. "
                "Example: '2023-08-01T12:00:00.000+0000'"
            )
        ),
    ] = None,
    # Add original_estimate and remaining_estimate as per original tool
    original_estimate: Annotated[
        str | None, Field(description="(Optional) New value for the original estimate")
    ] = None,
    remaining_estimate: Annotated[
        str | None, Field(description="(Optional) New value for the remaining estimate")
    ] = None,
) -> str:
    """Add a worklog entry to a Jira issue.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        time_spent: Time spent in Jira format.
        comment: Optional comment in Markdown.
        started: Optional start time in ISO format.
        original_estimate: Optional new original estimate.
        remaining_estimate: Optional new remaining estimate.


    Returns:
        JSON string representing the added worklog object.

    Raises:
        ValueError: If in read-only mode or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    # add_worklog returns dict
    worklog_result = jira.add_worklog(
        issue_key=issue_key,
        time_spent=time_spent,
        comment=comment,
        started=started,
        original_estimate=original_estimate,
        remaining_estimate=remaining_estimate,
    )
    result = {"message": "Worklog added successfully", "worklog": worklog_result}
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="issue", service_name="Jira")
async def link_to_epic(
    ctx: Context,
    issue_key: Annotated[
        str, Field(description="The key of the issue to link (e.g., 'PROJ-123')")
    ],
    epic_key: Annotated[
        str, Field(description="The key of the epic to link to (e.g., 'PROJ-456')")
    ],
) -> str:
    """Link an existing issue to an epic.

    Args:
        ctx: The FastMCP context.
        issue_key: The key of the issue to link.
        epic_key: The key of the epic to link to.

    Returns:
        JSON string representing the updated issue object.

    Raises:
        ValueError: If in read-only mode or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    issue = jira.link_issue_to_epic(issue_key, epic_key)
    result = {
        "message": f"Issue {issue_key} has been linked to epic {epic_key}.",
        "issue": issue.to_simplified_dict(),
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="result", service_name="Jira")
async def create_issue_link(
    ctx: Context,
    link_type: Annotated[
        str,
        Field(
            description="The type of link to create (e.g., 'Duplicate', 'Blocks', 'Relates to')"
        ),
    ],
    inward_issue_key: Annotated[
        str, Field(description="The key of the inward issue (e.g., 'PROJ-123')")
    ],
    outward_issue_key: Annotated[
        str, Field(description="The key of the outward issue (e.g., 'PROJ-456')")
    ],
    comment: Annotated[
        str | None, Field(description="(Optional) Comment to add to the link")
    ] = None,
    comment_visibility: Annotated[
        dict[str, str] | None,
        Field(
            description="(Optional) Visibility settings for the comment (e.g., {'type': 'group', 'value': 'jira-users'})",
            default=None,
        ),
    ] = None,
) -> str:
    """Create a link between two Jira issues.

    Args:
        ctx: The FastMCP context.
        link_type: The type of link (e.g., 'Blocks').
        inward_issue_key: The key of the source issue.
        outward_issue_key: The key of the target issue.
        comment: Optional comment text.
        comment_visibility: Optional dictionary for comment visibility.

    Returns:
        JSON string indicating success or failure.

    Raises:
        ValueError: If required fields are missing, invalid input, in read-only mode, or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    if not all([link_type, inward_issue_key, outward_issue_key]):
        raise ValueError(
            "link_type, inward_issue_key, and outward_issue_key are required."
        )

    link_data = {
        "type": {"name": link_type},
        "inwardIssue": {"key": inward_issue_key},
        "outwardIssue": {"key": outward_issue_key},
    }

    if comment:
        comment_obj = {"body": comment}
        if comment_visibility and isinstance(comment_visibility, dict):
            if "type" in comment_visibility and "value" in comment_visibility:
                comment_obj["visibility"] = comment_visibility
            else:
                logger.warning("Invalid comment_visibility dictionary structure.")
        link_data["comment"] = comment_obj

    result = jira.create_issue_link(link_data)
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="result", service_name="Jira")
async def create_remote_issue_link(
    ctx: Context,
    issue_key: Annotated[
        str,
        Field(description="The key of the issue to add the link to (e.g., 'PROJ-123')"),
    ],
    url: Annotated[
        str,
        Field(
            description="The URL to link to (e.g., 'https://example.com/page' or Confluence page URL)"
        ),
    ],
    title: Annotated[
        str,
        Field(
            description="The title/name of the link (e.g., 'Documentation Page', 'Confluence Page')"
        ),
    ],
    summary: Annotated[
        str | None, Field(description="(Optional) Description of the link")
    ] = None,
    relationship: Annotated[
        str | None,
        Field(
            description="(Optional) Relationship description (e.g., 'causes', 'relates to', 'documentation')"
        ),
    ] = None,
    icon_url: Annotated[
        str | None, Field(description="(Optional) URL to a 16x16 icon for the link")
    ] = None,
) -> str:
    """Create a remote issue link (web link or Confluence link) for a Jira issue.

    This tool allows you to add web links and Confluence links to Jira issues.
    The links will appear in the issue's "Links" section and can be clicked to navigate to external resources.

    Args:
        ctx: The FastMCP context.
        issue_key: The key of the issue to add the link to.
        url: The URL to link to (can be any web page or Confluence page).
        title: The title/name that will be displayed for the link.
        summary: Optional description of what the link is for.
        relationship: Optional relationship description.
        icon_url: Optional URL to a 16x16 icon for the link.

    Returns:
        JSON string indicating success or failure.

    Raises:
        ValueError: If required fields are missing, invalid input, in read-only mode, or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    if not issue_key:
        raise ValueError("issue_key is required.")
    if not url:
        raise ValueError("url is required.")
    if not title:
        raise ValueError("title is required.")

    # Build the remote link data structure
    link_object = {
        "url": url,
        "title": title,
    }

    if summary:
        link_object["summary"] = summary

    if icon_url:
        link_object["icon"] = {"url16x16": icon_url, "title": title}

    link_data = {"object": link_object}

    if relationship:
        link_data["relationship"] = relationship

    result = jira.create_remote_issue_link(issue_key, link_data)
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="result", service_name="Jira")
async def remove_issue_link(
    ctx: Context,
    link_id: Annotated[str, Field(description="The ID of the link to remove")],
) -> str:
    """Remove a link between two Jira issues.

    Args:
        ctx: The FastMCP context.
        link_id: The ID of the link to remove.

    Returns:
        JSON string indicating success.

    Raises:
        ValueError: If link_id is missing, in read-only mode, or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    if not link_id:
        raise ValueError("link_id is required")

    result = jira.remove_issue_link(link_id)  # Returns dict on success
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="issue", service_name="Jira")
async def transition_issue(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    transition_id: Annotated[
        str,
        Field(
            description=(
                "ID of the transition to perform. Use the jira_get_transitions tool first "
                "to get the available transition IDs for the issue. Example values: '11', '21', '31'"
            )
        ),
    ],
    fields: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "(Optional) Dictionary of fields to update during the transition. "
                "Some transitions require specific fields to be set (e.g., resolution). "
                "Example: {'resolution': {'name': 'Fixed'}}"
            ),
            default=None,
        ),
    ] = None,
    comment: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Comment to add during the transition. "
                "This will be visible in the issue history."
            ),
        ),
    ] = None,
) -> str:
    """Transition a Jira issue to a new status.

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key.
        transition_id: ID of the transition.
        fields: Optional dictionary of fields to update during transition.
        comment: Optional comment for the transition.

    Returns:
        JSON string representing the updated issue object.

    Raises:
        ValueError: If required fields missing, invalid input, in read-only mode, or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    if not issue_key or not transition_id:
        raise ValueError("issue_key and transition_id are required.")

    # Use fields directly as dict
    update_fields = fields or {}
    if not isinstance(update_fields, dict):
        raise ValueError("fields must be a dictionary.")

    issue = jira.transition_issue(
        issue_key=issue_key,
        transition_id=transition_id,
        fields=update_fields,
        comment=comment,
    )

    result = {
        "message": f"Issue {issue_key} transitioned successfully",
        "issue": issue.to_simplified_dict() if issue else None,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="sprint", service_name="Jira")
async def create_sprint(
    ctx: Context,
    board_id: Annotated[str, Field(description="The id of board (e.g., '1000')")],
    sprint_name: Annotated[
        str, Field(description="Name of the sprint (e.g., 'Sprint 1')")
    ],
    start_date: Annotated[
        str, Field(description="Start time for sprint (ISO 8601 format)")
    ],
    end_date: Annotated[
        str, Field(description="End time for sprint (ISO 8601 format)")
    ],
    goal: Annotated[
        str | None, Field(description="(Optional) Goal of the sprint")
    ] = None,
) -> str:
    """Create Jira sprint for a board.

    Args:
        ctx: The FastMCP context.
        board_id: Board ID.
        sprint_name: Sprint name.
        start_date: Start date (ISO format).
        end_date: End date (ISO format).
        goal: Optional sprint goal.

    Returns:
        JSON string representing the created sprint object.

    Raises:
        ValueError: If in read-only mode or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    sprint = jira.create_sprint(
        board_id=board_id,
        sprint_name=sprint_name,
        start_date=start_date,
        end_date=end_date,
        goal=goal,
    )
    return json.dumps(sprint.to_simplified_dict(), indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="sprint", service_name="Jira")
async def update_sprint(
    ctx: Context,
    sprint_id: Annotated[str, Field(description="The id of sprint (e.g., '10001')")],
    sprint_name: Annotated[
        str | None, Field(description="(Optional) New name for the sprint")
    ] = None,
    state: Annotated[
        str | None,
        Field(description="(Optional) New state for the sprint (future|active|closed)"),
    ] = None,
    start_date: Annotated[
        str | None, Field(description="(Optional) New start date for the sprint")
    ] = None,
    end_date: Annotated[
        str | None, Field(description="(Optional) New end date for the sprint")
    ] = None,
    goal: Annotated[
        str | None, Field(description="(Optional) New goal for the sprint")
    ] = None,
) -> str:
    """Update jira sprint.

    Args:
        ctx: The FastMCP context.
        sprint_id: The ID of the sprint.
        sprint_name: Optional new name.
        state: Optional new state (future|active|closed).
        start_date: Optional new start date.
        end_date: Optional new end date.
        goal: Optional new goal.

    Returns:
        JSON string representing the updated sprint object or an error message.

    Raises:
        ValueError: If in read-only mode or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    sprint = jira.update_sprint(
        sprint_id=sprint_id,
        sprint_name=sprint_name,
        state=state,
        start_date=start_date,
        end_date=end_date,
        goal=goal,
    )

    if sprint is None:
        error_payload = {
            "error": f"Failed to update sprint {sprint_id}. Check logs for details."
        }
        return json.dumps(error_payload, indent=2, ensure_ascii=False)
    else:
        return json.dumps(sprint.to_simplified_dict(), indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="versions", service_name="Jira")
async def get_project_versions(
    ctx: Context,
    project_key: Annotated[str, Field(description="Jira project key (e.g., 'PROJ')")],
) -> str:
    """Get all fix versions for a specific Jira project."""
    jira = await get_jira_fetcher(ctx)
    versions = jira.get_project_versions(project_key)
    return json.dumps(versions, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
<<<<<<< HEAD
@handle_tool_errors(default_return_key="projects", service_name="Jira")
=======
async def get_development_information(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    application_type: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Filter by application type: 'stash' (Bitbucket Server), "
                "'bitbucket' (Bitbucket Cloud), 'github', or 'gitlab'"
            ),
            default=None,
        ),
    ] = None,
) -> str:
    """Get development information (pull requests, branches, commits) linked to a Jira issue.
    
    This retrieves information from development tools integrated with Jira through plugins
    like Bitbucket for Jira, GitHub for Jira, or GitLab for Jira.
    
    Args:
        ctx: The FastMCP context.
        issue_key: The Jira issue key.
        application_type: Optional filter by integration type.
    
    Returns:
        JSON string containing linked pull requests, branches, commits, and builds.
    
    Raises:
        ValueError: If the issue key is invalid or Jira client unavailable.
    """
    jira = await get_jira_fetcher(ctx)
    
    try:
        dev_info = jira.get_development_information(
            issue_key=issue_key,
            application_type=application_type
        )
        
        # Convert to dict representation
        result = dev_info.to_dict()
        result["issue_key"] = issue_key
        
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to get development information for {issue_key}: {e}")
        # Return empty development info on error
        return json.dumps({
            "issue_key": issue_key,
            "has_development_info": False,
            "errors": [str(e)],
            "pull_requests": [],
            "branches": [],
            "commits": [],
            "builds": [],
            "summary": "Failed to retrieve development information"
        }, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
>>>>>>> suparious/main
async def get_all_projects(
    ctx: Context,
    include_archived: Annotated[
        bool,
        Field(
            description="Whether to include archived projects in the results",
            default=False,
        ),
    ] = False,
) -> str:
    """Get all Jira projects accessible to the current user.

    Args:
        ctx: The FastMCP context.
        include_archived: Whether to include archived projects.

    Returns:
        JSON string representing a list of project objects accessible to the user.
        Project keys are always returned in uppercase.
        If JIRA_PROJECTS_FILTER is configured, only returns projects matching those keys.

    Raises:
        ValueError: If the Jira client is not configured or available.
    """
    try:
        jira = await get_jira_fetcher(ctx)
        projects = jira.get_all_projects(include_archived=include_archived)
    except (MCPAtlassianAuthenticationError, HTTPError, OSError, ValueError) as e:
        error_message = ""
        log_level = logging.ERROR
        if isinstance(e, MCPAtlassianAuthenticationError):
            error_message = f"Authentication/Permission Error: {str(e)}"
        elif isinstance(e, OSError | HTTPError):
            error_message = f"Network or API Error: {str(e)}"
        elif isinstance(e, ValueError):
            error_message = f"Configuration Error: {str(e)}"

        error_result = {
            "success": False,
            "error": error_message,
        }
        logger.log(log_level, f"get_all_projects failed: {error_message}")
        return json.dumps(error_result, indent=2, ensure_ascii=False)

    # Ensure all project keys are uppercase
    for project in projects:
        if "key" in project:
            project["key"] = project["key"].upper()

    # Apply project filter if configured
    if jira.config.projects_filter:
        # Split projects filter by commas and handle possible whitespace
        allowed_project_keys = {
            p.strip().upper() for p in jira.config.projects_filter.split(",")
        }
        projects = [
            project
            for project in projects
            if project.get("key") in allowed_project_keys
        ]

    return json.dumps(projects, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="issue_types", service_name="Jira")
async def get_all_issue_types(
    ctx: Context,
    project_key: Annotated[str, Field(description="Jira project key (e.g., 'PROJ')")],
) -> str:
    """Get all issue types for a specific Jira project.
    Args:
        ctx: The FastMCP context.
        project_key: The project key.

    Returns:
        JSON string representing a list of issue types.

    Raises:
        ValueError: If the Jira client is not configured or available.
    """
    jira = await get_jira_fetcher(ctx)
    issue_types = jira.get_project_issue_types(project_key)
    return json.dumps(issue_types, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
@handle_tool_errors(default_return_key="required_fields", service_name="Jira")
async def get_required_fields(
    ctx: Context,
    issue_type: Annotated[
        str,
        Field(
            description="Jira issue type (e.g., 'Task', 'Bug', 'Story', 'Epic', 'Subtask')"
        ),
    ],
    project_key: Annotated[str, Field(description="Jira project key (e.g., 'PROJ')")],
) -> str:
    """Get required fields for a specific Jira issue type in a project.
    Args:
        ctx: The FastMCP context.
        issue_type: The issue type.
        project_key: The project key.

    Returns:
        JSON string representing a list of required fields.

    Raises:
        ValueError: If the Jira client is not configured or available.
    """
    jira = await get_jira_fetcher(ctx)
    required_fields = jira.get_required_fields(issue_type, project_key)
    return json.dumps(required_fields, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="version", service_name="Jira")
async def create_version(
    ctx: Context,
    project_key: Annotated[str, Field(description="Jira project key (e.g., 'PROJ')")],
    name: Annotated[str, Field(description="Name of the version")],
    start_date: Annotated[
        str | None, Field(description="Start date (YYYY-MM-DD)", default=None)
    ] = None,
    release_date: Annotated[
        str | None, Field(description="Release date (YYYY-MM-DD)", default=None)
    ] = None,
    description: Annotated[
        str | None, Field(description="Description of the version", default=None)
    ] = None,
) -> str:
    """Create a new fix version in a Jira project.

    Args:
        ctx: The FastMCP context.
        project_key: The project key.
        name: Name of the version.
        start_date: Start date (optional).
        release_date: Release date (optional).
        description: Description (optional).

    Returns:
        JSON string of the created version object.
    """
    jira = await get_jira_fetcher(ctx)
    try:
        version = jira.create_project_version(
            project_key=project_key,
            name=name,
            start_date=start_date,
            release_date=release_date,
            description=description,
        )
        return json.dumps(version, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(
            f"Error creating version in project {project_key}: {str(e)}", exc_info=True
        )
        return json.dumps(
            {"success": False, "error": str(e)}, indent=2, ensure_ascii=False
        )


@jira_mcp.tool(name="batch_create_versions", tags={"jira", "write"})
@check_write_access
@handle_tool_errors(default_return_key="results", service_name="Jira")
async def batch_create_versions(
    ctx: Context,
    project_key: Annotated[str, Field(description="Jira project key (e.g., 'PROJ')")],
    versions: Annotated[
        str,
        Field(
            description=(
                "JSON array of version objects. Each object should contain:\n"
                "- name (required): Name of the version\n"
                "- startDate (optional): Start date (YYYY-MM-DD)\n"
                "- releaseDate (optional): Release date (YYYY-MM-DD)\n"
                "- description (optional): Description of the version\n"
                "Example: [\n"
                '  {"name": "v1.0", "startDate": "2025-01-01", "releaseDate": "2025-02-01", "description": "First release"},\n'
                '  {"name": "v2.0"}\n'
                "]"
            )
        ),
    ],
) -> str:
    """Batch create multiple versions in a Jira project.

    Args:
        ctx: The FastMCP context.
        project_key: The project key.
        versions: JSON array string of version objects.

    Returns:
        JSON array of results, each with success flag, version or error.
    """
    jira = await get_jira_fetcher(ctx)
    try:
        version_list = json.loads(versions)
        if not isinstance(version_list, list):
            raise ValueError("Input 'versions' must be a JSON array string.")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in versions")
    except Exception as e:
        raise ValueError(f"Invalid input for versions: {e}") from e

    results = []
    if not version_list:
        return json.dumps(results, indent=2, ensure_ascii=False)

    for idx, v in enumerate(version_list):
        # Defensive: ensure v is a dict and has a name
        if not isinstance(v, dict) or not v.get("name"):
            results.append(
                {
                    "success": False,
                    "error": f"Item {idx}: Each version must be an object with at least a 'name' field.",
                }
            )
            continue
        try:
            version = jira.create_project_version(
                project_key=project_key,
                name=v["name"],
                start_date=v.get("startDate"),
                release_date=v.get("releaseDate"),
                description=v.get("description"),
            )
            results.append({"success": True, "version": version})
        except Exception as e:
            logger.error(
                f"Error creating version in batch for project {project_key}: {str(e)}",
                exc_info=True,
            )
            results.append({"success": False, "error": str(e), "input": v})
    return json.dumps(results, indent=2, ensure_ascii=False)


<<<<<<< HEAD
@jira_mcp.tool(tags={"jira", "read"})
async def get_customfield_options(
    ctx: Context,
    field_id: Annotated[
        str,
        Field(
            description="The ID of the custom field (e.g., 'customfield_10001'). "
            "You can use the 'search_fields' tool to find the field ID for a custom field name."
        ),
    ],
    start_at: Annotated[
        int,
        Field(
            description="Starting index for pagination (0-based)",
            default=0,
            ge=0,
        ),
    ] = 0,
    max_results: Annotated[
        int,
        Field(
            description="Maximum number of results per page (1-10000)",
            default=10000,
            ge=1,
            le=10000,
        ),
    ] = 10000,
) -> str:
    """Get available options for a custom field in Jira.

    This retrieves the global options for a custom field. For more precise options
    based on context (project, issue type), use get_customfield_context_options.

    Args:
        ctx: The FastMCP context.
        field_id: The ID of the custom field (e.g., 'customfield_10001').
        start_at: Starting index for pagination.
        max_results: Maximum number of results per page.

    Returns:
        JSON string representing the field options with pagination info.
    """
    jira = await get_jira_fetcher(ctx)
    try:
        options_response = jira.get_field_options(
            field_id=field_id,
            start_at=start_at,
            max_results=max_results,
        )
        result = options_response.to_simplified_dict()
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error getting options for field '{field_id}': {str(e)}")
        error_result = {
            "success": False,
            "error": str(e),
            "field_id": field_id,
        }
        return json.dumps(error_result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_customfield_contexts(
    ctx: Context,
    field_id: Annotated[
        str,
        Field(
            description="The ID of the custom field (e.g., 'customfield_10001'). "
            "You can use the 'search_fields' tool to find the field ID for a custom field name."
        ),
    ],
    start_at: Annotated[
        int,
        Field(
            description="Starting index for pagination (0-based)",
            default=0,
            ge=0,
        ),
    ] = 0,
    max_results: Annotated[
        int,
        Field(
            description="Maximum number of results per page (1-10000)",
            default=10000,
            ge=1,
            le=10000,
        ),
    ] = 10000,
) -> str:
    """Get contexts for a custom field in Jira.

    Contexts define where and how custom fields are used. Different contexts
    can have different available options for the same field.

    Args:
        ctx: The FastMCP context.
        field_id: The ID of the custom field (e.g., 'customfield_10001').
        start_at: Starting index for pagination.
        max_results: Maximum number of results per page.

    Returns:
        JSON string representing the field contexts with pagination info.
    """
    jira = await get_jira_fetcher(ctx)
    try:
        contexts_response = jira.get_field_contexts(
            field_id=field_id,
            start_at=start_at,
            max_results=max_results,
        )
        result = contexts_response.to_simplified_dict()
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error getting contexts for field '{field_id}': {str(e)}")
        error_result = {
            "success": False,
            "error": str(e),
            "field_id": field_id,
        }
        return json.dumps(error_result, indent=2, ensure_ascii=False)


@jira_mcp.tool(tags={"jira", "read"})
async def get_customfield_context_options(
    ctx: Context,
    field_id: Annotated[
        str,
        Field(
            description="The ID of the custom field (e.g., 'customfield_10001'). "
            "You can use the 'search_fields' tool to find the field ID for a custom field name."
        ),
    ],
    context_id: Annotated[
        str,
        Field(
            description="The ID of the context. Use 'get_customfield_contexts' to find context IDs."
        ),
    ],
    start_at: Annotated[
        int,
        Field(
            description="Starting index for pagination (0-based)",
            default=0,
            ge=0,
        ),
    ] = 0,
    max_results: Annotated[
        int,
        Field(
            description="Maximum number of results per page (1-10000)",
            default=10000,
            ge=1,
            le=10000,
        ),
    ] = 10000,
) -> str:
    """Get options for a custom field within a specific context.

    This is the most precise way to get field options as they can differ by context.
    Different contexts (e.g., different projects or issue types) can have different
    available options for the same custom field.

    Args:
        ctx: The FastMCP context.
        field_id: The ID of the custom field (e.g., 'customfield_10001').
        context_id: The ID of the context.
        start_at: Starting index for pagination.
        max_results: Maximum number of results per page.

    Returns:
        JSON string representing the field options for the context with pagination info.
    """
    jira = await get_jira_fetcher(ctx)
    try:
        context_options_response = jira.get_field_context_options(
            field_id=field_id,
            context_id=context_id,
            start_at=start_at,
            max_results=max_results,
        )
        result = context_options_response.to_simplified_dict()
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(
            f"Error getting context options for field '{field_id}' in context '{context_id}': {str(e)}"
        )
        error_result = {
            "success": False,
            "error": str(e),
            "field_id": field_id,
            "context_id": context_id,
        }
        return json.dumps(error_result, indent=2, ensure_ascii=False)
=======
@jira_mcp.tool(tags={"jira", "write"})
@check_write_access
async def add_issues_to_sprint(
    ctx: Context,
    sprint_id: Annotated[str, Field(description="The ID of the sprint")],
    issues: Annotated[
        list[str], Field(description="A list of issue keys to add to the sprint")
    ],
) -> str:
    """
    Add issues to a sprint.

    Args:
        ctx: The FastMCP context.
        sprint_id: The ID of the sprint
        issues: A list of issue keys to add to the sprint

    Returns:
        JSON string indicating the result of the operation.
    """
    jira = await get_jira_fetcher(ctx)
    try:
        jira.add_issues_to_sprint(sprint_id, issues)
        return json.dumps(
            {"success": True, "message": f"Issues {issues} added to sprint {sprint_id}"}
        )
    except Exception as e:
        logger.error(f"Error adding issues to sprint: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)})
>>>>>>> feature/move-issue-to-sprint
=======
register_jira_tools(jira_mcp)
>>>>>>> feature/multi-server
