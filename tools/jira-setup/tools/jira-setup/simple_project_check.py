#!/usr/bin/env python3
"""
Simple script to check if we can use existing projects for testing.
"""

import os
from atlassian.jira import Jira
from dotenv import load_dotenv

load_dotenv()

def main():
    """Check existing Jira projects."""

    # Load Jira configuration
    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    print(f"🔗 Connecting to Jira: {jira_url}")

    # Create Jira client
    jira = Jira(
        url=jira_url,
        username=jira_username,
        password=jira_api_token,
        cloud=True
    )

    try:
        # Check existing projects
        print("🔍 Checking existing projects...")
        projects = jira.get_all_projects()

        if isinstance(projects, list):
            for project in projects:
                key = project.get('key', 'N/A')
                name = project.get('name', 'N/A')
                print(f"  📋 {key}: {name}")

        # Try to create a test issue in KAN project to see if it works
        print("\n🧪 Testing issue creation in KAN project...")

        test_summary = f"MCP Test Issue {os.urandom(4).hex()}"
        issue_data = {
            "summary": test_summary,
            "description": "Test issue for MCP validation",
            "issuetype": {"name": "Task"},
            "project": {"key": "KAN"}
        }

        try:
            issue = jira.create_issue(fields=issue_data)
            issue_key = issue.get('key')
            print(f"✅ Successfully created test issue: {issue_key}")

            # Clean up
            jira.delete_issue(issue_key)
            print(f"🧹 Cleaned up test issue: {issue_key}")

            print("\n✅ KAN project is accessible for testing!")
            print("💡 You can temporarily use KAN project for testing, or create TEST project manually.")

        except Exception as e:
            print(f"❌ Cannot create test issue in KAN: {e}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()