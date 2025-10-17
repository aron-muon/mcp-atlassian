"""
Automated test setup for MCP Atlassian live tests.

This module provides utilities to automatically set up and tear down test projects
and spaces for reliable live testing without polluting production data.
"""

import asyncio
import json
import os
import uuid
from typing import Dict, List, Optional

import pytest
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client import FastMCPTransport
from mcp.types import TextContent

from mcp_atlassian.servers import main_mcp

load_dotenv()


class TestProjectSetup:
    """Automated test project setup and teardown for Jira and Confluence."""

    def __init__(self):
        self.jira_test_project_key = None
        self.confluence_test_space_key = None
        self.created_resources = {
            "jira": {"projects": [], "issues": [], "versions": [], "comments": []},
            "confluence": {"spaces": [], "pages": [], "comments": [], "labels": []}
        }

    async def setup_jira_test_environment(self, create_project: bool = True) -> str:
        """
        Set up Jira test environment.

        Args:
            create_project: If True, creates a new test project. If False, uses existing.

        Returns:
            The project key to use for testing.
        """
        # Ensure environment variables are loaded before creating MCP client
        load_dotenv()

        transport = FastMCPTransport(main_mcp)
        client = Client(transport=transport)
        async with client as connected_client:
            if create_project:
                # Create a new test project
                project_key = f"TEST{uuid.uuid4().hex[:6].upper()}"
                project_name = f"MCP Test Project {project_key}"

                try:
                    # Force use of TEST project only
                    project_key = "TEST"

                    # Check if TEST project exists
                    result_content = await connected_client.call_tool('jira_get_all_projects', {})
                    if result_content and isinstance(result_content[0], TextContent):
                        projects = json.loads(result_content[0].text)
                        existing_projects = [p.get('key') for p in projects.get('projects', [])]

                        if "TEST" not in existing_projects:
                            print(f"TEST project not found. Available projects: {existing_projects}")
                            raise ValueError("TEST project does not exist. Please create TEST project in Jira.")

                        print(f"Using TEST project for real API testing")

                except Exception as e:
                    raise RuntimeError(f"Failed to set up TEST project: {e}")
            else:
                # Force use of TEST project only
                project_key = "TEST"
                print(f"Using TEST project for real API testing")

            # Verify the project works by creating a test issue
            try:
                test_issue_summary = f"Setup Test Issue {uuid.uuid4().hex[:8]}"
                result = await connected_client.call_tool('jira_create_issue', {
                    'project_key': project_key,
                    'summary': test_issue_summary,
                    'issue_type': 'Task',
                    'description': 'Setup validation issue - will be cleaned up'
                })

                if result and isinstance(result[0], TextContent):
                    issue_result = json.loads(result[0].text)
                    if issue_result.get('success'):
                        test_issue_key = issue_result['issue']['key']
                        self.created_resources["jira"]["issues"].append(test_issue_key)

                        # Verify we can retrieve it
                        verify_result = await connected_client.call_tool('jira_get_issue', {
                            'issue_key': test_issue_key
                        })

                        if verify_result and isinstance(verify_result[0], TextContent):
                            verify_data = json.loads(verify_result[0].text)
                            if verify_data.get('success'):
                                print(f"✅ Jira test environment validated with project: {project_key}")
                                self.jira_test_project_key = project_key
                                return project_key

                raise RuntimeError(f"Failed to validate Jira project {project_key}")

            except Exception as e:
                raise RuntimeError(f"Jira test environment validation failed: {e}")

    async def setup_confluence_test_environment(self, create_space: bool = True) -> str:
        """
        Set up Confluence test environment.

        Args:
            create_space: If True, creates a new test space. If False, uses existing.

        Returns:
            The space key to use for testing.
        """
        # Ensure environment variables are loaded before creating MCP client
        load_dotenv()

        transport = FastMCPTransport(main_mcp)
        client = Client(transport=transport)
        async with client as connected_client:
            if create_space:
                # Create a new test space
                space_key = f"TEST{uuid.uuid4().hex[:6].upper()}"
                space_name = f"MCP Test Space {space_key}"

                try:
                    # Force use of TEST space only
                    space_key = "TEST"

                    # Check if TEST space exists
                    result_content = await connected_client.call_tool('confluence_search', {
                        'query': 'space = "TEST"',
                        'limit': 1
                    })

                    if result_content and isinstance(result_content[0], TextContent):
                        search_result = json.loads(result_content[0].text)
                        if not search_result or len(search_result) == 0:
                            print(f"TEST space not found or empty")
                            raise ValueError("TEST space does not exist. Please create TEST space in Confluence.")

                        print(f"Using TEST space for real API testing")

                except Exception as e:
                    raise RuntimeError(f"Failed to set up TEST space: {e}")
            else:
                # Force use of TEST space only
                space_key = "TEST"
                print(f"Using TEST space for real API testing")

            # Verify the space works by trying to get page by title or creating a test page
            try:
                # Try to get the welcome page that should exist from space creation
                test_page_title = "Welcome to TEST Space"
                get_result = await connected_client.call_tool('confluence_get_page', {
                    'title': test_page_title,
                    'space_key': space_key
                })

                if get_result and isinstance(get_result[0], TextContent):
                    page_data = json.loads(get_result[0].text)
                    # confluence_get_page returns page data directly, not with a success field
                    if page_data.get('metadata') and page_data['metadata'].get('title') == test_page_title:
                        print(f"✅ Confluence test environment validated with space: {space_key} (welcome page found)")
                        self.confluence_test_space_key = space_key
                        return space_key

                # If welcome page not found, try to create a test page
                test_page_title = f"Setup Test Page {uuid.uuid4().hex[:8]}"
                result = await connected_client.call_tool('confluence_create_page', {
                    'space_key': space_key,
                    'title': test_page_title,
                    'content': 'Setup validation page - will be cleaned up'
                })

                if result and isinstance(result[0], TextContent):
                    page_result = json.loads(result[0].text)
                    if page_result.get('success'):
                        test_page_id = page_result['page']['id']
                        self.created_resources["confluence"]["pages"].append(test_page_id)

                        # Verify we can retrieve it
                        verify_result = await connected_client.call_tool('confluence_get_page', {
                            'page_id': test_page_id
                        })

                        if verify_result and isinstance(verify_result[0], TextContent):
                            verify_data = json.loads(verify_result[0].text)
                            if verify_data.get('success'):
                                print(f"✅ Confluence test environment validated with space: {space_key} (test page created)")
                                self.confluence_test_space_key = space_key
                                return space_key

                raise RuntimeError(f"Failed to validate Confluence space {space_key}")

            except Exception as e:
                raise RuntimeError(f"Confluence test environment validation failed: {e}")

    async def cleanup_test_environment(self):
        """Clean up all created test resources."""
        print("🧹 Cleaning up test environment...")

        # Ensure environment variables are loaded before creating MCP client
        load_dotenv()

        transport = FastMCPTransport(main_mcp)
        client = Client(transport=transport)
        async with client as connected_client:
            # Clean up Jira resources
            for issue_key in self.created_resources["jira"]["issues"]:
                try:
                    await connected_client.call_tool('jira_delete_issue', {'issue_key': issue_key})
                    print(f"  Deleted Jira issue: {issue_key}")
                except Exception as e:
                    print(f"  Failed to delete Jira issue {issue_key}: {e}")

            # Clean up Confluence resources
            for page_id in self.created_resources["confluence"]["pages"]:
                try:
                    await connected_client.call_tool('confluence_delete_page', {'page_id': page_id})
                    print(f"  Deleted Confluence page: {page_id}")
                except Exception as e:
                    print(f"  Failed to delete Confluence page {page_id}: {e}")

        print("✅ Test environment cleanup completed")

    def get_jira_project_key(self) -> str:
        """Get the configured Jira test project key."""
        return self.jira_test_project_key or os.getenv("JIRA_TEST_PROJECT_KEY", "TEST")

    def get_confluence_space_key(self) -> str:
        """Get the configured Confluence test space key."""
        return self.confluence_test_space_key or os.getenv("CONFLUENCE_TEST_SPACE_KEY", "TEST")


