#!/usr/bin/env python3
"""
Script to create TEST project in Jira using REST API directly.
"""

import asyncio
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def create_test_jira_project():
    """Create TEST project in Jira using REST API."""

    # Load Jira configuration
    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_url, jira_username, jira_api_token]):
        print("❌ Missing Jira configuration in .env file")
        print(f"JIRA_URL: {'✅' if jira_url else '❌'}")
        print(f"JIRA_USERNAME: {'✅' if jira_username else '❌'}")
        print(f"JIRA_API_TOKEN: {'✅' if jira_api_token else '❌'}")
        return False

    print(f"🔗 Connecting to Jira: {jira_url}")

    # Prepare REST API endpoint
    api_url = f"{jira_url.rstrip('/')}/rest/api/3/project"

    # Headers for authentication
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Basic auth
    auth = (jira_username, jira_api_token)

    try:
        # First, check if TEST project already exists
        print("🔍 Checking if TEST project exists...")
        projects_url = f"{jira_url.rstrip('/')}/rest/api/3/project/search"
        projects_response = requests.get(
            projects_url,
            headers=headers,
            auth=auth,
            params={"maxResults": 50}
        )

        if projects_response.status_code == 200:
            projects_data = projects_response.json()
            existing_projects = [p.get('key') for p in projects_data.get('values', [])]

            if 'TEST' in existing_projects:
                print("✅ TEST project already exists")
                return True
            else:
                print(f"❌ TEST project not found")
                print(f"📋 Available projects: {existing_projects}")
        else:
            print(f"⚠️  Could not check existing projects: {projects_response.status_code}")

        # Create TEST project using REST API
        print("🚀 Creating TEST project...")

        project_payload = {
            "key": "TEST",
            "name": "Test Project for MCP",
            "projectTypeKey": "business",  # Simple business type
            "description": "Test project for MCP real API testing. All test resources are tracked and cleaned up automatically.",
            "leadAccountId": jira_username  # Use current user as lead
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
            print("✅ Successfully created TEST project!")
            print(f"📋 Project details:")
            print(f"   - ID: {created_project.get('id')}")
            print(f"   - Key: {created_project.get('key')}")
            print(f"   - Name: {created_project.get('name')}")
            print(f"   - Type: {created_project.get('projectTypeKey')}")
            return True

        elif create_response.status_code == 400:  # Bad Request
            error_data = create_response.json()
            print(f"❌ Bad request: {error_data}")

            # Check specific error messages
            error_messages = str(error_data).lower()
            if "project with the same key" in error_messages:
                print("⚠️  Project with key 'TEST' might already exist")
                return True
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

def main():
    """Main function to create TEST project."""
    print("🚀 Creating TEST project in Jira for MCP testing using REST API...")

    result = create_test_jira_project()

    if result:
        print("\n✅ SUCCESS: TEST project is ready for MCP testing!")
        print("🧪 You can now run the real API tests with --use-real-data flag")
    else:
        print("\n❌ FAILED: Could not create TEST project")
        print("📖 Please manually create TEST project in Jira:")
        print("   1. Go to your Jira instance")
        print("   2. Create a new project with:")
        print("      - Project Key: TEST")
        print("      - Project Name: Test Project for MCP")
        print("      - Type: Business (or any type)")
        print("   3. Ensure your test user has full access to the project")

if __name__ == "__main__":
    main()