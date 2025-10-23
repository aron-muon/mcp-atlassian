#!/usr/bin/env python3
"""
Script to create a software project with Epic functionality for MCP testing.
"""

import asyncio
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_current_user_account_id(jira_url, username, api_token):
    """Get the current user's account ID."""
    api_url = f"{jira_url.rstrip('/')}/rest/api/3/myself"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    auth = (username, api_token)

    try:
        response = requests.get(api_url, headers=headers, auth=auth)
        if response.status_code == 200:
            user_data = response.json()
            account_id = user_data.get('accountId')
            print(f"✅ Found user account ID: {account_id}")
            return account_id
        else:
            print(f"❌ Failed to get user info: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting user info: {e}")
        return None

def create_software_project_with_epics():
    """Create a software project with Epic functionality using REST API."""

    # Load Jira configuration
    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_url, jira_username, jira_api_token]):
        print("❌ Missing Jira configuration in .env file")
        return False

    print(f"🔗 Connecting to Jira: {jira_url}")

    # Get current user's account ID
    account_id = get_current_user_account_id(jira_url, jira_username, jira_api_token)
    if not account_id:
        return False

    # Headers for authentication
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Basic auth
    auth = (jira_username, jira_api_token)

    try:
        # Check if TEST project already exists
        print("🔍 Checking if TEST software project exists...")
        projects_url = f"{jira_url.rstrip('/')}/rest/api/3/project/search"
        projects_response = requests.get(
            projects_url,
            headers=headers,
            auth=auth,
            params={"maxResults": 50}
        )

        existing_projects = []
        if projects_response.status_code == 200:
            projects_data = projects_response.json()
            existing_projects = [p.get('key') for p in projects_data.get('values', [])]

            if 'TEST' in existing_projects:
                print("✅ TEST project already exists (checking if it's software type with Epic support)")
                # We could check the project type here, but for now let's create a new one
            else:
                print(f"❌ TEST project not found, will create new one")

        # Create software project with Epic functionality using REST API
        print("🚀 Creating TEST software project with Epic support...")

        api_url = f"{jira_url.rstrip('/')}/rest/api/3/project"

        # Use a software template with Epic support
        project_payload = {
            "key": "TEST",
            "name": "Test Software Project for MCP",
            "projectTypeKey": "software",  # Software type for Epic support
            "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-simplified-scrum",  # Scrum template with Epics
            "description": "Test software project for MCP real API testing with Epic functionality. All test resources are tracked and cleaned up automatically.",
            "leadAccountId": account_id,  # Use account ID
            "assigneeType": "PROJECT_LEAD"
        }

        print(f"📤 Sending request to: {api_url}")
        print(f"📋 Project payload: {json.dumps(project_payload, indent=2)}")

        create_response = requests.post(
            api_url,
            headers=headers,
            auth=auth,
            json=project_payload,
            timeout=30
        )

        print(f"📊 Response status: {create_response.status_code}")

        if create_response.status_code == 201:  # Created
            created_project = create_response.json()
            print("✅ Successfully created TEST software project with Epic support!")
            print(f"📋 Project details:")
            print(f"   - ID: {created_project.get('id')}")
            print(f"   - Key: {created_project.get('key')}")
            print(f"   - Name: {created_project.get('name')}")
            print(f"   - Type: {created_project.get('projectTypeKey')}")
            print(f"   - Template: {created_project.get('projectTemplateKey')}")
            return True

        elif create_response.status_code == 400:  # Bad Request
            error_data = create_response.json()
            print(f"❌ Bad request: {error_data}")

            # Check specific error messages
            error_messages = str(error_data).lower()
            if "project with the same key" in error_messages:
                print("⚠️  Project with key 'TEST' already exists. Will try to verify Epic support.")
                return check_epic_support_in_existing_project(jira_url, jira_username, jira_api_token)
            elif "permission" in error_messages or "unauthorized" in error_messages:
                print("🚫 Permission denied. User may not have project creation rights.")
            else:
                print(f"❌ Validation error: {error_data}")

        elif create_response.status_code == 403:  # Forbidden
            print("🚫 Forbidden. User does not have permission to create projects.")

        elif create_response.status_code == 401:  # Unauthorized
            print("🚫 Unauthorized. Check your credentials.")

        else:
            print(f"❌ Failed to create project: {create_response.status_code}")
            print(f"Response: {create_response.text}")

        return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def check_epic_support_in_existing_project(jira_url, username, api_token, project_key="TEST"):
    """Check if existing TEST project has Epic support."""
    print(f"🔍 Checking Epic support in existing {project_key} project...")

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
                    print("✅ Epic issue type found in existing TEST project!")
                    return True

            print("❌ Epic issue type not found in existing TEST project")
            print("💡 The existing project might be a business type without Epic support")
            return False

        else:
            print(f"❌ Failed to check Epic support: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error checking Epic support: {e}")
        return False

def test_epic_creation(jira_url, username, api_token, project_key="TEST"):
    """Test creating an Epic in the project."""
    print(f"🧪 Testing Epic creation in {project_key} project...")

    api_url = f"{jira_url.rstrip('/')}/rest/api/3/issue"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    auth = (username, api_token)

    # Epic creation payload
    epic_payload = {
        "fields": {
            "summary": "Test Epic for MCP Validation",
            "description": "This is a test Epic created to verify Epic functionality works in the TEST project.",
            "issuetype": {
                "name": "Epic"
            },
            "project": {
                "key": project_key
            },
            "name": "MCP Test Epic"
        }
    }

    try:
        response = requests.post(api_url, headers=headers, auth=auth, json=epic_payload)

        if response.status_code == 201:
            epic_data = response.json()
            epic_key = epic_data.get('key')
            print(f"✅ Successfully created test Epic: {epic_key}")

            # Clean up the test Epic
            delete_url = f"{jira_url.rstrip('/')}/rest/api/3/issue/{epic_key}"
            delete_response = requests.delete(delete_url, headers=headers, auth=auth)
            if delete_response.status_code == 204:
                print(f"🧹 Cleaned up test Epic: {epic_key}")

            return True
        else:
            print(f"❌ Epic creation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error testing Epic creation: {e}")
        return False

def main():
    """Main function to create software project with Epic support."""
    print("🚀 Creating TEST software project with Epic functionality for MCP testing...")

    result = create_software_project_with_epics()

    if result:
        print("\n✅ SUCCESS: TEST software project with Epic support is ready!")
        print("🧪 Testing Epic creation...")

        # Test Epic creation
        jira_url = os.getenv("JIRA_URL")
        jira_username = os.getenv("JIRA_USERNAME")
        jira_api_token = os.getenv("JIRA_API_TOKEN")

        epic_test = test_epic_creation(jira_url, jira_username, jira_api_token)

        if epic_test:
            print("🎯 Epic functionality is working correctly!")
            print("🧪 You can now run all real API tests including Epic tests!")
        else:
            print("⚠️  Epic functionality may not be fully working")

        print("\n🎉 The real API tests should now pass with full Epic support!")
    else:
        print("\n❌ FAILED: Could not create TEST software project")
        print("📖 Please check the error messages above")

if __name__ == "__main__":
    main()