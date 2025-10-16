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


# Create the Jira FastMCP instance
jira_mcp = FastMCP(
    "Jira",
    description="Provides tools for interacting with Atlassian Jira.",
)

# Register all tools
register_jira_tools(jira_mcp)