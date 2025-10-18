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
                    # Use project key from environment variable
                    project_key = os.getenv("JIRA_TEST_PROJECT_KEY", "TST")

                    # Check if test project exists
                    result_content = await connected_client.call_tool('jira_get_all_projects', {})
                    if result_content and isinstance(result_content[0], TextContent):
                        projects = json.loads(result_content[0].text)
                        existing_projects = [p.get('key') for p in projects.get('projects', [])]

                        if project_key not in existing_projects:
                            print(f"{project_key} project not found. Available projects: {existing_projects}")
                            raise ValueError(f"{project_key} project does not exist. Please create {project_key} project in Jira.")

                        print(f"Using {project_key} project for real API testing")

                except Exception as e:
                    raise RuntimeError(f"Failed to set up {project_key} project: {e}")
            else:
                # Use project key from environment variable
                project_key = os.getenv("JIRA_TEST_PROJECT_KEY", "TST")
                print(f"Using {project_key} project for real API testing")

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
                    # Use environment variable for space key
                    space_key = os.getenv("CONFLUENCE_TEST_SPACE_KEY", "TEST")

                    # Check if test space exists
                    result_content = await connected_client.call_tool('confluence_search', {
                        'query': f'space = "{space_key}"',
                        'limit': 1
                    })

                    if result_content and isinstance(result_content[0], TextContent):
                        search_result = json.loads(result_content[0].text)
                        if not search_result or len(search_result) == 0:
                            print(f"{space_key} space not found or empty")
                            raise ValueError(f"{space_key} space does not exist. Please create {space_key} space in Confluence.")

                        print(f"Using {space_key} space for real API testing")

                except Exception as e:
                    raise RuntimeError(f"Failed to set up {space_key} space: {e}")
            else:
                # Use environment variable for space key
                space_key = os.getenv("CONFLUENCE_TEST_SPACE_KEY", "TEST")
                print(f"Using {space_key} space for real API testing")

            # Verify the space works by creating a test page (more flexible approach)
            try:
                # Always create a fresh test page to validate the space works
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
                                print(f"✅ Confluence test environment validated with space: {space_key} (test page created and verified)")
                                self.confluence_test_space_key = space_key
                                return space_key

                raise RuntimeError(f"Failed to validate Confluence space {space_key}")

            except Exception as e:
                raise RuntimeError(f"Confluence test environment validation failed: {e}")

    async def cleanup_test_environment(self):
        """Clean up all created test resources and leave spaces ready for future testing."""
        print("🧹 Cleaning up test environment...")

        # Ensure environment variables are loaded before creating MCP client
        load_dotenv()

        transport = FastMCPTransport(main_mcp)
        client = Client(transport=transport)
        async with client as connected_client:
            # Clean up Jira resources tracked during this test session
            for issue_key in self.created_resources["jira"]["issues"]:
                try:
                    await connected_client.call_tool('jira_delete_issue', {'issue_key': issue_key})
                    print(f"  Deleted tracked Jira issue: {issue_key}")
                except Exception as e:
                    print(f"  Failed to delete tracked Jira issue {issue_key}: {e}")

            # Clean up Confluence resources tracked during this test session
            for page_id in self.created_resources["confluence"]["pages"]:
                try:
                    await connected_client.call_tool('confluence_delete_page', {'page_id': page_id})
                    print(f"  Deleted tracked Confluence page: {page_id}")
                except Exception as e:
                    print(f"  Failed to delete tracked Confluence page {page_id}: {e}")

        # Final comprehensive cleanup of any remaining test data
        print("🧹 Performing final cleanup of any remaining test data...")
        try:
            test_project_key = os.getenv("JIRA_TEST_PROJECT_KEY", "TST")
            await _cleanup_jira_test_data(test_project_key, client)
        except Exception as e:
            print(f"  ⚠️  Final Jira cleanup failed: {e}")

        try:
            test_space_key = os.getenv("CONFLUENCE_TEST_SPACE_KEY", "TEST")
            from mcp_atlassian.confluence import ConfluenceFetcher
            from mcp_atlassian.confluence.config import ConfluenceConfig
            confluence_config = ConfluenceConfig.from_env()
            confluence_fetcher = ConfluenceFetcher(config=confluence_config)
            await _cleanup_confluence_test_data(test_space_key, confluence_fetcher)
        except Exception as e:
            print(f"  ⚠️  Final Confluence cleanup failed: {e}")

        print("✅ Test environment cleanup completed - spaces ready for future testing")

    def get_jira_project_key(self) -> str:
        """Get the configured Jira test project key."""
        return self.jira_test_project_key or os.getenv("JIRA_TEST_PROJECT_KEY", "TST")

    def get_confluence_space_key(self) -> str:
        """Get the configured Confluence test space key."""
        return self.confluence_test_space_key or os.getenv("CONFLUENCE_TEST_SPACE_KEY", "TEST")


