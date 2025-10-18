#!/usr/bin/env python3
"""
Script to create a simple software project for Epic functionality.
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def create_software_project_for_epics():
    """Create a software project without specifying template."""

    # Load Jira configuration
    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_url, jira_username, jira_api_token]):
        print("❌ Missing Jira configuration in .env file")
        return False

    print(f"🔗 Connecting to Jira: {jira_url}")

    # Get user account ID
    try:
        user_url = f"{jira_url.rstrip('/')}/rest/api/3/myself"
        headers = {"Accept": "application/json"}
        auth = (jira_username, jira_api_token)

        user_response = requests.get(user_url, headers=headers, auth=auth)
        if user_response.status_code != 200:
            print(f"❌ Failed to get user info: {user_response.status_code}")
            return False

        account_id = user_response.json().get('accountId')
        print(f"✅ Found user account ID: {account_id}")
    except Exception as e:
        print(f"❌ Error getting user info: {e}")
        return False

    # Check existing projects to avoid conflicts
    projects_url = f"{jira_url.rstrip('/')}/rest/api/3/project/search"
    projects_response = requests.get(projects_url, headers=headers, auth=auth, params={"maxResults": 50})

    existing_projects = []
    if projects_response.status_code == 200:
        projects_data = projects_response.json()
        existing_projects = [p.get('key') for p in projects_data.get('values', [])]
        print(f"📋 Existing projects: {existing_projects}")

    # Choose a project key that's not taken
    potential_keys = ["EPIC", "SOFT", "AGILE", "DEV"]
    project_key = None
    for key in potential_keys:
        if key not in existing_projects:
            project_key = key
            break

    if not project_key:
        print("❌ Could not find an available project key")
        return False

    print(f"🚀 Using project key: {project_key}")

    # Create software project without template (let Jira choose default)
    api_url = f"{jira_url.rstrip('/')}/rest/api/3/project"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    project_payload = {
        "key": project_key,
        "name": f"{project_key} Software Project for MCP Testing",
        "projectTypeKey": "software",  # Software type for Epic support
        "description": "Test software project for MCP real API testing with Epic functionality. All test resources are tracked and cleaned up automatically.",
        "leadAccountId": account_id,
        "assigneeType": "PROJECT_LEAD"
        # Note: Not specifying projectTemplateKey - let Jira use default software template
    }

    try:
        print(f"📤 Creating {project_key} software project (no template specified)...")
        print(f"📋 Project payload: {json.dumps(project_payload, indent=2)}")

        response = requests.post(api_url, headers=headers, auth=auth, json=project_payload, timeout=30)
        print(f"📊 Project creation status: {response.status_code}")

        if response.status_code == 201:
            project_data = response.json()
            print("✅ Successfully created software project!")
            print(f"📋 Project details:")
            print(f"   - ID: {project_data.get('id')}")
            print(f"   - Key: {project_data.get('key')}")
            print(f"   - Name: {project_data.get('name')}")
            print(f"   - Type: {project_data.get('projectTypeKey')}")
            return project_key

        elif response.status_code == 400:
            error_data = response.json()
            print(f"❌ Bad request: {error_data}")

            # Check if it's a template issue
            error_str = str(error_data).lower()
            if "template" in error_str:
                print("💡 Trying without project type specification...")
                return try_minimal_project_creation(jira_url, jira_username, jira_api_token, account_id, existing_projects)

        else:
            print(f"❌ Failed to create project: {response.status_code}")
            print(f"Response: {response.text}")

        return None

    except Exception as e:
        print(f"❌ Error creating project: {e}")
        return None

def try_minimal_project_creation(jira_url, username, api_token, account_id, existing_projects):
    """Try creating project with minimal configuration."""

    # Choose a different project key
    potential_keys = ["TESTSW", "MCP", "TEST2", "PROJ"]
    project_key = None
    for key in potential_keys:
        if key not in existing_projects:
            project_key = key
            break

    if not project_key:
        print("❌ Could not find an available project key")
        return False

    print(f"🔄 Trying minimal project creation with key: {project_key}")

    api_url = f"{jira_url.rstrip('/')}/rest/api/3/project"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    auth = (username, api_token)

    # Minimal payload - only required fields
    project_payload = {
        "key": project_key,
        "name": f"{project_key} Project for MCP",
        "leadAccountId": account_id
        # Not specifying projectTypeKey or projectTemplateKey
    }

    try:
        print(f"📤 Creating minimal project...")
        print(f"📋 Minimal payload: {json.dumps(project_payload, indent=2)}")

        response = requests.post(api_url, headers=headers, auth=auth, json=project_payload, timeout=30)
        print(f"📊 Minimal project creation status: {response.status_code}")

        if response.status_code == 201:
            project_data = response.json()
            print("✅ Successfully created minimal project!")
            print(f"📋 Project details:")
            print(f"   - Key: {project_data.get('key')}")
            print(f"   - Name: {project_data.get('name')}")
            print(f"   - Type: {project_data.get('projectTypeKey', 'Unknown')}")
            return project_key

        else:
            print(f"❌ Minimal project creation failed: {response.text}")

        return None

    except Exception as e:
        print(f"❌ Error with minimal project creation: {e}")
        return None

def test_epic_functionality(jira_url, username, api_token, project_key):
    """Test if Epic functionality works in the created project."""

    api_url = f"{jira_url.rstrip('/')}/rest/api/3/issue/createmeta/{project_key}/issuetypes"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    auth = (username, api_token)

    try:
        response = requests.get(api_url, headers=headers, auth=auth)

        if response.status_code == 200:
            data = response.json()

            # Look for Epic issue type
            for issue_type in data.get('values', []):
                if issue_type.get('name', '').lower() == 'epic':
                    print("✅ Epic issue type found!")
                    print(f"   📋 Epic: {issue_type.get('name')}")

                    # Check required fields
                    fields = issue_type.get('fields', {})
                    required_fields = [field_data.get('name', field_key)
                                     for field_key, field_data in fields.items()
                                     if field_data.get('required', False)]

                    if required_fields:
                        print(f"   🔧 Required fields: {required_fields}")
                    else:
                        print("   ℹ️  No required fields for Epic creation")

                    return True

            print("❌ Epic issue type not found in created project")
            return False

        else:
            print(f"❌ Failed to check Epic functionality: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error checking Epic functionality: {e}")
        return False

def main():
    """Main function to create project for Epic testing."""
    print("🚀 Creating software project for Epic functionality testing...")

    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    project_key = create_software_project_for_epics()

    if project_key:
        print(f"\n✅ SUCCESS: Created {project_key} project!")
        print("🔍 Checking Epic functionality...")

        has_epics = test_epic_functionality(jira_url, jira_username, jira_api_token, project_key)

        if has_epics:
            print(f"\n🎉 {project_key} project has Epic functionality!")
            print("🧪 You can now update tests to use this project for Epic testing")
            print(f"💡 Update JIRA_TEST_PROJECT_KEY to '{project_key}' in your .env file")
        else:
            print(f"\n⚠️  {project_key} project created but Epic functionality not available")
            print("💡 This might be a limitation of the Jira instance or project type")
    else:
        print("\n❌ FAILED: Could not create project with Epic functionality")

if __name__ == "__main__":
    main()