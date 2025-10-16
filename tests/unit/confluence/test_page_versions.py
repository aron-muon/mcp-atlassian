"""Tests for Confluence page versions functionality."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client, FastMCPTransport

from mcp_atlassian.models.confluence import ConfluenceVersion
from mcp_atlassian.servers.confluence import register_confluence_tools
from mcp_atlassian.servers.context import MainAppContext
from mcp_atlassian.servers.main import AtlassianMCP
from mcp_atlassian.utils.oauth import OAuthConfig
from mcp_atlassian.confluence.config import ConfluenceConfig
from mcp_atlassian.confluence import ConfluenceFetcher
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


@pytest.fixture
def mock_confluence_fetcher():
    """Create a mocked ConfluenceFetcher instance for testing."""
    mock_fetcher = MagicMock(spec=ConfluenceFetcher)

    # Mock page version methods
    mock_fetcher.get_page_versions.return_value = [
        {
            "number": 1,
            "when": "2023-01-01T10:00:00.000Z",
            "message": "Initial version",
            "minor_edit": False,
        }
    ]

    return mock_fetcher


@pytest.fixture
def mock_base_confluence_config():
    """Create a mock base ConfluenceConfig for MainAppContext using OAuth."""
    mock_oauth_config = OAuthConfig(
        client_id="server_client_id",
        client_secret="server_client_secret",
        redirect_uri="http://localhost",
        scope="read:confluence",
        cloud_id="mock_cloud_id",
    )
    return ConfluenceConfig(
        url="https://mock.atlassian.net/wiki",
        auth_type="oauth",
        oauth_config=mock_oauth_config,
    )


@pytest.fixture
def test_confluence_mcp(mock_base_confluence_config):
    """Create a test FastMCP instance with standard configuration."""
    @asynccontextmanager
    async def test_lifespan(app: FastMCP) -> AsyncGenerator[MainAppContext, None]:
        try:
            yield MainAppContext(
                full_confluence_config=mock_base_confluence_config, read_only=False
            )
        finally:
            pass

    test_mcp = AtlassianMCP(
        "TestConfluence",
        description="Test Confluence MCP Server",
        lifespan=test_lifespan,
    )

    # Create and configure the sub-MCP for Confluence tools
    confluence_sub_mcp = FastMCP(name="TestConfluenceSubMCP")
    register_confluence_tools(confluence_sub_mcp)

    test_mcp.mount("confluence", confluence_sub_mcp)

    return test_mcp


class TestPageVersions:
    """Test page versions functionality through MCP server."""

    @pytest.fixture
    def sample_version(self):
        """Sample version data."""
        return ConfluenceVersion(
            number=1,
            when="2023-01-01T10:00:00.000Z",
            message="Initial version",
            minor_edit=False,
        )

    @pytest.mark.anyio
    async def test_list_page_versions_success(self, test_confluence_mcp, mock_confluence_fetcher, sample_version):
        """Test getting all versions of a page through MCP server."""
        mock_confluence_fetcher.get_page_versions.return_value = [sample_version]

        with patch(
            "mcp_atlassian.servers.confluence.get_confluence_fetcher",
            return_value=mock_confluence_fetcher,
        ):
            async with Client(transport=FastMCPTransport(test_confluence_mcp)) as client:
                response = await client.call_tool(
                    "confluence_list_page_versions", {"page_id": "123456"}
                )

        result_data = json.loads(response[0].text)
        assert "page_id" in result_data
        assert result_data["page_id"] == "123456"
        assert "results" in result_data
        assert len(result_data["results"]) == 1
        assert result_data["results"][0]["number"] == 1

    @pytest.mark.anyio
    async def test_list_page_versions_error(self, test_confluence_mcp, mock_confluence_fetcher):
        """Test error handling when getting page versions through MCP server."""
        mock_confluence_fetcher.get_page_versions.side_effect = Exception(
            "Page not found"
        )

        with patch(
            "mcp_atlassian.servers.confluence.get_confluence_fetcher",
            return_value=mock_confluence_fetcher,
        ):
            async with Client(transport=FastMCPTransport(test_confluence_mcp)) as client:
                response = await client.call_tool(
                    "confluence_list_page_versions", {"page_id": "invalid"}
                )

        result_data = json.loads(response[0].text)
        assert "error" in result_data
        assert "Failed to get page versions" in result_data["error"]
