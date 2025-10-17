#!/usr/bin/env python3
"""
Find and create test data for running real API tests.
"""
import os
import requests
import json
from pathlib import Path

# Load .env file
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

def check_jira_projects():
    """Check available Jira projects."""
    print("=== Checking Jira Projects ===")

    session = requests.Session()
    session.auth = (os.getenv("JIRA_USERNAME"), os.getenv("JIRA_API_TOKEN"))

    try:
        response = session.get(f"{os.getenv('JIRA_URL')}rest/api/3/project")
        if response.status_code == 200:
            projects = response.json()
            print(f"Found {len(projects)} projects:")
            for project in projects[:5]:  # Show first 5
                print(f"  - {project['key']}: {project['name']}")

            # Find a good candidate for testing
            for project in projects:
                if project['key'] not in ['SYS', 'ADMIN', 'PORT', 'HSP']:
                    print(f"\nSelected project for testing: {project['key']} ({project['name']})")
                    return project['key']

            # Fallback to first project
            return projects[0]['key'] if projects else None
        else:
            print(f"Failed to get projects: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error checking projects: {e}")
        return None

def find_existing_issues(project_key):
    """Find existing issues in a project."""
    print(f"\n=== Finding Issues in {project_key} ===")

    session = requests.Session()
    session.auth = (os.getenv("JIRA_USERNAME"), os.getenv("JIRA_API_TOKEN"))

    try:
        # Search for recent issues
        jql = f"project = {project_key} ORDER BY created DESC"
        params = {
            "jql": jql,
            "fields": "key,summary,status,issuetype",
            "maxResults": 5
        }

        response = session.get(f"{os.getenv('JIRA_URL')}rest/api/3/search", params=params)
        if response.status_code == 200:
            data = response.json()
            issues = data.get("issues", [])
            print(f"Found {len(issues)} recent issues:")

            for issue in issues:
                print(f"  - {issue['key']}: {issue['fields']['summary']}")
                print(f"    Type: {issue['fields']['issuetype']['name']}")
                print(f"    Status: {issue['fields']['status']['name']}")

            # Return first issue as test issue
            if issues:
                test_issue = issues[0]['key']
                print(f"\nSelected test issue: {test_issue}")
                return test_issue
            return None
        else:
            print(f"Failed to search issues: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error finding issues: {e}")
        return None

def check_confluence_spaces():
    """Check available Confluence spaces."""
    print(f"\n=== Checking Confluence Spaces ===")

    session = requests.Session()
    session.auth = (os.getenv("CONFLUENCE_USERNAME"), os.getenv("CONFLUENCE_API_TOKEN"))

    try:
        response = session.get(f"{os.getenv('CONFLUENCE_URL')}rest/api/space", params={"limit": 20})
        if response.status_code == 200:
            data = response.json()
            spaces = data.get("results", [])
            print(f"Found {len(spaces)} spaces:")

            for space in spaces[:5]:  # Show first 5
                print(f"  - {space['key']}: {space['name']}")

            # Find a good candidate for testing
            for space in spaces:
                if space['key'] not in ['DS', '~personal']:
                    print(f"\nSelected space for testing: {space['key']} ({space['name']})")
                    return space['key']

            # Fallback to first space
            return spaces[0]['key'] if spaces else None
        else:
            print(f"Failed to get spaces (Confluence may not be available): {response.status_code}")
            return None
    except Exception as e:
        print(f"Error checking spaces (Confluence may not be available): {e}")
        return None

def find_confluence_pages(space_key):
    """Find existing pages in a Confluence space."""
    if not space_key:
        return None

    print(f"\n=== Finding Pages in {space_key} ===")

    session = requests.Session()
    session.auth = (os.getenv("CONFLUENCE_USERNAME"), os.getenv("CONFLUENCE_API_TOKEN"))

    try:
        cql = f"space = {space_key} and type = page order by created desc"
        params = {
            "cql": cql,
            "limit": 5
        }

        response = session.get(f"{os.getenv('CONFLUENCE_URL')}rest/api/search", params=params)
        if response.status_code == 200:
            data = response.json()
            pages = data.get("results", [])
            print(f"Found {len(pages)} recent pages:")

            for page in pages:
                print(f"  - {page['id']}: {page['title']}")

            # Return first page as test page
            if pages:
                test_page = pages[0]['id']
                print(f"\nSelected test page: {test_page}")
                return test_page
            return None
        else:
            print(f"Failed to search pages: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error finding pages: {e}")
        return None

def create_test_environment_file(project_key, issue_key, space_key, page_id):
    """Create a test environment file with the discovered data."""
    test_env_content = f"""# Test Environment Variables for MCP Atlassian Tests
# Auto-generated by find_test_data.py

# Jira Test Data
JIRA_TEST_PROJECT_KEY={project_key}
JIRA_TEST_ISSUE_KEY={issue_key}
JIRA_TEST_EPIC_KEY={issue_key}  # Using same issue as epic for testing

# Confluence Test Data (may be None if not available)
CONFLUENCE_TEST_SPACE_KEY={space_key or 'TEST'}
CONFLUENCE_TEST_PAGE_ID={page_id or '123456'}
"""

    with open('.env.test', 'w') as f:
        f.write(test_env_content)

    print(f"\n=== Created .env.test file ===")
    print("Test environment variables:")
    print(f"  JIRA_TEST_PROJECT_KEY={project_key}")
    print(f"  JIRA_TEST_ISSUE_KEY={issue_key}")
    print(f"  CONFLUENCE_TEST_SPACE_KEY={space_key or 'TEST'}")
    print(f"  CONFLUENCE_TEST_PAGE_ID={page_id or '123456'}")

if __name__ == "__main__":
    print("Finding test data for MCP Atlassian API tests")
    print("=" * 50)

    # Check Jira
    project_key = check_jira_projects()
    if project_key:
        issue_key = find_existing_issues(project_key)
    else:
        issue_key = None

    # Check Confluence
    space_key = check_confluence_spaces()
    if space_key:
        page_id = find_confluence_pages(space_key)
    else:
        page_id = None

    # Create test environment file
    create_test_environment_file(project_key, issue_key, space_key, page_id)

    print("\n" + "=" * 50)
    if project_key and issue_key:
        print("✅ Ready for Jira API testing")
    else:
        print("❌ Jira test data incomplete")

    if space_key and page_id:
        print("✅ Ready for Confluence API testing")
    else:
        print("⚠️  Confluence test data incomplete (may not be available)")