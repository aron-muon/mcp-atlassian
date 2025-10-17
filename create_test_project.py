#!/usr/bin/env python3
"""
Script to create TEST project in Jira for MCP testing.
"""

import asyncio
import json
import os
from atlassian.jira import Jira
from dotenv import load_dotenv

load_dotenv()

async def create_test_jira_project():
    """Create TEST project in Jira if it doesn't exist."""

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

    # Create Jira client
    jira = Jira(
        url=jira_url,
        username=jira_username,
        password=jira_api_token,
        cloud=True
    )

    try:
        # Check if TEST project already exists
        print("🔍 Checking if TEST project exists...")
        projects = jira.get_all_projects()

        # Handle different response formats
        if isinstance(projects, list):
            existing_projects = [p.get('key') for p in projects if isinstance(p, dict)]
        elif isinstance(projects, dict) and 'projects' in projects:
            existing_projects = [p.get('key') for p in projects['projects'] if isinstance(p, dict)]
        else:
            existing_projects = []

        if 'TEST' in existing_projects:
            print("✅ TEST project already exists")
            return True

        print("❌ TEST project not found")
        print("📋 Available projects:", existing_projects)

        # Check if we can create projects via API
        print("\n🔍 Checking project creation permissions...")

        # Try to get project creation metadata
        try:
            creation_meta = jira.get_project_creation_meta()
            print("✅ Project creation metadata accessible")

            # Get available project types
            project_types = creation_meta.get('projectTypes', [])
            if project_types:
                print(f"📋 Available project types: {[pt.get('key') for pt in project_types]}")

                # Look for a simple project type (like business, kanban, etc.)
                suitable_type = None
                for pt in project_types:
                    if pt.get('key') in ['business', 'kanban', 'scrum', 'basic']:
                        suitable_type = pt.get('key')
                        break

                if suitable_type:
                    print(f"🎯 Using project type: {suitable_type}")

                    # Try to create the project
                    print("🚀 Attempting to create TEST project...")

                    project_payload = {
                        "name": "Test Project for MCP",
                        "key": "TEST",
                        "projectTypeKey": suitable_type,
                        "projectTemplateKey": "com.atlassian.jira-core-project-templates:jira-core-project-management",  # Basic template
                        "description": "Test project for MCP real API testing. All test resources are tracked and cleaned up automatically.",
                        "lead": jira_username,
                        "assigneeType": "PROJECT_LEAD"
                    }

                    try:
                        created_project = jira.create_project(project_payload)
                        print("✅ Successfully created TEST project!")
                        print(f"📋 Project details: {json.dumps(created_project, indent=2)}")
                        return True

                    except Exception as e:
                        print(f"❌ Failed to create project: {e}")
                        if "403" in str(e):
                            print("🚫 Permission denied. Cannot create projects via API.")
                        elif "project with the same key" in str(e).lower():
                            print("⚠️  Project with key 'TEST' might already exist or was recently deleted")
                        return False
                else:
                    print("❌ No suitable project type found for creation")
                    return False
            else:
                print("❌ No project types available for creation")
                return False

        except Exception as e:
            print(f"❌ Cannot access project creation metadata: {e}")
            return False

    except Exception as e:
        print(f"❌ Error connecting to Jira: {e}")
        return False

def main():
    """Main function to create TEST project."""
    print("🚀 Creating TEST project in Jira for MCP testing...")

    result = asyncio.run(create_test_jira_project())

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
        print("      - Type: Any (Kanban, Scrum, Business, etc.)")
        print("   3. Ensure your test user has full access to the project")

if __name__ == "__main__":
    main()