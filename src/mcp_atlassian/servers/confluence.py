"""Confluence FastMCP server instance and tool definitions."""

import json
import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import BeforeValidator, Field

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.servers.dependencies import get_confluence_fetcher
from mcp_atlassian.utils.decorators import (
    check_write_access,
)

logger = logging.getLogger(__name__)


def register_confluence_tools(confluence_mcp: FastMCP) -> None:
    @confluence_mcp.tool(tags={"confluence", "read"})
    async def search(
        ctx: Context,
        query: Annotated[
            str,
            Field(
                description=(
                    "Search query - can be either a simple text (e.g. 'project documentation') or a CQL query string. "
                    "Simple queries use 'siteSearch' by default, to mimic the WebUI search, with an automatic fallback "
                    "to 'text' search if not supported. Examples of CQL:\n"
                    "- Basic search: 'type=page AND space=DEV'\n"
                    "- Personal space search: 'space=\"~username\"' (note: personal space keys starting with ~ must be quoted)\n"
                    "- Search by title: 'title~\"Meeting Notes\"'\n"
                    "- Use siteSearch: 'siteSearch ~ \"important concept\"'\n"
                    "- Use text search: 'text ~ \"important concept\"'\n"
                    "- Recent content: 'created >= \"2023-01-01\"'\n"
                    "- Content with specific label: 'label=documentation'\n"
                    "- Recently modified content: 'lastModified > startOfMonth(\"-1M\")'\n"
                    "- Content modified this year: 'creator = currentUser() AND lastModified > startOfYear()'\n"
                    "- Content you contributed to recently: 'contributor = currentUser() AND lastModified > startOfWeek()'\n"
                    "- Content watched by user: 'watcher = \"user@domain.com\" AND type = page'\n"
                    '- Exact phrase in content: \'text ~ "\\"Urgent Review Required\\"" AND label = "pending-approval"\'\n'
                    '- Title wildcards: \'title ~ "Minutes*" AND (space = "HR" OR space = "Marketing")\'\n'
                    'Note: Special identifiers need proper quoting in CQL: personal space keys (e.g., "~username"), '
                    "reserved words, numeric IDs, and identifiers with special characters."
                )
            ),
        ],
        limit: Annotated[
            int,
            Field(
                description="Maximum number of results (1-50)",
                default=10,
                ge=1,
                le=50,
            ),
        ] = 10,
        spaces_filter: Annotated[
            str | None,
            Field(
                description=(
                    "(Optional) Comma-separated list of space keys to filter results by. "
                    "Overrides the environment variable CONFLUENCE_SPACES_FILTER if provided. "
                    "Use empty string to disable filtering."
                ),
                default=None,
            ),
        ] = None,
    ) -> str:
        """Search Confluence content using simple terms or CQL.

        Args:
            ctx: The FastMCP context.
            query: Search query - can be simple text or a CQL query string.
            limit: Maximum number of results (1-50).
            spaces_filter: Comma-separated list of space keys to filter by.

        Returns:
            JSON string representing a list of simplified Confluence page objects.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        # Check if the query is a simple search term or already a CQL query
        if query and not any(
            x in query for x in ["=", "~", ">", "<", " AND ", " OR ", "currentUser()"]
        ):
            original_query = query
            try:
                query = f'siteSearch ~ "{original_query}"'
                logger.info(
                    f"Converting simple search term to CQL using siteSearch: {query}"
                )
                pages = confluence_fetcher.search(
                    query, limit=limit, spaces_filter=spaces_filter
                )
            except Exception as e:
                logger.warning(
                    f"siteSearch failed ('{e}'), falling back to text search."
                )
                query = f'text ~ "{original_query}"'
                logger.info(f"Falling back to text search with CQL: {query}")
                pages = confluence_fetcher.search(
                    query, limit=limit, spaces_filter=spaces_filter
                )
        else:
            pages = confluence_fetcher.search(
                query, limit=limit, spaces_filter=spaces_filter
            )
        search_results = [page.to_simplified_dict() for page in pages]
        return json.dumps(search_results, indent=2, ensure_ascii=False)

    @confluence_mcp.tool(tags={"confluence", "read"})
    async def get_page(
        ctx: Context,
        page_id: Annotated[
            str | None,
            Field(
                description=(
                    "Confluence page ID (numeric ID, can be found in the page URL). "
                    "For example, in the URL 'https://example.atlassian.net/wiki/spaces/TEAM/pages/123456789/Page+Title', "
                    "the page ID is '123456789'. "
                    "Provide this OR both 'title' and 'space_key'. If page_id is provided, title and space_key will be ignored."
                ),
                default=None,
            ),
        ] = None,
        title: Annotated[
            str | None,
            Field(
                description=(
                    "The exact title of the Confluence page. Use this with 'space_key' if 'page_id' is not known."
                ),
                default=None,
            ),
        ] = None,
        space_key: Annotated[
            str | None,
            Field(
                description=(
                    "The key of the Confluence space where the page resides (e.g., 'DEV', 'TEAM'). Required if using 'title'."
                ),
                default=None,
            ),
        ] = None,
        include_metadata: Annotated[
            bool,
            Field(
                description="Whether to include page metadata such as creation date, last update, version, and labels.",
                default=True,
            ),
        ] = True,
        convert_to_markdown: Annotated[
            bool,
            Field(
                description=(
                    "Whether to convert page to markdown (true) or keep it in raw HTML format (false). "
                    "Raw HTML can reveal macros (like dates) not visible in markdown, but CAUTION: "
                    "using HTML significantly increases token usage in AI responses."
                ),
                default=True,
            ),
        ] = True,
    ) -> str:
        """Get content of a specific Confluence page by its ID, or by its title and space key.

        Args:
            ctx: The FastMCP context.
            page_id: Confluence page ID. If provided, 'title' and 'space_key' are ignored.
            title: The exact title of the page. Must be used with 'space_key'.
            space_key: The key of the space. Must be used with 'title'.
            include_metadata: Whether to include page metadata.
            convert_to_markdown: Convert content to markdown (true) or keep raw HTML (false).

        Returns:
            JSON string representing the page content and/or metadata, or an error if not found or parameters are invalid.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        page_object = None

        if page_id:
            if title or space_key:
                logger.warning(
                    "page_id was provided; title and space_key parameters will be ignored."
                )
            try:
                page_object = confluence_fetcher.get_page_content(
                    page_id, convert_to_markdown=convert_to_markdown
                )
            except Exception as e:
                logger.error(f"Error fetching page by ID '{page_id}': {e}")
                return json.dumps(
                    {"error": f"Failed to retrieve page by ID '{page_id}': {e}"},
                    indent=2,
                    ensure_ascii=False,
                )
        elif title and space_key:
            page_object = confluence_fetcher.get_page_by_title(
                space_key, title, convert_to_markdown=convert_to_markdown
            )
            if not page_object:
                return json.dumps(
                    {
                        "error": f"Page with title '{title}' not found in space '{space_key}'."
                    },
                    indent=2,
                    ensure_ascii=False,
                )
        else:
            raise ValueError(
                "Either 'page_id' OR both 'title' and 'space_key' must be provided."
            )

        if not page_object:
            return json.dumps(
                {"error": "Page not found with the provided identifiers."},
                indent=2,
                ensure_ascii=False,
            )

        if include_metadata:
            result = {"metadata": page_object.to_simplified_dict()}
        else:
            result = {"content": {"value": page_object.content}}

        return json.dumps(result, indent=2, ensure_ascii=False)

    @confluence_mcp.tool(tags={"confluence", "read"})
    async def get_page_children(
        ctx: Context,
        parent_id: Annotated[
            str,
            Field(
                description="The ID of the parent page whose children you want to retrieve"
            ),
        ],
        expand: Annotated[
            str,
            Field(
                description="Fields to expand in the response (e.g., 'version', 'body.storage')",
                default="version",
            ),
        ] = "version",
        limit: Annotated[
            int,
            Field(
                description="Maximum number of child pages to return (1-50)",
                default=25,
                ge=1,
                le=50,
            ),
        ] = 25,
        include_content: Annotated[
            bool,
            Field(
                description="Whether to include the page content in the response",
                default=False,
            ),
        ] = False,
        convert_to_markdown: Annotated[
            bool,
            Field(
                description="Whether to convert page content to markdown (true) or keep it in raw HTML format (false). Only relevant if include_content is true.",
                default=True,
            ),
        ] = True,
        start: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based)", default=0, ge=0
            ),
        ] = 0,
    ) -> str:
        """Get child pages of a specific Confluence page.

        Args:
            ctx: The FastMCP context.
            parent_id: The ID of the parent page.
            expand: Fields to expand.
            limit: Maximum number of child pages.
            include_content: Whether to include page content.
            convert_to_markdown: Convert content to markdown if include_content is true.
            start: Starting index for pagination.

        Returns:
            JSON string representing a list of child page objects.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        if include_content and "body" not in expand:
            expand = f"{expand},body.storage" if expand else "body.storage"

        try:
            pages = confluence_fetcher.get_page_children(
                page_id=parent_id,
                start=start,
                limit=limit,
                expand=expand,
                convert_to_markdown=convert_to_markdown,
            )
            child_pages = [page.to_simplified_dict() for page in pages]
            result = {
                "parent_id": parent_id,
                "count": len(child_pages),
                "limit_requested": limit,
                "start_requested": start,
                "results": child_pages,
            }
        except Exception as e:
            logger.error(
                f"Error getting/processing children for page ID {parent_id}: {e}",
                exc_info=True,
            )
            result = {"error": f"Failed to get child pages: {e}"}

        return json.dumps(result, indent=2, ensure_ascii=False)

    @confluence_mcp.tool(tags={"confluence", "read"})
    async def get_comments(
        ctx: Context,
        page_id: Annotated[
            str,
            Field(
                description=(
                    "Confluence page ID (numeric ID, can be parsed from URL, "
                    "e.g. from 'https://example.atlassian.net/wiki/spaces/TEAM/pages/123456789/Page+Title' "
                    "-> '123456789')"
                )
            ),
        ],
    ) -> str:
        """Get comments for a specific Confluence page.

        Args:
            ctx: The FastMCP context.
            page_id: Confluence page ID.

        Returns:
            JSON string representing a list of comment objects.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        comments = confluence_fetcher.get_page_comments(page_id)
        formatted_comments = [comment.to_simplified_dict() for comment in comments]
        return json.dumps(formatted_comments, indent=2, ensure_ascii=False)

    @confluence_mcp.tool(tags={"confluence", "read"})
    async def get_labels(
        ctx: Context,
        page_id: Annotated[
            str,
            Field(
                description=(
                    "Confluence page ID (numeric ID, can be parsed from URL, "
                    "e.g. from 'https://example.atlassian.net/wiki/spaces/TEAM/pages/123456789/Page+Title' "
                    "-> '123456789')"
                )
            ),
        ],
    ) -> str:
        """Get labels for a specific Confluence page.

        Args:
            ctx: The FastMCP context.
            page_id: Confluence page ID.

        Returns:
            JSON string representing a list of label objects.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        labels = confluence_fetcher.get_page_labels(page_id)
        formatted_labels = [label.to_simplified_dict() for label in labels]
        return json.dumps(formatted_labels, indent=2, ensure_ascii=False)

    @confluence_mcp.tool(tags={"confluence", "write"})
    @check_write_access("confluence")
    async def add_label(
        ctx: Context,
        page_id: Annotated[str, Field(description="The ID of the page to update")],
        name: Annotated[str, Field(description="The name of the label")],
    ) -> str:
        """Add label to an existing Confluence page.

        Args:
            ctx: The FastMCP context.
            page_id: The ID of the page to update.
            name: The name of the label.

        Returns:
            JSON string representing the updated list of label objects for the page.

        Raises:
            ValueError: If in read-only mode or Confluence client is unavailable.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        labels = confluence_fetcher.add_page_label(page_id, name)
        formatted_labels = [label.to_simplified_dict() for label in labels]
        return json.dumps(formatted_labels, indent=2, ensure_ascii=False)

    @confluence_mcp.tool(tags={"confluence", "write"})
    @check_write_access("confluence")
    async def create_page(
        ctx: Context,
        space_key: Annotated[
            str,
            Field(
                description="The key of the space to create the page in (usually a short uppercase code like 'DEV', 'TEAM', or 'DOC')"
            ),
        ],
        title: Annotated[str, Field(description="The title of the page")],
        content: Annotated[
            str,
            Field(
                description="The content of the page. Format depends on content_format parameter. Can be Markdown (default), wiki markup, or storage format"
            ),
        ],
        parent_id: Annotated[
            str | None,
            Field(
                description="(Optional) parent page ID. If provided, this page will be created as a child of the specified page",
                default=None,
            ),
            BeforeValidator(lambda x: str(x) if x is not None else None),
        ] = None,
        content_format: Annotated[
            str,
            Field(
                description="(Optional) The format of the content parameter. Options: 'markdown' (default), 'wiki', or 'storage'. Wiki format uses Confluence wiki markup syntax",
                default="markdown",
            ),
        ] = "markdown",
        enable_heading_anchors: Annotated[
            bool,
            Field(
                description="(Optional) Whether to enable automatic heading anchor generation. Only applies when content_format is 'markdown'",
                default=False,
            ),
        ] = False,
    ) -> str:
        """Create a new Confluence page.

        Args:
            ctx: The FastMCP context.
            space_key: The key of the space.
            title: The title of the page.
            content: The content of the page (format depends on content_format).
            parent_id: Optional parent page ID.
            content_format: The format of the content ('markdown', 'wiki', or 'storage').
            enable_heading_anchors: Whether to enable heading anchors (markdown only).

        Returns:
            JSON string representing the created page object.

        Raises:
            ValueError: If in read-only mode, Confluence client is unavailable, or invalid content_format.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)

        # Validate content_format
        if content_format not in ["markdown", "wiki", "storage"]:
            raise ValueError(
                f"Invalid content_format: {content_format}. Must be 'markdown', 'wiki', or 'storage'"
            )

        # Determine parameters based on content format
        if content_format == "markdown":
            is_markdown = True
            content_representation = None  # Will be converted to storage
        else:
            is_markdown = False
            content_representation = content_format  # Pass 'wiki' or 'storage' directly

        page = confluence_fetcher.create_page(
            space_key=space_key,
            title=title,
            body=content,
            parent_id=parent_id,
            is_markdown=is_markdown,
            enable_heading_anchors=enable_heading_anchors
            if content_format == "markdown"
            else False,
            content_representation=content_representation,
        )
        result = page.to_simplified_dict()
        return json.dumps(
            {"message": "Page created successfully", "page": result},
            indent=2,
            ensure_ascii=False,
        )

    @confluence_mcp.tool(tags={"confluence", "write"})
    @check_write_access("confluence")
    async def update_page(
        ctx: Context,
        page_id: Annotated[str, Field(description="The ID of the page to update")],
        title: Annotated[str, Field(description="The new title of the page")],
        content: Annotated[
            str,
            Field(
                description="The new content of the page. Format depends on content_format parameter"
            ),
        ],
        is_minor_edit: Annotated[
            bool, Field(description="Whether this is a minor edit", default=False)
        ] = False,
        version_comment: Annotated[
            str | None,
            Field(description="Optional comment for this version", default=None),
        ] = None,
        parent_id: Annotated[
            str | None,
            Field(description="Optional the new parent page ID", default=None),
            BeforeValidator(lambda x: str(x) if x is not None else None),
        ] = None,
        content_format: Annotated[
            str,
            Field(
                description="(Optional) The format of the content parameter. Options: 'markdown' (default), 'wiki', or 'storage'. Wiki format uses Confluence wiki markup syntax",
                default="markdown",
            ),
        ] = "markdown",
        enable_heading_anchors: Annotated[
            bool,
            Field(
                description="(Optional) Whether to enable automatic heading anchor generation. Only applies when content_format is 'markdown'",
                default=False,
            ),
        ] = False,
    ) -> str:
        """Update an existing Confluence page.

        Args:
            ctx: The FastMCP context.
            page_id: The ID of the page to update.
            title: The new title of the page.
            content: The new content of the page (format depends on content_format).
            is_minor_edit: Whether this is a minor edit.
            version_comment: Optional comment for this version.
            parent_id: Optional new parent page ID.
            content_format: The format of the content ('markdown', 'wiki', or 'storage').
            enable_heading_anchors: Whether to enable heading anchors (markdown only).

        Returns:
            JSON string representing the updated page object.

        Raises:
            ValueError: If Confluence client is not configured, available, or invalid content_format.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)

        # Validate content_format
        if content_format not in ["markdown", "wiki", "storage"]:
            raise ValueError(
                f"Invalid content_format: {content_format}. Must be 'markdown', 'wiki', or 'storage'"
            )

        # Determine parameters based on content format
        if content_format == "markdown":
            is_markdown = True
            content_representation = None  # Will be converted to storage
        else:
            is_markdown = False
            content_representation = content_format  # Pass 'wiki' or 'storage' directly

        updated_page = confluence_fetcher.update_page(
            page_id=page_id,
            title=title,
            body=content,
            is_minor_edit=is_minor_edit,
            version_comment=version_comment,
            is_markdown=is_markdown,
            parent_id=parent_id,
            enable_heading_anchors=enable_heading_anchors
            if content_format == "markdown"
            else False,
            content_representation=content_representation,
        )
        page_data = updated_page.to_simplified_dict()
        return json.dumps(
            {"message": "Page updated successfully", "page": page_data},
            indent=2,
            ensure_ascii=False,
        )

    @confluence_mcp.tool(tags={"confluence", "write"})
    @check_write_access("confluence")
    async def delete_page(
        ctx: Context,
        page_id: Annotated[str, Field(description="The ID of the page to delete")],
    ) -> str:
        """Delete an existing Confluence page.

        Args:
            ctx: The FastMCP context.
            page_id: The ID of the page to delete.

        Returns:
            JSON string indicating success or failure.

        Raises:
            ValueError: If Confluence client is not configured or available.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        try:
            result = confluence_fetcher.delete_page(page_id=page_id)
            if result:
                response = {
                    "success": True,
                    "message": f"Page {page_id} deleted successfully",
                }
            else:
                response = {
                    "success": False,
                    "message": f"Unable to delete page {page_id}. API request completed but deletion unsuccessful.",
                }
        except Exception as e:
            logger.error(f"Error deleting Confluence page {page_id}: {str(e)}")
            response = {
                "success": False,
                "message": f"Error deleting page {page_id}",
                "error": str(e),
            }

        return json.dumps(response, indent=2, ensure_ascii=False)

    @confluence_mcp.tool(tags={"confluence", "write"})
    @check_write_access("confluence")
    async def add_comment(
        ctx: Context,
        page_id: Annotated[
            str, Field(description="The ID of the page to add a comment to")
        ],
        content: Annotated[
            str, Field(description="The comment content in Markdown format")
        ],
    ) -> str:
        """Add a comment to a Confluence page.

        Args:
            ctx: The FastMCP context.
            page_id: The ID of the page to add a comment to.
            content: The comment content in Markdown format.

        Returns:
            JSON string representing the created comment.

        Raises:
            ValueError: If in read-only mode or Confluence client is unavailable.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        try:
            comment = confluence_fetcher.add_comment(page_id=page_id, content=content)
            if comment:
                comment_data = comment.to_simplified_dict()
                response = {
                    "success": True,
                    "message": "Comment added successfully",
                    "comment": comment_data,
                }
            else:
                response = {
                    "success": False,
                    "message": f"Unable to add comment to page {page_id}. API request completed but comment creation unsuccessful.",
                }
        except Exception as e:
            logger.error(f"Error adding comment to Confluence page {page_id}: {str(e)}")
            response = {
                "success": False,
                "message": f"Error adding comment to page {page_id}",
                "error": str(e),
            }

        return json.dumps(response, indent=2, ensure_ascii=False)

    @confluence_mcp.tool(tags={"confluence", "read"})
    async def search_user(
        ctx: Context,
        query: Annotated[
            str,
            Field(
                description=(
                    "Search query - a CQL query string for user search. "
                    "Examples of CQL:\n"
                    "- Basic user lookup by full name: 'user.fullname ~ \"First Last\"'\n"
                    'Note: Special identifiers need proper quoting in CQL: personal space keys (e.g., "~username"), '
                    "reserved words, numeric IDs, and identifiers with special characters."
                )
            ),
        ],
        limit: Annotated[
            int,
            Field(
                description="Maximum number of results (1-50)",
                default=10,
                ge=1,
                le=50,
            ),
        ] = 10,
    ) -> str:
        """Search Confluence users using CQL.

        Args:
            ctx: The FastMCP context.
            query: Search query - a CQL query string for user search.
            limit: Maximum number of results (1-50).

        Returns:
            JSON string representing a list of simplified Confluence user search result objects.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)

        # If the query doesn't look like CQL, wrap it as a user fullname search
        if query and not any(
            x in query for x in ["=", "~", ">", "<", " AND ", " OR ", "user."]
        ):
            # Simple search term - search by fullname
            query = f'user.fullname ~ "{query}"'
            logger.info(f"Converting simple search term to user CQL: {query}")

        try:
            user_results = confluence_fetcher.search_user(query, limit=limit)
            search_results = [user.to_simplified_dict() for user in user_results]
            return json.dumps(search_results, indent=2, ensure_ascii=False)
        except MCPAtlassianAuthenticationError as e:
            logger.error(
                f"Authentication error during user search: {e}", exc_info=False
            )
            return json.dumps(
                {
                    "error": "Authentication failed. Please check your credentials.",
                    "details": str(e),
                },
                indent=2,
                ensure_ascii=False,
            )
        except Exception as e:
            logger.error(f"Error searching users: {str(e)}")
            return json.dumps(
                {
                    "error": f"An unexpected error occurred while searching for users: {str(e)}"
                },
                indent=2,
                ensure_ascii=False,
            )

    @confluence_mcp.tool(tags={"confluence", "read"})
    async def get_user_details(
        ctx: Context,
        identifier: Annotated[
            str,
            Field(
                description=(
                    "User identifier - can be accountId, username, or userkey. "
                    "For Cloud instances, use accountId. For Server/DC, use username or userkey."
                )
            ),
        ],
        identifier_type: Annotated[
            str,
            Field(
                description=(
                    "Type of identifier provided. Options: 'accountid', 'username', 'userkey'. "
                    "Default is 'accountid' for Cloud instances."
                ),
                default="accountid",
            ),
        ] = "accountid",
    ) -> str:
        """Get detailed user information by identifier.

        Args:
            ctx: The FastMCP context.
            identifier: The user identifier (accountId, username, or userkey).
            identifier_type: Type of identifier ('accountid', 'username', 'userkey').

        Returns:
            JSON string representing detailed user information.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        try:
            user_details = confluence_fetcher.get_user_details(identifier, identifier_type)
            if user_details:
                return json.dumps(
                    {
                        "success": True,
                        "user": user_details.to_simplified_dict() if hasattr(user_details, 'to_simplified_dict') else user_details
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            else:
                return json.dumps(
                    {
                        "success": False,
                        "message": f"User not found with {identifier_type}: {identifier}"
                    },
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.error(f"Error getting user details: {str(e)}")
            return json.dumps(
                {
                    "success": False,
                    "message": f"Error getting user details: {str(e)}",
                    "error": str(e),
                },
                indent=2,
                ensure_ascii=False,
            )

    @confluence_mcp.tool(tags={"confluence", "read"})
    async def list_page_versions(
        ctx: Context,
        page_id: Annotated[
            str,
            Field(
                description=(
                    "Confluence page ID (numeric ID, can be parsed from URL, "
                    "e.g. from 'https://example.atlassian.net/wiki/spaces/TEAM/pages/123456789/Page+Title' "
                    "-> '123456789')"
                )
            ),
        ],
        limit: Annotated[
            int,
            Field(
                description="Maximum number of versions to return (1-50)",
                default=25,
                ge=1,
                le=50,
            ),
        ] = 25,
        start: Annotated[
            int,
            Field(
                description="Starting index for pagination (0-based)",
                default=0,
                ge=0,
            ),
        ] = 0,
        expand: Annotated[
            str,
            Field(
                description="Fields to expand in the response (e.g., 'content', 'message')",
                default="content",
            ),
        ] = "content",
    ) -> str:
        """List all versions of a Confluence page.

        Args:
            ctx: The FastMCP context.
            page_id: Confluence page ID.
            limit: Maximum number of versions to return.
            start: Starting index for pagination.
            expand: Fields to expand in the response.

        Returns:
            JSON string representing a list of page version objects.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        try:
            versions = confluence_fetcher.get_page_versions(
                page_id=page_id,
                start=start,
                limit=limit,
                expand=expand
            )
            version_list = [version.to_simplified_dict() for version in versions]
            return json.dumps(
                {
                    "page_id": page_id,
                    "count": len(version_list),
                    "limit_requested": limit,
                    "start_requested": start,
                    "results": version_list,
                },
                indent=2,
                ensure_ascii=False,
            )
        except Exception as e:
            logger.error(f"Error getting page versions for {page_id}: {str(e)}")
            return json.dumps(
                {
                    "error": f"Failed to get page versions: {str(e)}",
                    "page_id": page_id,
                },
                indent=2,
                ensure_ascii=False,
            )

    @confluence_mcp.tool(tags={"confluence", "read"})
    async def get_page_version(
        ctx: Context,
        page_id: Annotated[
            str,
            Field(
                description=(
                    "Confluence page ID (numeric ID, can be parsed from URL, "
                    "e.g. from 'https://example.atlassian.net/wiki/spaces/TEAM/pages/123456789/Page+Title' "
                    "-> '123456789')"
                )
            ),
        ],
        version_number: Annotated[
            int,
            Field(
                description="The specific version number to retrieve",
                ge=1,
            ),
        ],
        expand: Annotated[
            str,
            Field(
                description="Fields to expand in the response (e.g., 'content', 'message')",
                default="content",
            ),
        ] = "content",
        convert_to_markdown: Annotated[
            bool,
            Field(
                description="Whether to convert page content to markdown (true) or keep it in raw HTML format (false)",
                default=True,
            ),
        ] = True,
    ) -> str:
        """Get a specific version of a Confluence page.

        Args:
            ctx: The FastMCP context.
            page_id: Confluence page ID.
            version_number: The specific version number to retrieve.
            expand: Fields to expand in the response.
            convert_to_markdown: Convert content to markdown (true) or keep raw HTML (false).

        Returns:
            JSON string representing the page version object.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        try:
            version = confluence_fetcher.get_page_version(
                page_id=page_id,
                version_number=version_number,
                expand=expand,
                convert_to_markdown=convert_to_markdown
            )
            if version:
                return json.dumps(
                    {
                        "success": True,
                        "page_id": page_id,
                        "version_number": version_number,
                        "version": version.to_simplified_dict() if hasattr(version, 'to_simplified_dict') else version
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            else:
                return json.dumps(
                    {
                        "success": False,
                        "message": f"Version {version_number} not found for page {page_id}",
                        "page_id": page_id,
                        "version_number": version_number,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.error(f"Error getting page version {version_number} for {page_id}: {str(e)}")
            return json.dumps(
                {
                    "success": False,
                    "message": f"Failed to get page version: {str(e)}",
                    "page_id": page_id,
                    "version_number": version_number,
                    "error": str(e),
                },
                indent=2,
                ensure_ascii=False,
            )

    @confluence_mcp.tool(tags={"confluence", "write"})
    @check_write_access("confluence")
    async def move_page(
        ctx: Context,
        page_id: Annotated[
            str,
            Field(
                description=(
                    "Confluence page ID (numeric ID, can be parsed from URL, "
                    "e.g. from 'https://example.atlassian.net/wiki/spaces/TEAM/pages/123456789/Page+Title' "
                    "-> '123456789')"
                )
            ),
        ],
        target_space_key: Annotated[
            str | None,
            Field(
                description=(
                    "(Optional) Target space key where the page should be moved. "
                    "If not provided, the page will be moved within the same space."
                ),
                default=None,
            ),
        ] = None,
        target_parent_page_id: Annotated[
            str | None,
            Field(
                description=(
                    "(Optional) Target parent page ID. If provided, the page will become a child of this page. "
                    "If not provided, the page will be moved to the root of the target space."
                ),
                default=None,
            ),
        ] = None,
        position: Annotated[
            str,
            Field(
                description=(
                    "Position of the page relative to siblings. Options: 'append', 'before', 'after'. "
                    "Default is 'append' which adds it as the last child."
                ),
                default="append",
            ),
        ] = "append",
    ) -> str:
        """Move a Confluence page to a different parent and/or space.

        Args:
            ctx: The FastMCP context.
            page_id: Confluence page ID to move.
            target_space_key: Optional target space key.
            target_parent_page_id: Optional target parent page ID.
            position: Position relative to siblings ('append', 'before', 'after').

        Returns:
            JSON string indicating success or failure with the updated page information.
        """
        confluence_fetcher = await get_confluence_fetcher(ctx)
        try:
            # Validate position
            if position not in ["append", "before", "after"]:
                raise ValueError(f"Invalid position: {position}. Must be 'append', 'before', or 'after'")

            # Perform the move operation
            result = confluence_fetcher.move_page(
                page_id=page_id,
                target_space_key=target_space_key,
                target_parent_page_id=target_parent_page_id,
                position=position
            )

            if result:
                # Get the updated page information
                updated_page = confluence_fetcher.get_page_content(page_id, convert_to_markdown=False)
                return json.dumps(
                    {
                        "success": True,
                        "message": f"Page {page_id} moved successfully",
                        "page_id": page_id,
                        "target_space_key": target_space_key,
                        "target_parent_page_id": target_parent_page_id,
                        "position": position,
                        "updated_page": updated_page.to_simplified_dict() if updated_page else None,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            else:
                return json.dumps(
                    {
                        "success": False,
                        "message": f"Unable to move page {page_id}. API request completed but move operation unsuccessful.",
                        "page_id": page_id,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.error(f"Error moving Confluence page {page_id}: {str(e)}")
            return json.dumps(
                {
                    "success": False,
                    "message": f"Error moving page {page_id}",
                    "page_id": page_id,
                    "error": str(e),
                },
                indent=2,
                ensure_ascii=False,
            )


# Create the Confluence FastMCP instance
confluence_mcp = FastMCP(
    name="Confluence",
    description="Provides tools for interacting with Atlassian Confluence.",
)

# Register all tools
register_confluence_tools(confluence_mcp)
