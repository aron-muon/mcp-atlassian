#!/usr/bin/env python3
"""
Script to check TEST project issue types and set up Epic support.
"""

import asyncio
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def check_project_issue_types(jira_url, username, api_token, project_key="TEST"):
    """Check what issue types are available in the TEST project."""

    api_url = f"{jira_url.rstrip('/')}/rest/api/3/issue/createmeta/{project_key}/issuetypes"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    auth = (username, api_token)

    try:
        response = requests.get(api_url, headers=headers, auth=auth)
        print(f"📊 Issue types check status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Available issue types in TEST project:")

            for issue_type in data.get('values', []):
                name = issue_type.get('name', 'Unknown')
                description = issue_type.get('description', '')
                subtask = issue_type.get('subtask', False)

                print(f"  📋 {name} {'(Sub-task)' if subtask else ''}")
                if description:
                    print(f"     {description}")

            return data
        else:
            print(f"❌ Failed to get issue types: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error checking issue types: {e}")
        return None

def create_test_epic(jira_url, username, api_token, project_key="TEST"):
    """Try to create a test Epic in the TEST project."""

    api_url = f"{jira_url.rstrip('/')}/rest/api/3/issue"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    auth = (username, api_token)

    # Epic creation payload
    epic_payload = {
        "update": {},
        "fields": {
            "summary": "Test Epic for MCP Setup",
            "description": "This is a test Epic created to verify Epic functionality in the TEST project.",
            "issuetype": {
                "name": "Epic"
            },
            "project": {
                "key": project_key
            },
            # Epic specific fields - these might vary by Jira instance
            "name": "MCP Test Epic"
        }
    }

    try:
        print(f"🚀 Attempting to create test Epic...")
        print(f"📤 Payload: {json.dumps(epic_payload, indent=2)}")

        response = requests.post(api_url, headers=headers, auth=auth, json=epic_payload)
        print(f"📊 Epic creation status: {response.status_code}")

        if response.status_code == 201:  # Created
            epic_data = response.json()
            epic_key = epic_data.get('key')
            epic_id = epic_data.get('id')

            print("✅ Successfully created test Epic!")
            print(f"   📋 Epic Key: {epic_key}")
            print(f"   🆔 Epic ID: {epic_id}")

            return epic_key, epic_id

        elif response.status_code == 400:  # Bad Request
            error_data = response.json()
            print(f"❌ Epic creation failed: {error_data}")

            # Check for missing Epic functionality
            error_str = str(error_data).lower()
            if "epic" in error_str and ("not found" in error_str or "invalid" in error_str):
                print("⚠️  Epic issue type not available in TEST project")
                print("💡 The TEST project might need to be a 'software' type project for Epic support")

            return None, None

        else:
            print(f"❌ Unexpected error: {response.status_code} - {response.text}")
            return None, None

    except Exception as e:
        print(f"❌ Error creating Epic: {e}")
        return None, None

def check_epic_field_metadata(jira_url, username, api_token, project_key="TEST"):
    """Check Epic field requirements for the project."""

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
                    print("✅ Found Epic issue type!")

                    # Check required fields
                    fields = issue_type.get('fields', {})
                    required_fields = []

                    for field_key, field_data in fields.items():
                        if field_data.get('required', False):
                            field_name = field_data.get('name', field_key)
                            required_fields.append(field_name)
                            print(f"  🔧 Required field: {field_name}")

                    if not required_fields:
                        print("  ℹ️  No required fields for Epic creation")

                    return True

            print("❌ Epic issue type not found in TEST project")
            return False

        else:
            print(f"❌ Failed to check field metadata: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error checking Epic metadata: {e}")
        return False

def main():
    """Main function to set up Epic support in TEST project."""
    print("🔧 Setting up Epic support in TEST project...")

    # Load Jira configuration
    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_url, jira_username, jira_api_token]):
        print("❌ Missing Jira configuration in .env file")
        return

    print(f"🔗 Connecting to Jira: {jira_url}")

    # Step 1: Check available issue types
    print("\n📋 Step 1: Checking available issue types...")
    issue_types = check_project_issue_types(jira_url, jira_username, jira_api_token)

    if not issue_types:
        print("❌ Could not retrieve issue types")
        return

    # Step 2: Check Epic field requirements
    print("\n🔍 Step 2: Checking Epic field requirements...")
    has_epic = check_epic_field_metadata(jira_url, jira_username, jira_api_token)

    if not has_epic:
        print("\n❌ Epic functionality is not available in the TEST project")
        print("💡 This is expected for 'business' type projects")
        print("💡 To enable Epic functionality, you would need:")
        print("   1. A 'software' type project, OR")
        print("   2. Configure Epic issue type in the current project")
        return

    # Step 3: Try to create a test Epic
    print("\n🚀 Step 3: Attempting to create test Epic...")
    epic_key, epic_id = create_test_epic(jira_url, jira_username, jira_api_token)

    if epic_key:
        print(f"\n✅ SUCCESS: Epic support is working in TEST project!")
        print(f"🧪 Test Epic created: {epic_key}")
        print("🎯 The real API tests should now work for Epic functionality")
    else:
        print(f"\n❌ Epic creation failed")
        print("💡 The tests may need to be updated to handle projects without Epic support")

if __name__ == "__main__":
    main()