async def setup_test_project_fresh(jira: bool = True, confluence: bool = True) -> TestProjectSetup:
    """
    Set up a fresh TEST project/space by automatically creating if needed.

    This function ensures that tests start with a clean TEST environment by:
    1. Creating TEST space in Confluence if it doesn't exist (if confluence=True)
    2. Verifying TEST project exists in Jira (project creation via API not supported) (if jira=True)
    3. Setting up the environment for testing

    Args:
        jira: Whether to set up Jira TEST project
        confluence: Whether to set up Confluence TEST space

    Returns:
        TestProjectSetup instance with TEST project/space ready for testing
    """
    setup = TestProjectSetup()

    # Handle Confluence TEST space - AUTO-CREATE IF NEEDED
    if confluence:
        try:
            print(f"🔍 Checking for TEST space...")

            # Import here to avoid circular imports
            from mcp_atlassian.confluence import ConfluenceFetcher
            from mcp_atlassian.confluence.config import ConfluenceConfig

            # Check if TEST space exists via direct API
            confluence_config = ConfluenceConfig.from_env()
            confluence_fetcher = ConfluenceFetcher(config=confluence_config)

            spaces_response = confluence_fetcher.confluence.get_all_spaces()
            existing_spaces = [space.get('key') for space in spaces_response.get('results', [])]

            if 'TEST' not in existing_spaces:
                print(f"🆕 TEST space not found, creating...")
                confluence_fetcher.confluence.create_space(
                    space_key='TEST',
                    space_name='Test Space for MCP'
                )
                print(f"✅ Created TEST space")

                # Create a welcome page
                welcome_page = confluence_fetcher.create_page(
                    space_key='TEST',
                    title='Welcome to TEST Space',
                    body='This space is automatically created for MCP real API testing. All test resources are tracked and cleaned up automatically.'
                )
                print(f"✅ Created welcome page: {welcome_page.title}")
            else:
                print(f"✅ Found existing TEST space")

            await setup.setup_confluence_test_environment(create_space=False)

        except Exception as e:
            print(f"❌ TEST space setup failed: {e}")
            raise e

    # Handle Jira TEST project - VERIFY EXISTS (cannot auto-create)
    if jira:
        transport = FastMCPTransport(main_mcp)
        client = Client(transport=transport)
        async with client as connected_client:
            try:
                print(f"🔍 Checking for TEST project...")
                result_content = await connected_client.call_tool('jira_get_all_projects', {})
                if result_content and isinstance(result_content[0], TextContent):
                    projects = json.loads(result_content[0].text)
                    existing_projects = [p.get('key') for p in projects.get('projects', [])]

                    if 'TEST' not in existing_projects:
                        print(f"❌ TEST project not found. Available projects: {existing_projects}")
                        print(f"")
                        print(f"MANUAL ACTION REQUIRED:")
                        print(f"1. Go to your Jira instance: {os.getenv('JIRA_URL', 'https://your-domain.atlassian.net/')}")
                        print(f"2. Create a new project with:")
                        print(f"   - Project Key: TEST")
                        print(f"   - Project Name: Test Project for MCP")
                        print(f"   - Type: Any (Kanban, Scrum, etc.)")
                        print(f"3. Ensure your test user has full access to the project")
                        print(f"")
                        raise ValueError("TEST project not found. Please create TEST project in Jira.")

                    print(f"✅ Found TEST project")
                    await setup.setup_jira_test_environment(create_project=False)

            except Exception as e:
                print(f"❌ TEST project setup failed: {e}")
                raise e

    return setup


