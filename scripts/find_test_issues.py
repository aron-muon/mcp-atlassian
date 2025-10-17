#!/usr/bin/env python3
"""
Find test issues using the updated Jira API.
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

def find_jira_issues(project_key):
    """Find existing issues in a project using the new API."""
    print(f"=== Finding Issues in {project_key} ===")

    session = requests.Session()
    session.auth = (os.getenv("JIRA_USERNAME"), os.getenv("JIRA_API_TOKEN"))

    try:
        # Use the new JQL search API
        url = f"{os.getenv('JIRA_URL')}rest/api/3/search/jql"
        data = {
            "jql": f"project = {project_key} ORDER BY created DESC",
            "fields": ["key", "summary", "status", "issuetype"],
            "maxResults": 10
        }

        response = session.post(url, json=data)
        print(f"API Response Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            issues = result.get("issues", [])
            print(f"Found {len(issues)} recent issues:")

            for issue in issues:
                fields = issue['fields']
                print(f"  - {issue['key']}: {fields.get('summary', 'No summary')}")
                print(f"    Type: {fields.get('issuetype', {}).get('name', 'Unknown')}")
                print(f"    Status: {fields.get('status', {}).get('name', 'Unknown')}")

            if issues:
                # Find different types of issues for testing
                task_issues = [i for i in issues if i['fields']['issuetype']['name'] == 'Task']
                epic_issues = [i for i in issues if i['fields']['issuetype']['name'].lower() == 'epic']
                subtask_issues = [i for i in issues if i['fields']['issuetype']['name'].lower() == 'sub-task']

                test_data = {
                    'project_key': project_key,
                    'test_issue': issues[0]['key'],  # First issue for general testing
                    'test_task': task_issues[0]['key'] if task_issues else issues[0]['key'],
                    'test_epic': epic_issues[0]['key'] if epic_issues else issues[0]['key'],
                    'test_subtask': subtask_issues[0]['key'] if subtask_issues else None
                }

                print(f"\nSelected test data:")
                print(f"  Project: {test_data['project_key']}")
                print(f"  Test Issue: {test_data['test_issue']}")
                print(f"  Test Task: {test_data['test_task']}")
                print(f"  Test Epic: {test_data['test_epic']}")
                print(f"  Test Subtask: {test_data['test_subtask']}")

                return test_data
            else:
                print("No issues found in this project")
                return None
        else:
            print(f"Failed to search issues: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error finding issues: {e}")
        return None

def create_test_issue_if_needed(project_key):
    """Create a test issue if no suitable issues exist."""
    print(f"\n=== Creating Test Issue in {project_key} ===")

    session = requests.Session()
    session.auth = (os.getenv("JIRA_USERNAME"), os.getenv("JIRA_API_TOKEN"))

    try:
        # First, check if we can create issues by getting field metadata
        fields_url = f"{os.getenv('JIRA_URL')}rest/api/3/issue/createmeta"
        params = {
            "projectKeys": project_key,
            "issuetypeNames": "Task",
            "expand": "projects.issuetypes.fields"
        }

        response = session.get(fields_url, params=params)
        if response.status_code != 200:
            print(f"Cannot check create metadata: {response.status_code}")
            return None

        # Try to create a simple test issue
        create_url = f"{os.getenv('JIRA_URL')}rest/api/3/issue"
        issue_data = {
            "fields": {
                "project": {"key": project_key},
                "summary": "Test Issue for MCP API Validation",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "This is a test issue created by the MCP Atlassian validation script. It can be deleted after testing."
                                }
                            ]
                        }
                    ]
                },
                "issuetype": {"name": "Task"}
            }
        }

        response = session.post(create_url, json=issue_data)
        print(f"Create issue response: {response.status_code}")

        if response.status_code == 201:
            issue = response.json()
            print(f"✅ Created test issue: {issue['key']}")
            return issue['key']
        else:
            print(f"Failed to create issue: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error creating test issue: {e}")
        return None

if __name__ == "__main__":
    print("Finding Jira test data using updated API")
    print("=" * 50)

    project_key = "KAN"  # From our previous discovery
    test_data = find_jira_issues(project_key)

    if not test_data:
        print("No existing issues found, trying to create one...")
        test_issue = create_test_issue_if_needed(project_key)
        if test_issue:
            test_data = {
                'project_key': project_key,
                'test_issue': test_issue,
                'test_task': test_issue,
                'test_epic': test_issue,
                'test_subtask': None
            }

    if test_data:
        # Update the .env.test file with real data
        test_env_content = f"""# Test Environment Variables for MCP Atlassian Tests
# Auto-generated by find_test_issues.py

# Jira Test Data
JIRA_TEST_PROJECT_KEY={test_data['project_key']}
JIRA_TEST_ISSUE_KEY={test_data['test_issue']}
JIRA_TEST_EPIC_KEY={test_data['test_epic']}

# Confluence Test Data (not available)
CONFLUENCE_TEST_SPACE_KEY=TEST
CONFLUENCE_TEST_PAGE_ID=123456
"""

        with open('.env.test', 'w') as f:
            f.write(test_env_content)

        print(f"\n✅ Updated .env.test file with real test data")
        print("Ready to run Jira API tests!")
    else:
        print("\n❌ Could not find or create test data")