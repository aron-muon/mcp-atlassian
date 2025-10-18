#!/usr/bin/env python3
"""
Script to create TEST project in Jira for MCP testing using JSON REST API with scrum template for epics.
"""

import asyncio
import json
import os
import base64
import aiohttp
from dotenv import load_dotenv

load_dotenv()

async def create_test_jira_project():
    """Create TEST project in Jira if it doesn't exist, using scrum template for epics support."""

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

    # Create authentication header
    auth_string = f"{jira_username}:{jira_api_token}"
    auth_header = base64.b64encode(auth_string.encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        try:
            # Check if TST project exists and verify it's the correct type
            print("🔍 Checking TST project...")
            async with session.get(f"{jira_url}/rest/api/3/project/TST", headers=headers) as response:
                if response.status == 200:
                    project_info = await response.json()
                    project_type = project_info.get('projectTypeKey', '')
                    project_name = project_info.get('name', '')
                    print(f"✅ TST project exists: {project_name} (type: {project_type})")

                    # Check if it's the correct type (software with scrum template)
                    if project_type == 'software':
                        print("✅ TST project is already a software project")

                        # Verify epics support
                        epics_response = await session.get(f"{jira_url}/rest/api/3/issue/createmeta/TST/issuetypes", headers=headers)
                        if epics_response.status == 200:
                            createmeta = await epics_response.json()
                            issue_types = createmeta.get('issueTypes', [])
                            epic_types = [it for it in issue_types if it['name'].lower() == 'epic']

                            if epic_types:
                                print("✅ TST project already has epics support")
                                return True
                            else:
                                print("⚠️  TST project exists but doesn't have epics support")
                                print("🔄 Continuing with project recreation...")
                        else:
                            print("⚠️  Could not verify epics support in TST project")
                            print("🔄 Continuing with project recreation...")

                        # Delete the existing project to recreate with proper epics support
                        print("🗑️  Deleting existing TST project to recreate with scrum template...")
                        delete_response = await session.delete(f"{jira_url}/rest/api/3/project/TST", headers=headers)
                        if delete_response.status == 204:
                            print("✅ Successfully deleted existing TST project")
                            await asyncio.sleep(3)
                        else:
                            text = await delete_response.text()
                            print(f"❌ Failed to delete project: {delete_response.status} - {text}")
                            return False
                    else:
                        print(f"⚠️  TST project exists but is not a software project (type: {project_type})")
                        print("🔄 This should not happen. Stopping to avoid data loss.")
                        return False

                elif response.status == 404:
                    print("✅ TST project not found - proceeding with creation")
                else:
                    print(f"⚠️  Unexpected status checking TST project: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False

            # Now proceed with creating the new TST project if needed
            print("\n🚀 Creating TST project with scrum template for epics support...")

            # Get user account ID first
            print("🔍 Getting user account ID...")
            async with session.get(f"{jira_url}/rest/api/3/myself", headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    print(f"❌ Failed to get user info: {response.status} - {text}")
                    return False

                user_info = await response.json()
                account_id = user_info.get('accountId')
                print(f"✅ User account ID: {account_id}")

            # Project creation payload with scrum template
            project_payload = {
                "key": "TST",
                "name": "Software Dev Test - MCP Atlassian",
                "description": "Software development focused test space for MCP Atlassian testing with epics support",
                "projectTypeKey": "software",
                "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-simplified-agility-scrum",
                "leadAccountId": account_id,
                "assigneeType": "PROJECT_LEAD"
            }

            print(f"📋 Project creation payload:")
            print(json.dumps(project_payload, indent=2))

            # Create the project
            async with session.post(f"{jira_url}/rest/api/3/project",
                                   headers=headers,
                                   json=project_payload) as response:

                if response.status == 201:
                    result = await response.json()
                    print("✅ Successfully created TEST project!")
                    print(f"📋 Project details: {json.dumps(result, indent=2)}")

                    # Wait a moment for the project to be fully set up
                    await asyncio.sleep(2)

                    return True
                else:
                    text = await response.text()
                    print(f"❌ Failed to create project: {response.status}")
                    print(f"Response: {text}")

                    if "403" in str(response.status):
                        print("🚫 Permission denied. Cannot create projects via API.")
                    elif "project with the same key" in text.lower():
                        print("⚠️  Project with key 'TEST' might already exist or was recently deleted")
                    return False

        except aiohttp.ClientError as e:
            print(f"❌ Network error connecting to Jira: {e}")
            return False
        except Exception as e:
            print(f"❌ Error creating project: {e}")
            return False

async def verify_epics_support(jira_url, headers):
    """Verify that epics functionality is available in the TEST project"""

    print("\n🔍 Verifying epics support in TEST project...")

    async with aiohttp.ClientSession() as session:
        try:
            # Check if epics issue type exists in the project
            async with session.get(f"{jira_url}/rest/api/3/issue/createmeta/TST/issuetypes", headers=headers) as response:
                if response.status == 200:
                    createmeta = await response.json()
                    issue_types = createmeta.get('issueTypes', [])
                    epic_types = [it for it in issue_types if it['name'].lower() == 'epic']

                    if epic_types:
                        print(f"✅ Epic issue type found: {epic_types[0]['name']}")
                        return True
                    else:
                        print("❌ No Epic issue type found in TEST project")
                        print("📋 Available issue types:")
                        for it in issue_types:
                            print(f"   - {it['name']}")
                        return False
                else:
                    text = await response.text()
                    print(f"❌ Failed to check issue types: {response.status} - {text}")
                    return False

        except Exception as e:
            print(f"❌ Error checking epics support: {e}")
            return False


async def main():
    """Main function to create TEST project."""
    print("🚀 Creating Software Development TEST Project with Epics Support")
    print("=" * 60)

    # Load configuration for verification
    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    result = await create_test_jira_project()

    if result:
        print("\n✅ Successfully created TEST project!")

        # Verify epics functionality
        auth_string = f"{jira_username}:{jira_api_token}"
        auth_header = base64.b64encode(auth_string.encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Accept": "application/json"
        }

        epics_supported = await verify_epics_support(jira_url, headers)

        if epics_supported:
            print("\n🎉 SUCCESS: TEST project is ready for MCP testing with epics support!")
            print("🧪 You can now run the real API tests with --use-real-data flag")
        else:
            print("\n⚠️  WARNING: TEST project created but epics support verification failed.")
            print("🧪 You can still run tests, but epic-specific features may not work.")
    else:
        print("\n❌ FAILED: Could not create TEST project")
        print("📖 Please manually create TEST project in Jira:")
        print("   1. Go to your Jira instance")
        print("   2. Create a new project with:")
        print("      - Project Key: TEST")
        print("      - Project Name: Software Development Test")
        print("      - Type: Software")
        print("      - Template: Scrum")
        print("   3. Ensure your test user has full access to the project")

if __name__ == "__main__":
    asyncio.run(main())