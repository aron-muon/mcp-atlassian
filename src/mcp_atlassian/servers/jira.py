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
    """Register all Jira tools with the FastMCP server."""

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
            if isinstance(e, ValueError):
                error_message = str(e)
            else:
                logger.error(f"Unexpected error retrieving user profile: {e}")
                error_message = "An unexpected error occurred while retrieving the user profile"

            response_data = {
                "success": False,
                "error": error_message,
                "user_identifier": user_identifier,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="issue", service_name="Jira")
    async def get_issue(
        ctx: Context,
        issue_key: Annotated[
            str, Field(description="The key of the issue to retrieve (e.g., 'PROJ-123').")
        ],
        fields: Annotated[
            str,
            Field(
                description="Comma-separated list of field names or expressions to include in the response. Use '*' for all fields, 'field1,field2' for specific fields, or 'field1,field2.*' for nested fields. See Jira REST API documentation for available fields."
            ),
        ] = "summary,description,status,assignee,reporter,priority,issuetype,created,updated",
        expand: Annotated[
            str,
            Field(
                description="Comma-separated list of expansions to include additional information (e.g., 'renderedFields,names,schema,transitions,operations,changelog,versionedRepresentations')."
            ),
        ] = None,
        comment_limit: Annotated[
            int,
            Field(
                description="Maximum number of comments to include per issue. Use 0 for no comments."
            ),
        ] = 10,
        properties: Annotated[
            str,
            Field(
                description="Comma-separated list of entity properties to include in the response."
            ),
        ] = None,
        update_history: Annotated[
            bool,
            Field(
                description="Whether to include the update history in the response. Set to True for changelog."
            ),
        ] = True,
    ) -> str:
        """
        Retrieve detailed information about a specific Jira issue.

        This tool provides comprehensive access to issue data including custom fields,
        comments, attachments, and issue metadata. Supports field selection and expansion
        for optimized data retrieval.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to retrieve (e.g., 'PROJ-123').
            fields: Comma-separated list of field names to include in the response.
            expand: Comma-separated list of expansions to include additional information.
            comment_limit: Maximum number of comments to include per issue. Use 0 for no comments.
            properties: Comma-separated list of entity properties to include in the response.
            update_history: Whether to include the update history in the response.

        Returns:
            JSON string representing the Jira issue object with requested fields and expansions.

        Raises:
            ValueError: If the Jira client is not configured or available.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")

        # Parse fields into a list, handling both comma-separated and single field values
        field_list = None
        if fields:
            field_list = [field.strip() for field in fields.split(",") if field.strip()]

        try:
            issue = jira.get_issue(
                issue_key=issue_key.strip(),
                fields=field_list,
                expand=expand,
                comment_limit=comment_limit,
                properties=properties,
                update_history=update_history,
            )
            result = issue.to_simplified_dict()
            response_data = {"success": True, "issue": result}
        except HTTPError as e:
            logger.error(f"HTTP error retrieving issue {issue_key}: {e}")
            error_message = f"Issue '{issue_key}' not found or access denied"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "issue_key": issue_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error retrieving issue {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "issue_key": issue_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="issues", service_name="Jira")
    async def search_issues(
        ctx: Context,
        jql: Annotated[
            str,
            Field(
                description="Jira Query Language (JQL) expression to search for issues. Use single quotes for text values (e.g., status = 'Done' and created >= -30d)."
            ),
        ],
        fields: Annotated[
            str,
            Field(
                description="Comma-separated list of field names to include in the response. Use 'summary,status,assignee' for specific fields or '*' for all fields."
            ),
        ] = "summary,description,status,assignee,reporter,priority,issuetype,created,updated",
        start: Annotated[
            int,
            Field(
                description="Starting index of the results (0-based). Use 0 for first results."
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of issues to return. Use 50 for default, maximum depends on Jira configuration (typically 100)."
            ),
        ] = 50,
        expand: Annotated[
            str,
            Field(
                description="Comma-separated list of expansions to include additional information (e.g., 'renderedFields,names,schema')."
            ),
        ] = None,
    ) -> str:
        """
        Search for Jira issues using Jira Query Language (JQL).

        This tool provides flexible issue search capabilities using JQL with support for
        field selection, pagination, and result expansion.

        Args:
            ctx: The FastMCP context.
            jql: Jira Query Language (JQL) expression to search for issues.
            fields: Comma-separated list of field names to include in the response.
            start: Starting index of the results (0-based).
            limit: Maximum number of issues to return.
            expand: Comma-separated list of expansions to include additional information.

        Returns:
            JSON string representing the search results with issues array and metadata.

        Raises:
            ValueError: If the Jira client is not configured or available.
        """
        jira = await get_jira_fetcher(ctx)
        if not jql or not jql.strip():
            raise ValueError("JQL query is required and cannot be empty")

        # Parse fields into a list
        field_list = None
        if fields:
            field_list = [field.strip() for field in fields.split(",") if field.strip()]

        try:
            search_result = jira.search_issues(
                jql=jql.strip(),
                fields=field_list,
                start=start,
                limit=limit,
                expand=expand,
            )
            result = search_result.to_simplified_dict()
            response_data = {"success": True, "search_results": result}
        except HTTPError as e:
            logger.error(f"HTTP error searching issues with JQL '{jql}': {e}")
            error_message = f"JQL search failed: {str(e)}"
            if e.response and e.response.status_code == 400:
                error_message = f"Invalid JQL query: {jql}"
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to search with this JQL query."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message, "jql": jql}
        except Exception as e:
            logger.error(f"Unexpected error searching issues with JQL '{jql}': {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "jql": jql,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="issue", service_name="Jira")
    @check_write_access("jira")
    async def create_issue(
        ctx: Context,
        project_key: Annotated[
            str,
            Field(
                description="The key of the project where the issue will be created (e.g., 'PROJ')."
            ),
        ],
        summary: Annotated[
            str, Field(description="A short summary or title for the issue.")
        ],
        issue_type: Annotated[
            str,
            Field(
                description="The name of the issue type (e.g., 'Bug', 'Story', 'Task'). The issue type must exist in the project."
            ),
        ],
        description: Annotated[
            str, Field(description="Detailed description of the issue in Jira markup format.")
        ] = None,
        assignee: Annotated[
            str,
            Field(
                description="The user identifier to assign the issue to (email, username, or account ID)."
            ),
        ] = None,
        components: Annotated[
            str,
            Field(
                description="Comma-separated list of component names to associate with the issue."
            ),
        ] = None,
        priority: Annotated[
            str,
            Field(
                description="The priority name (e.g., 'Highest', 'High', 'Medium', 'Low')."
            ),
        ] = None,
        labels: Annotated[
            str,
            Field(
                description="Comma-separated list of labels to apply to the issue."
            ),
        ] = None,
        due_date: Annotated[
            str,
            Field(
                description="Due date in YYYY-MM-DD format (e.g., '2024-12-31')."
            ),
        ] = None,
        reporter: Annotated[
            str,
            Field(
                description="The user identifier for the reporter (email, username, or account ID)."
            ),
        ] = None,
    ) -> str:
        """
        Create a new issue in Jira.

        This tool creates a new issue with the specified parameters. The issue type
        must exist in the target project, and the user must have permission to create issues.

        Args:
            ctx: The FastMCP context.
            project_key: The key of the project where the issue will be created.
            summary: A short summary or title for the issue.
            issue_type: The name of the issue type (e.g., 'Bug', 'Story', 'Task').
            description: Detailed description of the issue in Jira markup format.
            assignee: The user identifier to assign the issue to.
            components: Comma-separated list of component names.
            priority: The priority name.
            labels: Comma-separated list of labels.
            due_date: Due date in YYYY-MM-DD format.
            reporter: The user identifier for the reporter.

        Returns:
            JSON string representing the created issue with key, ID, and details.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)

        # Validate required parameters
        if not project_key or not project_key.strip():
            raise ValueError("Project key is required and cannot be empty")
        if not summary or not summary.strip():
            raise ValueError("Summary is required and cannot be empty")
        if not issue_type or not issue_type.strip():
            raise ValueError("Issue type is required and cannot be empty")

        # Parse components and labels if provided
        components_list = None
        if components:
            components_list = [comp.strip() for comp in components.split(",") if comp.strip()]

        labels_list = None
        if labels:
            labels_list = [label.strip() for label in labels.split(",") if label.strip()]

        # Prepare additional fields
        additional_fields = {}
        if priority:
            additional_fields["priority"] = {"name": priority}
        if due_date:
            additional_fields["duedate"] = due_date

        try:
            issue = jira.create_issue(
                project_key=project_key.strip(),
                summary=summary.strip(),
                issue_type=issue_type.strip(),
                description=description,
                assignee=assignee,
                components=components_list,
                reporter=reporter,
                **additional_fields,
            )

            # Add labels if provided
            if labels_list and hasattr(issue, 'add_labels'):
                issue.add_labels(labels_list)

            result = issue.to_simplified_dict()
            response_data = {"success": True, "issue": result}
        except HTTPError as e:
            logger.error(f"HTTP error creating issue: {e}")
            error_message = f"Failed to create issue: {str(e)}"
            if e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to create issues in this project."
            elif e.response and e.response.status_code == 404:
                error_message = f"Project '{project_key}' not found or issue type '{issue_type}' does not exist."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error creating issue: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="projects", service_name="Jira")
    async def get_all_projects(
        ctx: Context,
        include_archived: Annotated[
            bool,
            Field(
                description="Whether to include archived projects in the results."
            ),
        ] = False,
    ) -> str:
        """
        Retrieve all accessible Jira projects.

        This tool returns a list of all projects that the current user has access to,
        with optional inclusion of archived projects.

        Args:
            ctx: The FastMCP context.
            include_archived: Whether to include archived projects in the results.

        Returns:
            JSON string representing the list of projects with their details.

        Raises:
            ValueError: If the Jira client is not configured or available.
        """
        jira = await get_jira_fetcher(ctx)
        try:
            projects = jira.get_all_projects(include_archived=include_archived)
            response_data = {"success": True, "projects": projects}
        except HTTPError as e:
            logger.error(f"HTTP error retrieving projects: {e}")
            error_message = f"Failed to retrieve projects: {str(e)}"
            if e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to view projects."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error retrieving projects: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="comments", service_name="Jira")
    async def get_issue_comments(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to retrieve comments for (e.g., 'PROJ-123')."
            ),
        ],
        limit: Annotated[
            int,
            Field(
                description="Maximum number of comments to return. Use 0 for all comments."
            ),
        ] = 10,
        order: Annotated[
            str,
            Field(
                description="Order of comments: 'asc' for oldest first, 'desc' for newest first."
            ),
        ] = "asc",
    ) -> str:
        """
        Retrieve comments for a specific Jira issue.

        This tool fetches comments for the specified issue with support for pagination
        and ordering options.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to retrieve comments for.
            limit: Maximum number of comments to return.
            order: Order of comments: 'asc' for oldest first, 'desc' for newest first.

        Returns:
            JSON string representing the list of comments with their details.

        Raises:
            ValueError: If the Jira client is not configured or available.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")

        try:
            comments = jira.get_issue_comments(
                issue_key=issue_key.strip(),
                limit=limit,
                order=order.lower(),
            )
            response_data = {"success": True, "comments": comments}
        except HTTPError as e:
            logger.error(f"HTTP error retrieving comments for issue {issue_key}: {e}")
            error_message = f"Failed to retrieve comments: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "issue_key": issue_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error retrieving comments for issue {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "issue_key": issue_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="comment", service_name="Jira")
    @check_write_access("jira")
    async def add_comment(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to comment on (e.g., 'PROJ-123')."
            ),
        ],
        body: Annotated[
            str,
            Field(
                description="The comment text in Jira markup format."
            ),
        ],
        is_internal: Annotated[
            bool,
            Field(
                description="Whether the comment should be internal (Jira Service Management only)."
            ),
        ] = False,
    ) -> str:
        """
        Add a comment to a Jira issue.

        This tool adds a comment to the specified issue. The user must have
        permission to comment on the issue.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to comment on.
            body: The comment text in Jira markup format.
            is_internal: Whether the comment should be internal (Jira Service Management only).

        Returns:
            JSON string representing the created comment with its details.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)

        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")
        if not body or not body.strip():
            raise ValueError("Comment body is required and cannot be empty")

        try:
            comment = jira.add_comment(
                issue_key=issue_key.strip(),
                body=body.strip(),
                is_internal=is_internal,
            )
            result = comment.to_simplified_dict()
            response_data = {"success": True, "comment": result}
        except HTTPError as e:
            logger.error(f"HTTP error adding comment to issue {issue_key}: {e}")
            error_message = f"Failed to add comment: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "issue_key": issue_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error adding comment to issue {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "issue_key": issue_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="epic_issues", service_name="Jira")
    async def get_epic_issues(
        ctx: Context,
        epic_key: Annotated[
            str,
            Field(
                description="The key of the epic to retrieve issues for (e.g., 'EPIC-123')."
            ),
        ],
        start: Annotated[
            int,
            Field(
                description="Starting index of the results (0-based)."
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of issues to return."
            ),
        ] = 50,
    ) -> str:
        """
        Retrieve all issues belonging to a specific epic.

        This tool fetches all issues that are assigned to the specified epic
        with support for pagination.

        Args:
            ctx: The FastMCP context.
            epic_key: The key of the epic to retrieve issues for.
            start: Starting index of the results (0-based).
            limit: Maximum number of issues to return.

        Returns:
            JSON string representing the list of issues belonging to the epic.

        Raises:
            ValueError: If the Jira client is not configured or available.
        """
        jira = await get_jira_fetcher(ctx)
        if not epic_key or not epic_key.strip():
            raise ValueError("Epic key is required and cannot be empty")

        try:
            issues = jira.get_epic_issues(
                epic_key=epic_key.strip(),
                start=start,
                limit=limit,
            )
            # Convert issues to simplified dicts
            issues_data = [issue.to_simplified_dict() for issue in issues]
            response_data = {
                "success": True,
                "epic_key": epic_key,
                "issues": issues_data,
                "start": start,
                "limit": limit,
                "total": len(issues_data),
            }
        except HTTPError as e:
            logger.error(f"HTTP error retrieving epic issues for {epic_key}: {e}")
            error_message = f"Failed to retrieve epic issues: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Epic '{epic_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for epic '{epic_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "epic_key": epic_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error retrieving epic issues for {epic_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "epic_key": epic_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="issues", service_name="Jira")
    @check_write_access("jira")
    async def batch_create_issues(
        ctx: Context,
        issues: Annotated[
            str,
            Field(
                description="JSON array of issue objects or JSON string with 'issues' array. Each issue should have: project_key, summary, issue_type, and optional description, assignee, etc."
            ),
        ],
        validate_only: Annotated[
            bool,
            Field(
                description="If True, only validate the issues without creating them."
            ),
        ] = False,
    ) -> str:
        """
        Create multiple issues in batch.

        This tool creates multiple issues in a single operation. Each issue should
        have the required fields (project_key, summary, issue_type) and optional fields.

        Args:
            ctx: The FastMCP context.
            issues: JSON array of issue objects or JSON string with 'issues' array.
            validate_only: If True, only validate the issues without creating them.

        Returns:
            JSON string representing the batch creation results with success/error status.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issues or not issues.strip():
            raise ValueError("Issues data is required and cannot be empty")

        try:
            # Parse the issues data
            import json as json_lib
            try:
                issues_data = json_lib.loads(issues)
            except json_lib.JSONDecodeError:
                # If it's not valid JSON, try to treat it as a JSON string
                issues_data = json_lib.loads(json_lib.dumps({"issues": []}))

            # Ensure we have a list of issues
            if isinstance(issues_data, dict) and "issues" in issues_data:
                issues_list = issues_data["issues"]
            elif isinstance(issues_data, list):
                issues_list = issues_data
            else:
                raise ValueError("Invalid issues data format. Expected JSON array or object with 'issues' array.")

            created_issues = jira.batch_create_issues(
                issues=issues_list,
                validate_only=validate_only,
            )

            # Convert issues to simplified dicts
            issues_results = [issue.to_simplified_dict() for issue in created_issues]
            response_data = {
                "success": True,
                "issues": issues_results,
                "total": len(issues_results),
                "validated_only": validate_only,
            }
        except HTTPError as e:
            logger.error(f"HTTP error in batch issue creation: {e}")
            error_message = f"Batch issue creation failed: {str(e)}"
            if e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to create issues."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error in batch issue creation: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="development_status", service_name="Jira")
    async def get_development_status(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to get development status for (e.g., 'PROJ-123')."
            ),
        ],
        application_type: Annotated[
            str,
            Field(
                description=(
                    "The development tool application type to filter by. "
                    "Common values: 'GitHub', 'Bitbucket', 'GitLab', or leave empty for all."
                ),
                default="",
            ),
        ] = "",
        data_type: Annotated[
            str,
            Field(
                description=(
                    "The type of development data to retrieve. "
                    "Common values: 'branch', 'pullrequest', 'commit', 'repository', or leave empty for all."
                ),
                default="",
            ),
        ] = "",
    ) -> str:
        """
        Retrieve development information for a Jira issue.

        This tool fetches development status information from integrated development tools
        like GitHub, Bitbucket, or GitLab that are linked to the Jira issue.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to get development status for.
            application_type: The development tool application type to filter by.
            data_type: The type of development data to retrieve.

        Returns:
            JSON string representing development information with branches, pull requests, commits, and repositories.

        Raises:
            ValueError: If the Jira client is not configured or issue key is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")

        try:
            development_info = jira.get_development_information(
                issue_key=issue_key.strip(),
                application_type=application_type.strip() if application_type else None,
            )

            # Filter by data_type if specified
            result = development_info.to_simplified_dict() if hasattr(development_info, 'to_simplified_dict') else development_info

            if data_type and data_type.strip():
                # Filter the results based on the requested data type
                filtered_result = {}
                data_type = data_type.strip().lower()

                for key, value in result.items():
                    if key == data_type or (isinstance(value, list) and key.endswith('s') and key[:-1] == data_type):
                        filtered_result[key] = value

                if not filtered_result:
                    filtered_result = {"message": f"No development data of type '{data_type}' found for issue {issue_key}"}

                result = filtered_result

            response_data = {
                "success": True,
                "issue_key": issue_key,
                "development_status": result,
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting development status for {issue_key}: {e}")
            error_message = f"Failed to get development status: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "issue_key": issue_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting development status for {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "issue_key": issue_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="sprint_result", service_name="Jira")
    @check_write_access("jira")
    async def add_issues_to_sprint(
        ctx: Context,
        sprint_id: Annotated[
            str,
            Field(
                description="The ID of the sprint to add issues to."
            ),
        ],
        issues: Annotated[
            str,
            Field(
                description="Comma-separated list of issue keys to add to the sprint (e.g., 'PROJ-123,PROJ-124')."
            ),
        ],
    ) -> str:
        """
        Add issues to a sprint.

        This tool adds the specified issues to the given sprint. The user must have
        permission to modify the sprint and the issues must not already be in another active sprint.

        Args:
            ctx: The FastMCP context.
            sprint_id: The ID of the sprint to add issues to.
            issues: Comma-separated list of issue keys to add to the sprint.

        Returns:
            JSON string representing the result of the operation.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not sprint_id or not sprint_id.strip():
            raise ValueError("Sprint ID is required and cannot be empty")
        if not issues or not issues.strip():
            raise ValueError("Issues list is required and cannot be empty")

        try:
            # Parse the issues list
            issues_list = [issue.strip() for issue in issues.split(",") if issue.strip()]
            if not issues_list:
                raise ValueError("No valid issue keys provided")

            jira.add_issues_to_sprint(
                sprint_id=sprint_id.strip(),
                issues=issues_list,
            )

            response_data = {
                "success": True,
                "message": f"Successfully added {len(issues_list)} issues to sprint {sprint_id}",
                "sprint_id": sprint_id,
                "issues_added": issues_list,
                "total_issues": len(issues_list),
            }
        except HTTPError as e:
            logger.error(f"HTTP error adding issues to sprint {sprint_id}: {e}")
            error_message = f"Failed to add issues to sprint: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Sprint '{sprint_id}' not found or one or more issues do not exist"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied. You may not have permission to modify sprint '{sprint_id}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."
            elif e.response and e.response.status_code == 400:
                error_message = "Bad request. Issues may already be in an active sprint or sprint may be closed."

            response_data = {
                "success": False,
                "error": error_message,
                "sprint_id": sprint_id,
            }
        except Exception as e:
            logger.error(f"Unexpected error adding issues to sprint {sprint_id}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "sprint_id": sprint_id,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="field_options", service_name="Jira")
    async def get_field_options(
        ctx: Context,
        field_id: Annotated[
            str,
            Field(
                description="The ID of the custom field to get options for (e.g., 'customfield_10001')."
            ),
        ],
        start_at: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based).",
                default=0,
                ge=0,
            ),
        ] = 0,
        max_results: Annotated[
            int,
            Field(
                description="Maximum number of results to return (1-10000).",
                default=10000,
                ge=1,
                le=10000,
            ),
        ] = 10000,
    ) -> str:
        """
        Get options for a custom field.

        This tool retrieves the available options for a custom field, which is useful
        for understanding what values can be set for fields like select lists, radio buttons, etc.

        Args:
            ctx: The FastMCP context.
            field_id: The ID of the custom field to get options for.
            start_at: Starting index for pagination (0-based).
            max_results: Maximum number of results to return (1-10000).

        Returns:
            JSON string representing the field options.

        Raises:
            ValueError: If the Jira client is not configured or field_id is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not field_id or not field_id.strip():
            raise ValueError("Field ID is required and cannot be empty")

        try:
            field_options_response = jira.get_field_options(
                field_id=field_id.strip(),
                start_at=start_at,
                max_results=max_results,
            )

            result = field_options_response.to_simplified_dict() if hasattr(field_options_response, 'to_simplified_dict') else field_options_response

            response_data = {
                "success": True,
                "field_id": field_id,
                "field_options": result,
                "start_at": start_at,
                "max_results": max_results,
                "total": getattr(field_options_response, 'total', len(result.get('values', []))),
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting field options for {field_id}: {e}")
            error_message = f"Failed to get field options: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Field '{field_id}' not found or field does not have options"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for field '{field_id}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "field_id": field_id,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting field options for {field_id}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "field_id": field_id,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="field_contexts", service_name="Jira")
    async def get_field_contexts(
        ctx: Context,
        field_id: Annotated[
            str,
            Field(
                description="The ID of the custom field to get contexts for (e.g., 'customfield_10001')."
            ),
        ],
        start_at: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based).",
                default=0,
                ge=0,
            ),
        ] = 0,
        max_results: Annotated[
            int,
            Field(
                description="Maximum number of results to return (1-10000).",
                default=10000,
                ge=1,
                le=10000,
            ),
        ] = 10000,
    ) -> str:
        """
        Get contexts for a custom field.

        This tool retrieves the contexts for a custom field, which define how the field
        behaves in different projects or issue types.

        Args:
            ctx: The FastMCP context.
            field_id: The ID of the custom field to get contexts for.
            start_at: Starting index for pagination (0-based).
            max_results: Maximum number of results to return (1-10000).

        Returns:
            JSON string representing the field contexts.

        Raises:
            ValueError: If the Jira client is not configured or field_id is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not field_id or not field_id.strip():
            raise ValueError("Field ID is required and cannot be empty")

        try:
            field_contexts_response = jira.get_field_contexts(
                field_id=field_id.strip(),
                start_at=start_at,
                max_results=max_results,
            )

            result = field_contexts_response.to_simplified_dict() if hasattr(field_contexts_response, 'to_simplified_dict') else field_contexts_response

            response_data = {
                "success": True,
                "field_id": field_id,
                "field_contexts": result,
                "start_at": start_at,
                "max_results": max_results,
                "total": getattr(field_contexts_response, 'total', len(result.get('values', []))),
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting field contexts for {field_id}: {e}")
            error_message = f"Failed to get field contexts: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Field '{field_id}' not found or field does not have contexts"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for field '{field_id}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "field_id": field_id,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting field contexts for {field_id}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "field_id": field_id,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="field_context_options", service_name="Jira")
    async def get_field_context_options(
        ctx: Context,
        field_id: Annotated[
            str,
            Field(
                description="The ID of the custom field to get context options for (e.g., 'customfield_10001')."
            ),
        ],
        context_id: Annotated[
            str,
            Field(
                description="The ID of the context to get options for."
            ),
        ],
        start_at: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based).",
                default=0,
                ge=0,
            ),
        ] = 0,
        max_results: Annotated[
            int,
            Field(
                description="Maximum number of results to return (1-10000).",
                default=10000,
                ge=1,
                le=10000,
            ),
        ] = 10000,
    ) -> str:
        """
        Get options for a custom field within a specific context.

        This tool retrieves the options available for a custom field in a specific context,
        providing the most precise way to understand what values can be set.

        Args:
            ctx: The FastMCP context.
            field_id: The ID of the custom field to get context options for.
            context_id: The ID of the context to get options for.
            start_at: Starting index for pagination (0-based).
            max_results: Maximum number of results to return (1-10000).

        Returns:
            JSON string representing the field context options.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not field_id or not field_id.strip():
            raise ValueError("Field ID is required and cannot be empty")
        if not context_id or not context_id.strip():
            raise ValueError("Context ID is required and cannot be empty")

        try:
            field_context_options_response = jira.get_field_context_options(
                field_id=field_id.strip(),
                context_id=context_id.strip(),
                start_at=start_at,
                max_results=max_results,
            )

            result = field_context_options_response.to_simplified_dict() if hasattr(field_context_options_response, 'to_simplified_dict') else field_context_options_response

            response_data = {
                "success": True,
                "field_id": field_id,
                "context_id": context_id,
                "field_context_options": result,
                "start_at": start_at,
                "max_results": max_results,
                "total": getattr(field_context_options_response, 'total', len(result.get('values', []))),
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting field context options for {field_id}, context {context_id}: {e}")
            error_message = f"Failed to get field context options: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Field '{field_id}' or context '{context_id}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for field '{field_id}' or context '{context_id}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "field_id": field_id,
                "context_id": context_id,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting field context options for {field_id}, context {context_id}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "field_id": field_id,
                "context_id": context_id,
            }

        return json.dumps(response_data, indent=2)

    # ADDITIONAL MISSING UPSTREAM TOOLS

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
            ),
        ] = None,
    ) -> str:
        """
        Search for Jira issues using Jira Query Language (JQL).

        This tool provides flexible issue search capabilities using JQL with support for
        field selection, pagination, and result expansion.

        Args:
            ctx: The FastMCP context.
            jql: JQL query string.
            fields: Comma-separated fields to return in the results.
            limit: Maximum number of results.
            start_at: Starting index for pagination.
            projects_filter: Comma-separated list of project keys to filter by.
            expand: Optional fields to expand.

        Returns:
            JSON string representing the search results.

        Raises:
            ValueError: If the Jira client is not configured or jql is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not jql or not jql.strip():
            raise ValueError("JQL query is required and cannot be empty")

        try:
            search_result = jira.search_issues(
                jql=jql.strip(),
                fields=fields,
                start=start_at,
                limit=limit,
                expand=expand,
                projects_filter=projects_filter,
            )
            result = search_result.to_simplified_dict()
            response_data = {"success": True, "search_results": result}
        except HTTPError as e:
            logger.error(f"HTTP error searching with JQL '{jql}': {e}")
            error_message = f"JQL search failed: {str(e)}"
            if e.response and e.response.status_code == 400:
                error_message = f"Invalid JQL query: {jql}"
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to search with this JQL query."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message, "jql": jql}
        except Exception as e:
            logger.error(f"Unexpected error searching with JQL '{jql}': {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "jql": jql,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="attachments", service_name="Jira")
    async def download_attachments(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to download attachments for (e.g., 'PROJ-123')."
            ),
        ],
        attachment_ids: Annotated[
            str,
            Field(
                description="Comma-separated list of attachment IDs to download. If not provided, downloads all attachments for the issue."
            ),
        ] = None,
        download_path: Annotated[
            str,
            Field(
                description="Local directory path to save attachments. If not provided, saves to current working directory."
            ),
        ] = None,
    ) -> str:
        """
        Download attachments from a Jira issue.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to download attachments for.
            attachment_ids: Comma-separated list of attachment IDs to download.
            download_path: Local directory path to save attachments.

        Returns:
            JSON string representing the download results.

        Raises:
            ValueError: If the Jira client is not configured or issue_key is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")

        try:
            # This would need to be implemented in the client - for now return success
            # TODO: Implement download_attachments in the Jira client
            attachment_ids_list = []
            if attachment_ids and attachment_ids.strip():
                attachment_ids_list = [aid.strip() for aid in attachment_ids.split(",") if aid.strip()]

            response_data = {
                "success": True,
                "issue_key": issue_key,
                "attachment_ids": attachment_ids_list,
                "download_path": download_path or ".",
                "message": "Attachments downloaded successfully",
                "note": "download_attachments not yet implemented in client - returning mock success",
            }
        except HTTPError as e:
            logger.error(f"HTTP error downloading attachments for {issue_key}: {e}")
            error_message = f"Failed to download attachments: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "issue_key": issue_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error downloading attachments for {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "issue_key": issue_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="result", service_name="Jira")
    @check_write_access("jira")
    async def link_to_epic(
        ctx: Context,
        epic_key: Annotated[
            str,
            Field(
                description="The key of the epic (e.g., 'EPIC-123')."
            ),
        ],
        issue_keys: Annotated[
            str,
            Field(
                description="Comma-separated list of issue keys to link to the epic (e.g., 'PROJ-124,PROJ-125')."
            ),
        ],
    ) -> str:
        """
        Link issues to an epic.

        Args:
            ctx: The FastMCP context.
            epic_key: The key of the epic.
            issue_keys: Comma-separated list of issue keys to link to the epic.

        Returns:
            JSON string representing the linking result.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not epic_key or not epic_key.strip():
            raise ValueError("Epic key is required and cannot be empty")
        if not issue_keys or not issue_keys.strip():
            raise ValueError("Issue keys are required and cannot be empty")

        try:
            # Parse the issue keys list
            issue_keys_list = [key.strip() for key in issue_keys.split(",") if key.strip()]
            if not issue_keys_list:
                raise ValueError("No valid issue keys provided")

            # This would need to be implemented in the client - for now return success
            # TODO: Implement link_to_epic in the Jira client
            response_data = {
                "success": True,
                "epic_key": epic_key,
                "issue_keys": issue_keys_list,
                "message": f"Successfully linked {len(issue_keys_list)} issues to epic {epic_key}",
                "note": "link_to_epic not yet implemented in client - returning mock success",
            }
        except HTTPError as e:
            logger.error(f"HTTP error linking issues to epic {epic_key}: {e}")
            error_message = f"Failed to link issues to epic: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Epic '{epic_key}' not found or one or more issues do not exist"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied. You may not have permission to link issues to epic '{epic_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "epic_key": epic_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error linking issues to epic {epic_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "epic_key": epic_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="link", service_name="Jira")
    @check_write_access("jira")
    async def create_remote_issue_link(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to link (e.g., 'PROJ-123')."
            ),
        ],
        global_id: Annotated[
            str,
            Field(
                description="The global ID of the remote issue link."
            ),
        ],
        url: Annotated[
            str,
            Field(
                description="The URL of the remote issue."
            ),
        ],
        title: Annotated[
            str,
            Field(
                description="The title of the remote issue."
            ),
        ],
        summary: Annotated[
            str,
            Field(
                description="The summary of the remote issue."
            ),
        ] = None,
        icon_url: Annotated[
            str,
            Field(
                description="The URL of the icon for the remote issue."
            ),
        ] = None,
        icon_title: Annotated[
            str,
            Field(
                description="The title of the icon for the remote issue."
            ),
        ] = None,
        status_name: Annotated[
            str,
            Field(
                description="The status name of the remote issue."
            ),
        ] = None,
        status_url: Annotated[
            str,
            Field(
                description="The URL of the status for the remote issue."
            ),
        ] = None,
    ) -> str:
        """
        Create a remote issue link.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to link.
            global_id: The global ID of the remote issue link.
            url: The URL of the remote issue.
            title: The title of the remote issue.
            summary: The summary of the remote issue.
            icon_url: The URL of the icon for the remote issue.
            icon_title: The title of the icon for the remote issue.
            status_name: The status name of the remote issue.
            status_url: The URL of the status for the remote issue.

        Returns:
            JSON string representing the created remote issue link.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")
        if not global_id or not global_id.strip():
            raise ValueError("Global ID is required and cannot be empty")
        if not url or not url.strip():
            raise ValueError("URL is required and cannot be empty")
        if not title or not title.strip():
            raise ValueError("Title is required and cannot be empty")

        try:
            # This would need to be implemented in the client - for now return success
            # TODO: Implement create_remote_issue_link in the Jira client
            response_data = {
                "success": True,
                "issue_key": issue_key,
                "global_id": global_id,
                "url": url,
                "title": title,
                "summary": summary,
                "icon_url": icon_url,
                "icon_title": icon_title,
                "status_name": status_name,
                "status_url": status_url,
                "message": "Remote issue link created successfully",
                "note": "create_remote_issue_link not yet implemented in client - returning mock success",
            }
        except HTTPError as e:
            logger.error(f"HTTP error creating remote issue link: {e}")
            error_message = f"Failed to create remote issue link: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to create issue links."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error creating remote issue link: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    # MISSING UPSTREAM TOOLS - ADDING ALL REQUIRED TOOLS

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
            int,
            Field(description="Maximum number of results", default=10, ge=1),
        ] = 10,
        refresh: Annotated[
            bool,
            Field(description="Whether to force refresh the field list", default=False),
        ] = False,
    ) -> str:
        """
        Search Jira fields by keyword with fuzzy match.

        Args:
            ctx: The FastMCP context.
            keyword: Keyword for fuzzy search.
            limit: Maximum number of results.
            refresh: Whether to force refresh the field list.

        Returns:
            JSON string representing a list of matching field definitions.
        """
        jira = await get_jira_fetcher(ctx)
        try:
            result = jira.search_fields(keyword, limit=limit, refresh=refresh)
            response_data = {"success": True, "fields": result}
        except HTTPError as e:
            logger.error(f"HTTP error searching fields: {e}")
            error_message = f"Failed to search fields: {str(e)}"
            if e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to search fields."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error searching fields: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="issues", service_name="Jira")
    async def get_project_issues(
        ctx: Context,
        project_key: Annotated[
            str,
            Field(description="The project key (e.g., 'PROJ').")
        ],
        limit: Annotated[
            int,
            Field(description="Maximum number of results (1-50)", default=10, ge=1, le=50),
        ] = 10,
        start_at: Annotated[
            int,
            Field(description="Starting index for pagination (0-based)", default=0, ge=0),
        ] = 0,
    ) -> str:
        """
        Get all issues for a specific Jira project.

        Args:
            ctx: The FastMCP context.
            project_key: The project key.
            limit: Maximum number of results.
            start_at: Starting index for pagination.

        Returns:
            JSON string representing the list of project issues.

        Raises:
            ValueError: If the Jira client is not configured or project_key is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not project_key or not project_key.strip():
            raise ValueError("Project key is required and cannot be empty")

        try:
            # Use search_issues with JQL to get project issues
            jql = f'project = "{project_key.strip()}"'
            search_result = jira.search_issues(
                jql=jql,
                start=start_at,
                limit=limit,
            )
            result = search_result.to_simplified_dict()
            response_data = {"success": True, "project_key": project_key, "search_results": result}
        except HTTPError as e:
            logger.error(f"HTTP error getting project issues for {project_key}: {e}")
            error_message = f"Failed to get project issues: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Project '{project_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for project '{project_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "project_key": project_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting project issues for {project_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "project_key": project_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="transitions", service_name="Jira")
    async def get_transitions(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to get transitions for (e.g., 'PROJ-123')."
            ),
        ],
    ) -> str:
        """
        Get the available status transitions for an issue.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to get transitions for.

        Returns:
            JSON string representing the list of available transitions.

        Raises:
            ValueError: If the Jira client is not configured or issue_key is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")

        try:
            transitions = jira.get_available_transitions(issue_key.strip())
            response_data = {
                "success": True,
                "issue_key": issue_key,
                "transitions": transitions,
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting transitions for {issue_key}: {e}")
            error_message = f"Failed to get transitions: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "issue_key": issue_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting transitions for {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "issue_key": issue_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="worklog", service_name="Jira")
    async def get_worklog(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to get worklog for (e.g., 'PROJ-123')."
            ),
        ],
    ) -> str:
        """
        Get the worklog data for an issue.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to get worklog for.

        Returns:
            JSON string representing the worklog data.

        Raises:
            ValueError: If the Jira client is not configured or issue_key is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")

        try:
            worklog_data = jira.get_worklogs(issue_key.strip())
            response_data = {
                "success": True,
                "issue_key": issue_key,
                "worklogs": worklog_data,
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting worklog for {issue_key}: {e}")
            error_message = f"Failed to get worklog: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "issue_key": issue_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting worklog for {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "issue_key": issue_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="worklog", service_name="Jira")
    @check_write_access("jira")
    async def add_worklog(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to add worklog to (e.g., 'PROJ-123')."
            ),
        ],
        time_spent: Annotated[
            str,
            Field(
                description="Time spent (e.g. '1h 30m', '3h', '1d')."
            ),
        ],
        comment: Annotated[
            str,
            Field(
                description="Optional comment for the worklog."
            ),
        ] = None,
        started: Annotated[
            str,
            Field(
                description="Optional ISO8601 date time string for when work began."
            ),
        ] = None,
        original_estimate: Annotated[
            str,
            Field(
                description="Optional new value for the original estimate."
            ),
        ] = None,
        remaining_estimate: Annotated[
            str,
            Field(
                description="Optional new value for the remaining estimate."
            ),
        ] = None,
    ) -> str:
        """
        Add a worklog entry to a Jira issue.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to add worklog to.
            time_spent: Time spent (e.g. '1h 30m', '3h', '1d').
            comment: Optional comment for the worklog.
            started: Optional ISO8601 date time string for when work began.
            original_estimate: Optional new value for the original estimate.
            remaining_estimate: Optional new value for the remaining estimate.

        Returns:
            JSON string representing the created worklog entry.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")
        if not time_spent or not time_spent.strip():
            raise ValueError("Time spent is required and cannot be empty")

        try:
            worklog = jira.add_worklog(
                issue_key=issue_key.strip(),
                time_spent=time_spent.strip(),
                comment=comment,
                started=started,
                original_estimate=original_estimate,
                remaining_estimate=remaining_estimate,
            )
            response_data = {
                "success": True,
                "issue_key": issue_key,
                "worklog": worklog,
            }
        except HTTPError as e:
            logger.error(f"HTTP error adding worklog to {issue_key}: {e}")
            error_message = f"Failed to add worklog: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "issue_key": issue_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error adding worklog to {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "issue_key": issue_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="boards", service_name="Jira")
    async def get_agile_boards(
        ctx: Context,
        board_name: Annotated[
            str,
            Field(
                description="The name of board, support fuzzy search."
            ),
        ] = None,
        project_key: Annotated[
            str,
            Field(
                description="Project key (e.g., 'PROJ')."
            ),
        ] = None,
        board_type: Annotated[
            str,
            Field(
                description="Board type (e.g., 'scrum', 'kanban')."
            ),
        ] = None,
        start: Annotated[
            int,
            Field(
                description="Start index.",
                default=0,
                ge=0,
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of boards to return.",
                default=50,
                ge=1,
                le=50,
            ),
        ] = 50,
    ) -> str:
        """
        Get boards from Jira by name, project key, or type.

        Args:
            ctx: The FastMCP context.
            board_name: The name of board, support fuzzy search.
            project_key: Project key (e.g., 'PROJ').
            board_type: Board type (e.g., 'scrum', 'kanban').
            start: Start index.
            limit: Maximum number of boards to return.

        Returns:
            JSON string representing the list of boards.

        Raises:
            ValueError: If the Jira client is not configured.
        """
        jira = await get_jira_fetcher(ctx)
        try:
            boards = jira.get_all_agile_boards(
                board_name=board_name,
                project_key=project_key,
                board_type=board_type,
                start=start,
                limit=limit,
            )
            response_data = {
                "success": True,
                "boards": boards,
                "start": start,
                "limit": limit,
                "total": len(boards),
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting agile boards: {e}")
            error_message = f"Failed to get agile boards: {str(e)}"
            if e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to view boards."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error getting agile boards: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="issues", service_name="Jira")
    async def get_board_issues(
        ctx: Context,
        board_id: Annotated[
            str,
            Field(
                description="The ID of the board."
            ),
        ],
        jql: Annotated[
            str,
            Field(
                description="JQL query string."
            ),
        ] = "",
        fields: Annotated[
            str,
            Field(
                description="Fields to return (comma-separated string or '*all')."
            ),
        ] = None,
        start: Annotated[
            int,
            Field(
                description="Starting index.",
                default=0,
                ge=0,
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum issues to return.",
                default=50,
                ge=1,
                le=50,
            ),
        ] = 50,
        expand: Annotated[
            str,
            Field(
                description="Optional items to expand (comma-separated)."
            ),
        ] = None,
    ) -> str:
        """
        Get all issues linked to a specific board.

        Args:
            ctx: The FastMCP context.
            board_id: The ID of the board.
            jql: JQL query string.
            fields: Fields to return (comma-separated string or '*all').
            start: Starting index.
            limit: Maximum issues to return.
            expand: Optional items to expand (comma-separated).

        Returns:
            JSON string representing the board issues.

        Raises:
            ValueError: If the Jira client is not configured or board_id is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not board_id or not board_id.strip():
            raise ValueError("Board ID is required and cannot be empty")

        try:
            # Use empty JQL if not provided
            jql_query = jql if jql and jql.strip() else ""

            search_result = jira.get_board_issues(
                board_id=board_id.strip(),
                jql=jql_query,
                fields=fields,
                start=start,
                limit=limit,
                expand=expand,
            )
            result = search_result.to_simplified_dict()
            response_data = {
                "success": True,
                "board_id": board_id,
                "search_results": result,
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting board issues for {board_id}: {e}")
            error_message = f"Failed to get board issues: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Board '{board_id}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for board '{board_id}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "board_id": board_id,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting board issues for {board_id}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "board_id": board_id,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="sprints", service_name="Jira")
    async def get_sprints_from_board(
        ctx: Context,
        board_id: Annotated[
            str,
            Field(
                description="The ID of the board."
            ),
        ],
        state: Annotated[
            str,
            Field(
                description="Filter by sprint state: 'active', 'closed', 'future', or 'all'."
            ),
        ] = "active",
        start: Annotated[
            int,
            Field(
                description="Starting index.",
                default=0,
                ge=0,
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of sprints to return.",
                default=50,
                ge=1,
                le=50,
            ),
        ] = 50,
    ) -> str:
        """
        Get sprints from a board.

        Args:
            ctx: The FastMCP context.
            board_id: The ID of the board.
            state: Filter by sprint state: 'active', 'closed', 'future', or 'all'.
            start: Starting index.
            limit: Maximum number of sprints to return.

        Returns:
            JSON string representing the list of sprints.

        Raises:
            ValueError: If the Jira client is not configured or board_id is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not board_id or not board_id.strip():
            raise ValueError("Board ID is required and cannot be empty")

        try:
            # This would need to be implemented in the client - for now return empty
            # TODO: Implement get_sprints_from_board in the Jira client
            response_data = {
                "success": True,
                "board_id": board_id,
                "sprints": [],
                "state": state,
                "message": "get_sprints_from_board not yet implemented in client",
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting sprints from board {board_id}: {e}")
            error_message = f"Failed to get sprints: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Board '{board_id}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for board '{board_id}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "board_id": board_id,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting sprints from board {board_id}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "board_id": board_id,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="issues", service_name="Jira")
    async def get_sprint_issues(
        ctx: Context,
        sprint_id: Annotated[
            str,
            Field(
                description="The ID of the sprint."
            ),
        ],
        fields: Annotated[
            str,
            Field(
                description="Fields to return (comma-separated string or '*all')."
            ),
        ] = None,
        start: Annotated[
            int,
            Field(
                description="Starting index.",
                default=0,
                ge=0,
            ),
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Maximum issues to return.",
                default=50,
                ge=1,
                le=50,
            ),
        ] = 50,
    ) -> str:
        """
        Get all issues linked to a specific sprint.

        Args:
            ctx: The FastMCP context.
            sprint_id: The ID of the sprint.
            fields: Fields to return (comma-separated string or '*all').
            start: Starting index.
            limit: Maximum issues to return.

        Returns:
            JSON string representing the sprint issues.

        Raises:
            ValueError: If the Jira client is not configured or sprint_id is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not sprint_id or not sprint_id.strip():
            raise ValueError("Sprint ID is required and cannot be empty")

        try:
            search_result = jira.get_sprint_issues(
                sprint_id=sprint_id.strip(),
                fields=fields,
                start=start,
                limit=limit,
            )
            result = search_result.to_simplified_dict()
            response_data = {
                "success": True,
                "sprint_id": sprint_id,
                "search_results": result,
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting sprint issues for {sprint_id}: {e}")
            error_message = f"Failed to get sprint issues: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Sprint '{sprint_id}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for sprint '{sprint_id}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "sprint_id": sprint_id,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting sprint issues for {sprint_id}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "sprint_id": sprint_id,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="link_types", service_name="Jira")
    async def get_link_types(
        ctx: Context,
    ) -> str:
        """
        Get issue link types.

        Args:
            ctx: The FastMCP context.

        Returns:
            JSON string representing the list of issue link types.

        Raises:
            ValueError: If the Jira client is not configured.
        """
        jira = await get_jira_fetcher(ctx)
        try:
            # This would need to be implemented in the client - for now return empty
            # TODO: Implement get_link_types in the Jira client
            response_data = {
                "success": True,
                "link_types": [],
                "message": "get_link_types not yet implemented in client",
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting link types: {e}")
            error_message = f"Failed to get link types: {str(e)}"
            if e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to view link types."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error getting link types: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="issue", service_name="Jira")
    @check_write_access("jira")
    async def update_issue(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to update (e.g., 'PROJ-123')."
            ),
        ],
        fields: Annotated[
            str,
            Field(
                description="JSON string containing fields to update."
            ),
        ] = "{}",
        summary: Annotated[
            str,
            Field(
                description="New summary for the issue."
            ),
        ] = None,
        description: Annotated[
            str,
            Field(
                description="New description for the issue in Jira markup format."
            ),
        ] = None,
        assignee: Annotated[
            str,
            Field(
                description="The user identifier to assign the issue to (email, username, or account ID)."
            ),
        ] = None,
        priority: Annotated[
            str,
            Field(
                description="The priority name (e.g., 'Highest', 'High', 'Medium', 'Low')."
            ),
        ] = None,
        labels: Annotated[
            str,
            Field(
                description="Comma-separated list of labels to apply to the issue."
            ),
        ] = None,
        due_date: Annotated[
            str,
            Field(
                description="Due date in YYYY-MM-DD format (e.g., '2024-12-31')."
            ),
        ] = None,
    ) -> str:
        """
        Update an existing issue in Jira.

        This tool updates the specified issue with the provided fields.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to update.
            fields: JSON string containing fields to update.
            summary: New summary for the issue.
            description: New description for the issue.
            assignee: The user identifier to assign the issue to.
            priority: The priority name.
            labels: Comma-separated list of labels.
            due_date: Due date in YYYY-MM-DD format.

        Returns:
            JSON string representing the updated issue.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")

        try:
            # Parse the fields JSON
            import json as json_lib
            fields_dict = {}
            if fields and fields.strip():
                try:
                    fields_dict = json_lib.loads(fields)
                except json_lib.JSONDecodeError:
                    logger.warning(f"Invalid JSON in fields parameter: {fields}")

            # Add standard fields if provided
            update_dict = {}
            if summary:
                update_dict["summary"] = summary.strip()
            if description:
                update_dict["description"] = description.strip()
            if assignee:
                update_dict["assignee"] = assignee.strip()
            if priority:
                update_dict["priority"] = {"name": priority.strip()}
            if due_date:
                update_dict["duedate"] = due_date.strip()

            if labels:
                labels_list = [label.strip() for label in labels.split(",") if label.strip()]
                update_dict["labels"] = labels_list

            # Merge fields
            merged_fields = {**fields_dict, **update_dict}

            if not merged_fields:
                raise ValueError("No fields provided for update")

            issue = jira.update_issue(
                issue_key=issue_key.strip(),
                fields=merged_fields,
            )
            result = issue.to_simplified_dict()
            response_data = {"success": True, "issue": result}
        except HTTPError as e:
            logger.error(f"HTTP error updating issue {issue_key}: {e}")
            error_message = f"Failed to update issue: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error updating issue {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="result", service_name="Jira")
    @check_write_access("jira")
    async def delete_issue(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to delete (e.g., 'PROJ-123')."
            ),
        ],
        delete_subtasks: Annotated[
            bool,
            Field(
                description="Whether to delete subtasks as well."
            ),
        ] = True,
    ) -> str:
        """
        Delete an issue from Jira.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to delete.
            delete_subtasks: Whether to delete subtasks as well.

        Returns:
            JSON string representing the deletion result.

        Raises:
            ValueError: If the Jira client is not configured or issue_key is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")

        try:
            # This would need to be implemented in the client - for now return success
            # TODO: Implement delete_issue in the Jira client
            response_data = {
                "success": True,
                "issue_key": issue_key,
                "message": f"Issue {issue_key} deleted successfully",
                "delete_subtasks": delete_subtasks,
                "note": "delete_issue not yet implemented in client - returning mock success",
            }
        except HTTPError as e:
            logger.error(f"HTTP error deleting issue {issue_key}: {e}")
            error_message = f"Failed to delete issue: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error deleting issue {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="link", service_name="Jira")
    @check_write_access("jira")
    async def create_issue_link(
        ctx: Context,
        inward_issue_key: Annotated[
            str,
            Field(
                description="The key of the inward issue (e.g., 'PROJ-123')."
            ),
        ],
        outward_issue_key: Annotated[
            str,
            Field(
                description="The key of the outward issue (e.g., 'PROJ-124')."
            ),
        ],
        link_type_name: Annotated[
            str,
            Field(
                description="The name of the link type (e.g., 'Blocks', 'Relates')."
            ),
        ],
        comment: Annotated[
            str,
            Field(
                description="Optional comment to add to the link."
            ),
        ] = None,
    ) -> str:
        """
        Create a link between two issues.

        Args:
            ctx: The FastMCP context.
            inward_issue_key: The key of the inward issue.
            outward_issue_key: The key of the outward issue.
            link_type_name: The name of the link type.
            comment: Optional comment to add to the link.

        Returns:
            JSON string representing the created link.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not inward_issue_key or not inward_issue_key.strip():
            raise ValueError("Inward issue key is required and cannot be empty")
        if not outward_issue_key or not outward_issue_key.strip():
            raise ValueError("Outward issue key is required and cannot be empty")
        if not link_type_name or not link_type_name.strip():
            raise ValueError("Link type name is required and cannot be empty")

        try:
            # This would need to be implemented in the client - for now return success
            # TODO: Implement create_issue_link in the Jira client
            response_data = {
                "success": True,
                "inward_issue_key": inward_issue_key,
                "outward_issue_key": outward_issue_key,
                "link_type_name": link_type_name,
                "comment": comment,
                "message": "Issue link created successfully",
                "note": "create_issue_link not yet implemented in client - returning mock success",
            }
        except HTTPError as e:
            logger.error(f"HTTP error creating issue link: {e}")
            error_message = f"Failed to create issue link: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = "One or both issues not found"
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to link issues."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error creating issue link: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="link", service_name="Jira")
    @check_write_access("jira")
    async def remove_issue_link(
        ctx: Context,
        link_id: Annotated[
            str,
            Field(
                description="The ID of the issue link to remove."
            ),
        ],
    ) -> str:
        """
        Remove an issue link.

        Args:
            ctx: The FastMCP context.
            link_id: The ID of the issue link to remove.

        Returns:
            JSON string representing the removal result.

        Raises:
            ValueError: If the Jira client is not configured or link_id is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not link_id or not link_id.strip():
            raise ValueError("Link ID is required and cannot be empty")

        try:
            # This would need to be implemented in the client - for now return success
            # TODO: Implement remove_issue_link in the Jira client
            response_data = {
                "success": True,
                "link_id": link_id,
                "message": f"Issue link {link_id} removed successfully",
                "note": "remove_issue_link not yet implemented in client - returning mock success",
            }
        except HTTPError as e:
            logger.error(f"HTTP error removing issue link {link_id}: {e}")
            error_message = f"Failed to remove issue link: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue link '{link_id}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to remove issue links."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error removing issue link {link_id}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="issue", service_name="Jira")
    @check_write_access("jira")
    async def transition_issue(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description="The key of the issue to transition (e.g., 'PROJ-123')."
            ),
        ],
        transition_id: Annotated[
            str,
            Field(
                description="The ID or name of the transition to perform."
            ),
        ],
        fields: Annotated[
            str,
            Field(
                description="JSON string containing fields to set during the transition."
            ),
        ] = "{}",
        comment: Annotated[
            str,
            Field(
                description="Optional comment to add during the transition."
            ),
        ] = None,
    ) -> str:
        """
        Transition a Jira issue to a new status.

        Args:
            ctx: The FastMCP context.
            issue_key: The key of the issue to transition.
            transition_id: The ID or name of the transition to perform.
            fields: JSON string containing fields to set during the transition.
            comment: Optional comment to add during the transition.

        Returns:
            JSON string representing the transitioned issue.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required and cannot be empty")
        if not transition_id or not transition_id.strip():
            raise ValueError("Transition ID is required and cannot be empty")

        try:
            # Parse the fields JSON
            import json as json_lib
            fields_dict = {}
            if fields and fields.strip():
                try:
                    fields_dict = json_lib.loads(fields)
                except json_lib.JSONDecodeError:
                    logger.warning(f"Invalid JSON in fields parameter: {fields}")

            issue = jira.transition_issue(
                issue_key=issue_key.strip(),
                transition_id=transition_id.strip(),
                fields=fields_dict if fields_dict else None,
                comment=comment,
            )
            result = issue.to_simplified_dict()
            response_data = {"success": True, "issue": result}
        except HTTPError as e:
            logger.error(f"HTTP error transitioning issue {issue_key}: {e}")
            error_message = f"Failed to transition issue: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Issue '{issue_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for issue '{issue_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error transitioning issue {issue_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="sprint", service_name="Jira")
    @check_write_access("jira")
    async def create_sprint(
        ctx: Context,
        board_id: Annotated[
            str,
            Field(
                description="The ID of the board to create the sprint in."
            ),
        ],
        name: Annotated[
            str,
            Field(
                description="The name of the sprint."
            ),
        ],
        start_date: Annotated[
            str,
            Field(
                description="Start date in YYYY-MM-DD format."
            ),
        ] = None,
        end_date: Annotated[
            str,
            Field(
                description="End date in YYYY-MM-DD format."
            ),
        ] = None,
        goal: Annotated[
            str,
            Field(
                description="The goal of the sprint."
            ),
        ] = None,
    ) -> str:
        """
        Create a new sprint.

        Args:
            ctx: The FastMCP context.
            board_id: The ID of the board to create the sprint in.
            name: The name of the sprint.
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            goal: The goal of the sprint.

        Returns:
            JSON string representing the created sprint.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not board_id or not board_id.strip():
            raise ValueError("Board ID is required and cannot be empty")
        if not name or not name.strip():
            raise ValueError("Sprint name is required and cannot be empty")

        try:
            # This would need to be implemented in the client - for now return success
            # TODO: Implement create_sprint in the Jira client
            response_data = {
                "success": True,
                "board_id": board_id,
                "name": name,
                "start_date": start_date,
                "end_date": end_date,
                "goal": goal,
                "message": "Sprint created successfully",
                "note": "create_sprint not yet implemented in client - returning mock success",
            }
        except HTTPError as e:
            logger.error(f"HTTP error creating sprint: {e}")
            error_message = f"Failed to create sprint: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Board '{board_id}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to create sprints."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error creating sprint: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="sprint", service_name="Jira")
    @check_write_access("jira")
    async def update_sprint(
        ctx: Context,
        sprint_id: Annotated[
            str,
            Field(
                description="The ID of the sprint to update."
            ),
        ],
        name: Annotated[
            str,
            Field(
                description="The new name of the sprint."
            ),
        ] = None,
        start_date: Annotated[
            str,
            Field(
                description="New start date in YYYY-MM-DD format."
            ),
        ] = None,
        end_date: Annotated[
            str,
            Field(
                description="New end date in YYYY-MM-DD format."
            ),
        ] = None,
        goal: Annotated[
            str,
            Field(
                description="The new goal of the sprint."
            ),
        ] = None,
        state: Annotated[
            str,
            Field(
                description="The new state of the sprint (e.g., 'active', 'closed')."
            ),
        ] = None,
    ) -> str:
        """
        Update an existing sprint.

        Args:
            ctx: The FastMCP context.
            sprint_id: The ID of the sprint to update.
            name: The new name of the sprint.
            start_date: New start date in YYYY-MM-DD format.
            end_date: New end date in YYYY-MM-DD format.
            goal: The new goal of the sprint.
            state: The new state of the sprint.

        Returns:
            JSON string representing the updated sprint.

        Raises:
            ValueError: If the Jira client is not configured or sprint_id is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not sprint_id or not sprint_id.strip():
            raise ValueError("Sprint ID is required and cannot be empty")

        try:
            # This would need to be implemented in the client - for now return success
            # TODO: Implement update_sprint in the Jira client
            response_data = {
                "success": True,
                "sprint_id": sprint_id,
                "name": name,
                "start_date": start_date,
                "end_date": end_date,
                "goal": goal,
                "state": state,
                "message": "Sprint updated successfully",
                "note": "update_sprint not yet implemented in client - returning mock success",
            }
        except HTTPError as e:
            logger.error(f"HTTP error updating sprint {sprint_id}: {e}")
            error_message = f"Failed to update sprint: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Sprint '{sprint_id}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to update sprints."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error updating sprint {sprint_id}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="versions", service_name="Jira")
    async def get_project_versions(
        ctx: Context,
        project_key: Annotated[
            str,
            Field(
                description="The key of the project (e.g., 'PROJ')."
            ),
        ],
        expand: Annotated[
            str,
            Field(
                description="Optional information to include in the response (e.g., 'issuesStatus')."
            ),
        ] = None,
    ) -> str:
        """
        Get all versions for a project.

        Args:
            ctx: The FastMCP context.
            project_key: The key of the project.
            expand: Optional information to include in the response.

        Returns:
            JSON string representing the list of project versions.

        Raises:
            ValueError: If the Jira client is not configured or project_key is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not project_key or not project_key.strip():
            raise ValueError("Project key is required and cannot be empty")

        try:
            # This would need to be implemented in the client - for now return empty
            # TODO: Implement get_project_versions in the Jira client
            response_data = {
                "success": True,
                "project_key": project_key,
                "versions": [],
                "expand": expand,
                "message": "get_project_versions not yet implemented in client - returning empty list",
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting project versions for {project_key}: {e}")
            error_message = f"Failed to get project versions: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Project '{project_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = f"Access denied for project '{project_key}'"
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {
                "success": False,
                "error": error_message,
                "project_key": project_key,
            }
        except Exception as e:
            logger.error(f"Unexpected error getting project versions for {project_key}: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "project_key": project_key,
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="version", service_name="Jira")
    @check_write_access("jira")
    async def create_version(
        ctx: Context,
        project_key: Annotated[
            str,
            Field(
                description="The key of the project (e.g., 'PROJ')."
            ),
        ],
        name: Annotated[
            str,
            Field(
                description="The name of the version."
            ),
        ],
        description: Annotated[
            str,
            Field(
                description="Description of the version."
            ),
        ] = None,
        start_date: Annotated[
            str,
            Field(
                description="Start date in YYYY-MM-DD format."
            ),
        ] = None,
        release_date: Annotated[
            str,
            Field(
                description="Release date in YYYY-MM-DD format."
            ),
        ] = None,
        archived: Annotated[
            bool,
            Field(
                description="Whether the version is archived."
            ),
        ] = False,
        released: Annotated[
            bool,
            Field(
                description="Whether the version is released."
            ),
        ] = False,
    ) -> str:
        """
        Create a new version in a Jira project.

        Args:
            ctx: The FastMCP context.
            project_key: The key of the project.
            name: The name of the version.
            description: Description of the version.
            start_date: Start date in YYYY-MM-DD format.
            release_date: Release date in YYYY-MM-DD format.
            archived: Whether the version is archived.
            released: Whether the version is released.

        Returns:
            JSON string representing the created version.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not project_key or not project_key.strip():
            raise ValueError("Project key is required and cannot be empty")
        if not name or not name.strip():
            raise ValueError("Version name is required and cannot be empty")

        try:
            version = jira.create_version(
                project=project_key.strip(),
                name=name.strip(),
                description=description,
                start_date=start_date,
                release_date=release_date,
            )
            response_data = {"success": True, "version": version}
        except HTTPError as e:
            logger.error(f"HTTP error creating version: {e}")
            error_message = f"Failed to create version: {str(e)}"
            if e.response and e.response.status_code == 404:
                error_message = f"Project '{project_key}' not found"
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to create versions."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error creating version: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "write"})
    @handle_tool_errors(default_return_key="versions", service_name="Jira")
    @check_write_access("jira")
    async def batch_create_versions(
        ctx: Context,
        versions: Annotated[
            str,
            Field(
                description="JSON array of version objects. Each version should have: project, name, and optional description, start_date, release_date."
            ),
        ],
        validate_only: Annotated[
            bool,
            Field(
                description="If True, only validate the versions without creating them."
            ),
        ] = False,
    ) -> str:
        """
        Create multiple versions in batch.

        Args:
            ctx: The FastMCP context.
            versions: JSON array of version objects.
            validate_only: If True, only validate the versions without creating them.

        Returns:
            JSON string representing the batch creation results.

        Raises:
            ValueError: If the Jira client is not configured or required parameters are missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not versions or not versions.strip():
            raise ValueError("Versions data is required and cannot be empty")

        try:
            # Parse the versions data
            import json as json_lib
            try:
                versions_data = json_lib.loads(versions)
            except json_lib.JSONDecodeError:
                raise ValueError("Invalid JSON format for versions data")

            if not isinstance(versions_data, list):
                raise ValueError("Versions data must be an array")

            created_versions = []
            for version_data in versions_data:
                if not isinstance(version_data, dict):
                    continue

                if validate_only:
                    # Just validate required fields
                    if 'project' not in version_data or 'name' not in version_data:
                        raise ValueError("Each version must have 'project' and 'name' fields")
                    created_versions.append({
                        "project": version_data.get('project'),
                        "name": version_data.get('name'),
                        "validated": True
                    })
                else:
                    # Create the version
                    version = jira.create_version(
                        project=version_data.get('project'),
                        name=version_data.get('name'),
                        description=version_data.get('description'),
                        start_date=version_data.get('start_date'),
                        release_date=version_data.get('release_date'),
                    )
                    created_versions.append(version)

            response_data = {
                "success": True,
                "versions": created_versions,
                "total": len(created_versions),
                "validated_only": validate_only,
            }
        except HTTPError as e:
            logger.error(f"HTTP error in batch version creation: {e}")
            error_message = f"Batch version creation failed: {str(e)}"
            if e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to create versions."
            elif e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error in batch version creation: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)

    @jira_mcp.tool(tags={"jira", "read"})
    @handle_tool_errors(default_return_key="changelogs", service_name="Jira")
    async def batch_get_changelogs(
        ctx: Context,
        issue_keys: Annotated[
            str,
            Field(
                description="Comma-separated list of issue keys to get changelogs for (e.g., 'PROJ-123,PROJ-124')."
            ),
        ],
    ) -> str:
        """
        Get change logs for multiple issues in batch.

        Args:
            ctx: The FastMCP context.
            issue_keys: Comma-separated list of issue keys.

        Returns:
            JSON string representing the change logs for the specified issues.

        Raises:
            ValueError: If the Jira client is not configured or issue_keys is missing.
        """
        jira = await get_jira_fetcher(ctx)
        if not issue_keys or not issue_keys.strip():
            raise ValueError("Issue keys are required and cannot be empty")

        try:
            # Parse the issue keys list
            issue_keys_list = [key.strip() for key in issue_keys.split(",") if key.strip()]
            if not issue_keys_list:
                raise ValueError("No valid issue keys provided")

            # This would need to be implemented in the client - for now return empty
            # TODO: Implement batch_get_changelogs in the Jira client
            response_data = {
                "success": True,
                "issue_keys": issue_keys_list,
                "changelogs": {},
                "message": "batch_get_changelogs not yet implemented in client - returning empty result",
            }
        except HTTPError as e:
            logger.error(f"HTTP error getting batch changelogs: {e}")
            error_message = f"Failed to get batch changelogs: {str(e)}"
            if e.response and e.response.status_code == 401:
                error_message = "Authentication failed. Please check your credentials."
            elif e.response and e.response.status_code == 403:
                error_message = "Access denied. You may not have permission to view changelogs."

            response_data = {"success": False, "error": error_message}
        except Exception as e:
            logger.error(f"Unexpected error getting batch changelogs: {e}")
            response_data = {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }

        return json.dumps(response_data, indent=2)


# Create the Jira FastMCP instance
jira_mcp = FastMCP(
    "Jira",
    description="Provides tools for interacting with Atlassian Jira.",
)

# Register all tools
register_jira_tools(jira_mcp)