async def setup_test_project_fresh(jira: bool = True, confluence: bool = True) -> TestProjectSetup:
    """
    Set up fresh test environment by cleaning existing test data and creating spaces if needed.

    This function ensures that tests start with a clean environment by:
    1. Creating test spaces if they don't exist (NEVER deletes spaces)
    2. Cleaning up existing test data (issues, pages, comments) from spaces/projects
    3. Setting up the environment for testing

    Args:
        jira: Whether to set up Jira test project
        confluence: Whether to set up Confluence test space

    Returns:
        TestProjectSetup instance with test project/space ready for testing
    """
    setup = TestProjectSetup()

    # Handle Confluence test space - CREATE IF NEEDED, NEVER DELETE
    if confluence:
        try:
            # Use environment variable for space key
            test_space_key = os.getenv("CONFLUENCE_TEST_SPACE_KEY", "TEST")
            print(f"🔍 Preparing {test_space_key} space...")

            # Import here to avoid circular imports
            from mcp_atlassian.confluence import ConfluenceFetcher
            from mcp_atlassian.confluence.config import ConfluenceConfig

            # Check if test space exists via direct API
            confluence_config = ConfluenceConfig.from_env()
            confluence_fetcher = ConfluenceFetcher(config=confluence_config)

            spaces_response = confluence_fetcher.confluence.get_all_spaces()
            existing_spaces = [space.get('key') for space in spaces_response.get('results', [])]

            if test_space_key not in existing_spaces:
                print(f"🆕 {test_space_key} space not found, creating...")
                confluence_fetcher.confluence.create_space(
                    space_key=test_space_key,
                    space_name=f'Test Space for MCP ({test_space_key})'
                )
                print(f"✅ Created {test_space_key} space")

                # Create a welcome page
                welcome_page = confluence_fetcher.create_page(
                    space_key=test_space_key,
                    title=f'Welcome to {test_space_key} Space',
                    body=f'This space is automatically created for MCP real API testing. All test resources are tracked and cleaned up automatically.'
                )
                print(f"✅ Created welcome page: {welcome_page.title}")
            else:
                print(f"✅ Found existing {test_space_key} space")
                # Clean up any existing test pages from previous runs
                print(f"🧹 Cleaning up existing test data from {test_space_key} space...")
                await _cleanup_confluence_test_data(test_space_key, confluence_fetcher)

            # Try to setup the test environment, but don't fail if validation has issues
            try:
                await setup.setup_confluence_test_environment(create_space=False)
            except Exception as e:
                print(f"⚠️  Confluence environment validation had issues, but continuing: {e}")
                # The space exists and was cleaned, so we can continue even if validation fails

        except Exception as e:
            print(f"❌ {test_space_key} space setup failed: {e}")
            raise e

    # Handle Jira test project - VERIFY EXISTS, NEVER DELETE PROJECT
    if jira:
        test_project_key = os.getenv("JIRA_TEST_PROJECT_KEY", "TST")
        transport = FastMCPTransport(main_mcp)
        client = Client(transport=transport)
        async with client as connected_client:
            try:
                print(f"🔍 Preparing {test_project_key} project...")
                result_content = await connected_client.call_tool('jira_get_all_projects', {})
                if result_content and isinstance(result_content[0], TextContent):
                    projects = json.loads(result_content[0].text)
                    existing_projects = [p.get('key') for p in projects.get('projects', [])]

                    if test_project_key not in existing_projects:
                        print(f"❌ {test_project_key} project not found. Available projects: {existing_projects}")
                        print(f"")
                        print(f"MANUAL ACTION REQUIRED:")
                        print(f"1. Go to your Jira instance: {os.getenv('JIRA_URL', 'https://your-domain.atlassian.net/')}")
                        print(f"2. Create a new project with:")
                        print(f"   - Project Key: {test_project_key}")
                        print(f"   - Project Name: Test Project for MCP")
                        print(f"   - Type: Software (Scrum template for epics support)")
                        print(f"3. Ensure your test user has full access to the project")
                        print(f"")
                        raise ValueError(f"{test_project_key} project not found. Please create {test_project_key} project in Jira.")

                    print(f"✅ Found existing {test_project_key} project")
                    # Clean up any existing test issues from previous runs
                    print(f"🧹 Cleaning up existing test data from {test_project_key} project...")
                    await _cleanup_jira_test_data(test_project_key, connected_client)

                    await setup.setup_jira_test_environment(create_project=False)

            except Exception as e:
                print(f"❌ {test_project_key} project setup failed: {e}")
                raise e

    return setup