async def setup_test_environment(jira: bool = True, confluence: bool = True,
                              create_jira_project: bool = False, create_confluence_space: bool = False) -> TestProjectSetup:
    """
    Set up test environment for Jira and Confluence.

    Args:
        jira: Whether to set up Jira test environment
        confluence: Whether to set up Confluence test environment
        create_jira_project: Whether to create new Jira project (vs using existing)
        create_confluence_space: Whether to create new Confluence space (vs using existing)

    Returns:
        TestProjectSetup instance with configured project/space keys
    """
    setup = TestProjectSetup()

    try:
        if jira:
            await setup.setup_jira_test_environment(create_jira_project)

        if confluence:
            await setup.setup_confluence_test_environment(create_confluence_space)

        return setup

    except Exception as e:
        # Cleanup any partial setup
        await setup.cleanup_test_environment()
        raise e


# Pytest fixtures for test setup
@pytest.fixture
async def test_environment():
    """Set up and tear down test environment for pytest."""
    setup = await setup_test_environment()
    yield setup
    await setup.cleanup_test_environment()


@pytest.fixture
async def jira_test_project():
    """Set up and tear down Jira test project for pytest."""
    setup = await setup_test_environment(jira=False, confluence=False)
    await setup.setup_jira_test_environment()
    yield setup.get_jira_project_key()
    await setup.cleanup_test_environment()


@pytest.fixture
async def confluence_test_space():
    """Set up and tear down Confluence test space for pytest."""
    setup = await setup_test_environment(jira=False, confluence=False)
    await setup.setup_confluence_test_environment()
    yield setup.get_confluence_space_key()
    await setup.cleanup_test_environment()


@pytest.fixture
async def fresh_test_environment():
    """Set up fresh TEST project/space by deleting existing and creating new."""
    setup = await setup_test_project_fresh()
    yield setup
    await setup.cleanup_test_environment()


@pytest.fixture
async def fresh_confluence_test_environment():
    """Set up fresh TEST space only (for Confluence-only tests)."""
    setup = await setup_test_project_fresh(jira=False, confluence=True)
    yield setup
    await setup.cleanup_test_environment()


@pytest.fixture
async def fresh_jira_test_environment():
    """Set up fresh TEST project only (for Jira-only tests)."""
    setup = await setup_test_project_fresh(jira=True, confluence=False)
    yield setup
    await setup.cleanup_test_environment()