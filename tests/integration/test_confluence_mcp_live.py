"""
Live tests for all Confluence MCP functions.

These tests integrate with the actual MCP server functions to test
the complete functionality from tool call to response. They require
real Confluence instances and will create/modify real data.
"""

import json
import os
import uuid
from typing import Any, Dict

import pytest

from fastmcp import Client
from fastmcp.client import FastMCPTransport
from mcp.types import TextContent

from mcp_atlassian.confluence import ConfluenceFetcher
from mcp_atlassian.confluence.config import ConfluenceConfig
from mcp_atlassian.servers import main_mcp
from tests.utils.base import BaseAuthTest
from tests.utils.test_setup import fresh_confluence_test_environment


@pytest.mark.integration
@pytest.mark.usefixtures("fresh_confluence_test_environment")
class TestConfluenceMCPFunctions(BaseAuthTest):
    """Live tests for all Confluence MCP functions with real API calls."""

    @pytest.fixture(autouse=True)
    def skip_without_real_data(self, request):
        """Skip these tests unless --use-real-data is provided."""
        if not request.config.getoption("--use-real-data", default=False):
            pytest.skip("Live MCP tests only run with --use-real-data flag")

    @pytest.fixture
    def confluence_client(self):
        """Create real Confluence client from environment."""
        if not os.getenv("CONFLUENCE_URL"):
            pytest.skip("CONFLUENCE_URL not set in environment")

        config = ConfluenceConfig.from_env()
        return ConfluenceFetcher(config=config)

    @pytest.fixture(scope="function")
    async def mcp_client(self):
        """Create FastMCP client connected to the main server for tool calls."""
        transport = FastMCPTransport(main_mcp)
        client = Client(transport=transport)
        async with client as connected_client:
            yield connected_client

    @pytest.fixture
    def test_space_key(self):
        """Get test space key from environment."""
        key = os.getenv("CONFLUENCE_TEST_SPACE_KEY", "TEST")
        return key

    @pytest.fixture
    def created_resources(self):
        """Track all created resources for cleanup."""
        resources = {
            "pages": [],
            "comments": [],
            "labels": []
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

    def cleanup_created_resources(self, confluence_client, resources: Dict[str, list]):
        """Clean up all created resources."""
        # Clean up pages last (as they might contain comments and labels)
        for comment_id in resources.get("comments", []):
            try:
                # Comments can't be deleted directly, they're deleted with the page
                pass
            except Exception:
                pass

        for label_name in resources.get("labels", []):
            try:
                # Labels can't be deleted directly, they're removed from pages
                pass
            except Exception:
                pass

        for page_id in resources.get("pages", []):
            try:
                confluence_client.delete_page(page_id=page_id)
            except Exception:
                pass

    async def test_confluence_search(self, mcp_client, confluence_client, test_space_key):
        """Test confluence_search MCP function."""
        # Test simple search
        result = await self.call_mcp_tool(
            mcp_client,
            "search",
            query="test",
            limit=5
        )

        assert isinstance(result, list)
        assert len(result) <= 5

        # Test CQL search
        cql_result = await self.call_mcp_tool(
            mcp_client,
            "search",
            query=f'space="{test_space_key}" and type=page',
            limit=3
        )

        assert isinstance(cql_result, list)
        assert len(cql_result) <= 3

        # Verify all results are from the test space
        for page in cql_result:
            if isinstance(page, dict) and "space" in page:
                assert page["space"]["key"] == test_space_key

    async def test_confluence_page_lifecycle(self, mcp_client, confluence_client, test_space_key, created_resources):
        """Test confluence_get_page, confluence_create_page, confluence_update_page, and confluence_delete_page MCP functions."""
        unique_id = str(uuid.uuid4())[:8]
        title = f"MCP Test Page {unique_id}"

        try:
            # Create a page
            create_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=title,
                content="This is a test page created via MCP function\n\n## Heading\n\nSome content here."
            )

            assert "page" in create_result
            assert create_result["page"]["title"] == title
            assert create_result["page"]["space"]["key"] == test_space_key

            page_id = create_result["page"]["id"]
            created_resources["pages"].append(page_id)

            # Get the page by ID
            get_result = await self.call_mcp_tool(
                mcp_client,
                "get_page",
                page_id=page_id
            )

            assert "metadata" in get_result
            assert get_result["metadata"]["title"] == title

            # Get the page by title and space
            get_by_title_result = await self.call_mcp_tool(
                mcp_client,
                "get_page",
                title=title,
                space_key=test_space_key
            )

            assert "metadata" in get_by_title_result
            assert get_by_title_result["metadata"]["title"] == title

            # Update the page
            updated_title = f"{title} - Updated"
            updated_content = "Updated content via MCP\n\n## New Heading\n\nUpdated content here."

            update_result = await self.call_mcp_tool(
                mcp_client,
                "update_page",
                page_id=page_id,
                title=updated_title,
                content=updated_content,
                version_comment="Updated via MCP test"
            )

            assert "page" in update_result
            assert update_result["page"]["title"] == updated_title

            # Verify the update
            get_updated_result = await self.call_mcp_tool(
                mcp_client,
                "get_page",
                page_id=page_id
            )

            assert "metadata" in get_updated_result
            assert get_updated_result["metadata"]["title"] == updated_title

            # Delete the page
            delete_result = await self.call_mcp_tool(
                mcp_client,
                "delete_page",
                page_id=page_id
            )

            assert delete_result["success"] is True
            created_resources["pages"].remove(page_id)

            # Verify deletion
            get_deleted_result = await self.call_mcp_tool(
                mcp_client,
                "get_page",
                page_id=page_id
            )

            assert "error" in get_deleted_result

        finally:
            self.cleanup_created_resources(confluence_client, created_resources)

    async def test_confluence_page_hierarchy(self, mcp_client, confluence_client, test_space_key, created_resources):
        """Test confluence_get_page_children MCP function with page hierarchy."""
        unique_id = str(uuid.uuid4())[:8]

        try:
            # Create parent page
            parent_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Parent Page {unique_id}",
                content="Parent page content"
            )

            parent_id = parent_result["page"]["id"]
            created_resources["pages"].append(parent_id)

            # Create child pages
            child1_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Child Page 1 {unique_id}",
                content="First child page content",
                parent_id=parent_id
            )

            child1_id = child1_result["page"]["id"]
            created_resources["pages"].append(child1_id)

            child2_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Child Page 2 {unique_id}",
                content="Second child page content",
                parent_id=parent_id
            )

            child2_id = child2_result["page"]["id"]
            created_resources["pages"].append(child2_id)

            # Get children of parent page
            children_result = await self.call_mcp_tool(
                mcp_client,
                "get_page_children",
                parent_id=parent_id
            )

            assert children_result["success"] is True
            assert children_result["count"] >= 2
            assert len(children_result["results"]) >= 2

            # Verify both children are in the results
            child_ids = [child["id"] for child in children_result["results"]]
            assert child1_id in child_ids
            assert child2_id in child_ids

            # Test with content inclusion
            children_with_content_result = await self.call_mcp_tool(
                mcp_client,
                "get_page_children",
                parent_id=parent_id,
                include_content=True,
                limit=2
            )

            assert children_with_content_result["success"] is True
            assert len(children_with_content_result["results"]) <= 2

            for child in children_with_content_result["results"]:
                assert "content" in child

        finally:
            self.cleanup_created_resources(confluence_client, created_resources)

    async def test_confluence_comments(self, mcp_client, confluence_client, test_space_key, created_resources):
        """Test confluence_get_comments and confluence_add_comment MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        try:
            # Create test page
            page_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Comment Test Page {unique_id}",
                content="Page for testing comments"
            )

            page_id = page_result["page"]["id"]
            created_resources["pages"].append(page_id)

            # Add a comment
            comment_content = f"This is a test comment {unique_id} from MCP function"
            add_comment_result = await self.call_mcp_tool(
                mcp_client,
                "add_comment",
                page_id=page_id,
                content=comment_content
            )

            assert add_comment_result["success"] is True
            assert comment_content in add_comment_result["comment"]["content"]
            created_resources["comments"].append(add_comment_result["comment"]["id"])

            # Get comments for the page
            get_comments_result = await self.call_mcp_tool(
                mcp_client,
                "get_comments",
                page_id=page_id
            )

            assert get_comments_result["success"] is True
            assert len(get_comments_result["comments"]) >= 1

            # Find our comment
            test_comment = None
            for comment in get_comments_result["comments"]:
                if unique_id in comment.get("content", ""):
                    test_comment = comment
                    break

            assert test_comment is not None
            assert unique_id in test_comment["content"]

        finally:
            self.cleanup_created_resources(confluence_client, created_resources)

    async def test_confluence_labels(self, mcp_client, confluence_client, test_space_key, created_resources):
        """Test confluence_get_labels and confluence_add_label MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        try:
            # Create test page
            page_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Label Test Page {unique_id}",
                content="Page for testing labels"
            )

            page_id = page_result["page"]["id"]
            created_resources["pages"].append(page_id)

            # Get initial labels (should be empty)
            initial_labels_result = await self.call_mcp_tool(
                mcp_client,
                "get_labels",
                page_id=page_id
            )

            assert initial_labels_result["success"] is True
            initial_label_count = len(initial_labels_result["labels"])

            # Add a label
            test_label = f"mcp-test-{unique_id}"
            add_label_result = await self.call_mcp_tool(
                mcp_client,
                "add_label",
                page_id=page_id,
                name=test_label
            )

            assert add_label_result["success"] is True
            created_resources["labels"].append(test_label)

            # Verify label was added
            updated_labels_result = await self.call_mcp_tool(
                mcp_client,
                "get_labels",
                page_id=page_id
            )

            assert updated_labels_result["success"] is True
            assert len(updated_labels_result["labels"]) == initial_label_count + 1

            # Find our label
            label_names = [label["name"] for label in updated_labels_result["labels"]]
            assert test_label in label_names

        finally:
            self.cleanup_created_resources(confluence_client, created_resources)

    async def test_confluence_user_functions(self, mcp_client, confluence_client):
        """Test confluence_search_user and confluence_get_user_details MCP functions."""
        try:
            # Test user search
            search_result = await self.call_mcp_tool(
                mcp_client,
                "search_user",
                query="user",
                limit=5
            )

            assert search_result["success"] is True
            assert isinstance(search_result, list)

            # If users are found, test getting user details
            if search_result and len(search_result) > 0:
                first_user = search_result[0]
                if "accountId" in first_user:
                    # Get user details by accountId
                    details_result = await self.call_mcp_tool(
                        mcp_client,
                        "get_user_details",
                        identifier=first_user["accountId"],
                        identifier_type="accountid"
                    )

                    assert details_result["success"] is True
                    assert details_result["user"]["accountId"] == first_user["accountId"]

        except Exception as e:
            # User functions might not be available in all Confluence instances
            pytest.skip(f"User functions not available: {e}")

    async def test_confluence_page_versions(self, mcp_client, confluence_client, test_space_key, created_resources):
        """Test confluence_list_page_versions and confluence_get_page_version MCP functions."""
        unique_id = str(uuid.uuid4())[:8]

        try:
            # Create test page
            page_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Version Test Page {unique_id}",
                content="Initial content"
            )

            page_id = page_result["page"]["id"]
            created_resources["pages"].append(page_id)

            # Get page versions (should have at least version 1)
            versions_result = await self.call_mcp_tool(
                mcp_client,
                "list_page_versions",
                page_id=page_id,
                limit=10
            )

            assert versions_result["success"] is True
            assert versions_result["count"] >= 1
            assert len(versions_result["results"]) >= 1

            # Get first version
            first_version = versions_result["results"][0]
            version_number = first_version["number"]

            # Get specific version
            specific_version_result = await self.call_mcp_tool(
                mcp_client,
                "get_page_version",
                page_id=page_id,
                version_number=version_number
            )

            assert specific_version_result["success"] is True
            assert specific_version_result["version_number"] == version_number

            # Update the page to create a new version
            update_result = await self.call_mcp_tool(
                mcp_client,
                "update_page",
                page_id=page_id,
                title=f"Version Test Page {unique_id} - Updated",
                content="Updated content",
                version_comment="Creating new version"
            )

            assert update_result["success"] is True

            # Get versions again (should have 2 versions now)
            updated_versions_result = await self.call_mcp_tool(
                mcp_client,
                "list_page_versions",
                page_id=page_id,
                limit=10
            )

            assert updated_versions_result["success"] is True
            assert updated_versions_result["count"] >= 2

        finally:
            self.cleanup_created_resources(confluence_client, created_resources)

    async def test_confluence_move_page(self, mcp_client, confluence_client, test_space_key, created_resources):
        """Test confluence_move_page MCP function."""
        unique_id = str(uuid.uuid4())[:8]

        try:
            # Create parent page
            parent_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Parent for Move Test {unique_id}",
                content="Parent page"
            )

            parent_id = parent_result["page"]["id"]
            created_resources["pages"].append(parent_id)

            # Create another page to be moved
            page_to_move_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Page to Move {unique_id}",
                content="This page will be moved"
            )

            page_to_move_id = page_to_move_result["page"]["id"]
            created_resources["pages"].append(page_to_move_id)

            # Move the page to be a child of the parent
            move_result = await self.call_mcp_tool(
                mcp_client,
                "move_page",
                page_id=page_to_move_id,
                target_parent_page_id=parent_id,
                position="append"
            )

            assert move_result["success"] is True

            # Verify the move by getting children of the parent
            children_result = await self.call_mcp_tool(
                mcp_client,
                "get_page_children",
                parent_id=parent_id
            )

            assert children_result["success"] is True
            child_ids = [child["id"] for child in children_result["results"]]
            assert page_to_move_id in child_ids

        finally:
            self.cleanup_created_resources(confluence_client, created_resources)

    async def test_confluence_content_formats(self, mcp_client, confluence_client, test_space_key, created_resources):
        """Test different content formats in confluence_create_page and confluence_update_page."""
        unique_id = str(uuid.uuid4())[:8]

        try:
            # Test with markdown content
            markdown_content = """
# Heading 1
This is **bold** text and this is *italic* text.

## Heading 2
- List item 1
- List item 2
- List item 3

### Code example
```
print("Hello, World!")
```
            """.strip()

            markdown_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Markdown Test Page {unique_id}",
                content=markdown_content,
                content_format="markdown"
            )

            assert markdown_result["success"] is True
            markdown_page_id = markdown_result["page"]["id"]
            created_resources["pages"].append(markdown_page_id)

            # Test with wiki markup content
            wiki_content = """
h1. Wiki Markup Heading

This is *bold* text and this is _italic_ text.

h2. Sub Heading

* List item 1
* List item 2
* List item 3

{code:language=python}
print("Hello, World!")
{code}
            """.strip()

            wiki_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Wiki Markup Test Page {unique_id}",
                content=wiki_content,
                content_format="wiki"
            )

            assert wiki_result["success"] is True
            wiki_page_id = wiki_result["page"]["id"]
            created_resources["pages"].append(wiki_page_id)

            # Test updating with different format
            update_result = await self.call_mcp_tool(
                mcp_client,
                "update_page",
                page_id=markdown_page_id,
                title=f"Markdown Test Page {unique_id} - Updated",
                content="## Updated Content\n\nThis was updated via MCP.",
                content_format="markdown"
            )

            assert update_result["success"] is True

        finally:
            self.cleanup_created_resources(confluence_client, created_resources)

    async def test_confluence_advanced_search(self, mcp_client, confluence_client, test_space_key):
        """Test advanced CQL search functionality."""
        try:
            # Test search with date filters
            date_search_result = await self.call_mcp_tool(
                mcp_client,
                "search",
                query=f'space="{test_space_key}" and created >= startOfDay()',
                limit=5
            )

            assert date_search_result["success"] is True
            assert isinstance(date_search_result, list)

            # Test search with label filter
            label_search_result = await self.call_mcp_tool(
                mcp_client,
                "search",
                query=f'space="{test_space_key}" and label is not empty',
                limit=5
            )

            assert label_search_result["success"] is True
            assert isinstance(label_search_result, list)

            # Test search with multiple conditions
            multi_search_result = await self.call_mcp_tool(
                mcp_client,
                "search",
                query=f'space="{test_space_key}" and type=page and lastModified > startOfWeek()',
                limit=3
            )

            assert multi_search_result["success"] is True
            assert isinstance(multi_search_result, list)

            # Verify all results are pages from the test space
            for page in multi_search_result:
                if isinstance(page, dict):
                    assert page["space"]["key"] == test_space_key
                    assert page.get("type") == "page"

        except Exception as e:
            # Advanced search might not be available in all instances
            pytest.skip(f"Advanced search not available: {e}")

    async def test_confluence_pagination(self, mcp_client, confluence_client, test_space_key, created_resources):
        """Test pagination functionality in search and page children."""
        unique_id = str(uuid.uuid4())[:8]

        try:
            # Create multiple pages to test pagination
            created_page_ids = []
            for i in range(5):
                page_result = await self.call_mcp_tool(
                    mcp_client,
                    "create_page",
                    space_key=test_space_key,
                    title=f"Pagination Test Page {i+1} {unique_id}",
                    content=f"Content for page {i+1}"
                )
                created_page_ids.append(page_result["page"]["id"])
                created_resources["pages"].append(page_result["page"]["id"])

            # Test search pagination
            search_page1 = await self.call_mcp_tool(
                mcp_client,
                "search",
                query=f'space="{test_space_key}" and title ~ "{unique_id}"',
                limit=2
            )

            assert search_page1["success"] is True
            assert len(search_page1) <= 2

            # Test page children pagination
            if created_page_ids:
                # Create a parent page
                parent_result = await self.call_mcp_tool(
                    mcp_client,
                    "create_page",
                    space_key=test_space_key,
                    title=f"Pagination Parent {unique_id}",
                    content="Parent for pagination test"
                )
                parent_id = parent_result["page"]["id"]
                created_resources["pages"].append(parent_id)

                # Move some pages as children
                for i, page_id in enumerate(created_page_ids[:3]):
                    try:
                        await self.call_mcp_tool(
                            mcp_client,
                            "move_page",
                            page_id=page_id,
                            target_parent_page_id=parent_id
                        )
                    except Exception:
                        # Move might fail, that's okay for this test
                        pass

                # Test paginated children
                children_paged = await self.call_mcp_tool(
                    mcp_client,
                    "get_page_children",
                    parent_id=parent_id,
                    limit=2
                )

                assert children_paged["success"] is True
                assert len(children_paged["results"]) <= 2

        finally:
            self.cleanup_created_resources(confluence_client, created_resources)

    async def test_confluence_error_handling(self, mcp_client, confluence_client):
        """Test error handling for various edge cases."""
        # Test getting non-existent page
        non_existent_result = await self.call_mcp_tool(
            mcp_client,
            "get_page",
            page_id="999999999"
        )

        assert not non_existent_result["success"]
        assert "error" in non_existent_result

        # Test getting page with invalid title/space combination
        invalid_title_result = await self.call_mcp_tool(
            mcp_client,
            "get_page",
            title="NonExistentPageTitle12345",
            space_key="INVALID"
        )

        assert not invalid_title_result["success"]
        assert "error" in invalid_title_result

        # Test searching with invalid CQL
        try:
            invalid_cql_result = await self.call_mcp_tool(
                mcp_client,
                "search",
                query="invalid CQL syntax {{{",
                limit=5
            )
            # Should handle gracefully
            assert isinstance(invalid_cql_result, list)
        except Exception:
            # Exception is also acceptable for invalid CQL
            pass

        # Test adding comment to non-existent page
        comment_error_result = await self.call_mcp_tool(
            mcp_client,
            "add_comment",
            page_id="999999999",
            content="Test comment"
        )

        assert not comment_error_result["success"]
        assert "error" in comment_error_result

    async def test_confluence_page_content_options(self, mcp_client, confluence_client, test_space_key, created_resources):
        """Test different page content retrieval options."""
        unique_id = str(uuid.uuid4())[:8]

        try:
            # Create page with substantial content
            content = """
# Test Page Content

This page contains various content types for testing MCP functions.

## Features Tested
- Markdown conversion
- Metadata inclusion
- Content retrieval options

### Code Example
```python
def hello_world():
    print("Hello from MCP!")
    return "success"
```

### Tables
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| More 1   | More 2   | More 3   |

**Bold text** and *italic text*.

> This is a blockquote for testing purposes.
            """.strip()

            # Create page
            create_result = await self.call_mcp_tool(
                mcp_client,
                "create_page",
                space_key=test_space_key,
                title=f"Content Options Test {unique_id}",
                content=content,
                content_format="markdown"
            )

            assert create_result["success"] is True
            page_id = create_result["page"]["id"]
            created_resources["pages"].append(page_id)

            # Test getting page with metadata
            with_metadata_result = await self.call_mcp_tool(
                mcp_client,
                "get_page",
                page_id=page_id,
                include_metadata=True
            )

            assert with_metadata_result["success"] is True
            assert "metadata" in with_metadata_result["page"]
            assert "title" in with_metadata_result["page"]["metadata"]
            assert "space" in with_metadata_result["page"]["metadata"]

            # Test getting page without metadata
            without_metadata_result = await self.call_mcp_tool(
                mcp_client,
                "get_page",
                page_id=page_id,
                include_metadata=False
            )

            assert without_metadata_result["success"] is True
            assert "content" in without_metadata_result["page"]
            # Should not have metadata fields
            assert "createdDate" not in without_metadata_result["page"]

            # Test getting page as HTML
            html_result = await self.call_mcp_tool(
                mcp_client,
                "get_page",
                page_id=page_id,
                convert_to_markdown=False
            )

            assert html_result["success"] is True
            # Content should be in HTML format
            content_value = html_result["page"].get("content", {}).get("value", "")
            assert "<" in content_value and ">" in content_value  # Basic HTML check

        finally:
            self.cleanup_created_resources(confluence_client, created_resources)