async def _cleanup_confluence_test_data(space_key: str, confluence_fetcher) -> None:
    """Clean up test data from Confluence space without deleting the space itself."""
    try:
        # Search for test pages with typical test patterns
        cql = f'space = "{space_key}" AND (title ~ "Test" OR title ~ "MCP" OR title ~ "Setup Test")'
        search_results = confluence_fetcher.search(cql, limit=50)

        cleaned_count = 0
        for page in search_results:
            try:
                # Only delete pages that look like test pages
                title = page.title.lower()
                if any(keyword in title for keyword in ['test', 'mcp', 'setup', 'validation']):
                    confluence_fetcher.delete_page(page.id)
                    cleaned_count += 1
                    print(f"  Deleted test page: {page.title}")
            except Exception as e:
                print(f"  Failed to delete page {page.title}: {e}")

        if cleaned_count > 0:
            print(f"✅ Cleaned up {cleaned_count} test pages from {space_key} space")
        else:
            print(f"✅ No test pages found to clean in {space_key} space")

    except Exception as e:
        print(f"⚠️  Could not clean up Confluence test data: {e}")


async def _cleanup_jira_test_data(project_key: str, client) -> None:
    """Clean up test data from Jira project without deleting the project itself."""
    try:
        # Search for test issues with typical test patterns
        search_result = await client.call_tool('jira_search', {
            'jql': f'project = "{project_key}" AND (summary ~ "Test" OR summary ~ "MCP" OR summary ~ "Validation" OR summary ~ "Setup")',
            'limit': 50
        })

        if search_result and isinstance(search_result[0], TextContent):
            search_data = json.loads(search_result[0].text)
            if search_data.get('success'):
                issues = search_data.get('search_results', {}).get('issues', [])

                cleaned_count = 0
                for issue in issues:
                    try:
                        issue_key = issue.get('key')
                        if issue_key:
                            await client.call_tool('jira_delete_issue', {'issue_key': issue_key})
                            cleaned_count += 1
                            print(f"  Deleted test issue: {issue_key}")
                    except Exception as e:
                        print(f"  Failed to delete issue {issue.get('key')}: {e}")

                if cleaned_count > 0:
                    print(f"✅ Cleaned up {cleaned_count} test issues from {project_key} project")
                else:
                    print(f"✅ No test issues found to clean in {project_key} project")

    except Exception as e:
        print(f"⚠️  Could not clean up Jira test data: {e}")


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