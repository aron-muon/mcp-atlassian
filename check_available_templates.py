#!/usr/bin/env python3
"""
Script to check available project templates in Jira.
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def check_available_templates():
    """Check what project templates are available in this Jira instance."""

    # Load Jira configuration
    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_url, jira_username, jira_api_token]):
        print("❌ Missing Jira configuration in .env file")
        return

    print(f"🔗 Connecting to Jira: {jira_url}")

    # Check available project templates
    api_url = f"{jira_url.rstrip('/')}/rest/api/3/project-template"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    auth = (jira_username, jira_api_token)

    try:
        print("🔍 Checking available project templates...")
        response = requests.get(api_url, headers=headers, auth=auth)
        print(f"📊 Template check status: {response.status_code}")

        if response.status_code == 200:
            templates = response.json()
            print(f"✅ Found {len(templates.get('values', []))} project templates")

            # Group templates by type
            software_templates = []
            business_templates = []
            service_desk_templates = []

            for template in templates.get('values', []):
                key = template.get('key', '')
                name = template.get('name', '')
                project_type = template.get('projectTypeKey', '')

                template_info = f"  📋 {name} ({key}) - Type: {project_type}"

                if 'software' in project_type.lower() or 'greenhopper' in key.lower():
                    software_templates.append(template_info)
                elif 'business' in project_type.lower() or 'core' in key.lower():
                    business_templates.append(template_info)
                elif 'service' in project_type.lower() or 'servicedesk' in key.lower():
                    service_desk_templates.append(template_info)

            print(f"\n🚀 Software Templates (with Epic support):")
            if software_templates:
                for template in software_templates:
                    print(template)
            else:
                print("  ❌ No software templates found")

            print(f"\n💼 Business Templates:")
            if business_templates:
                for template in business_templates:
                    print(template)
            else:
                print("  ❌ No business templates found")

            print(f"\n🎯 Service Desk Templates:")
            if service_desk_templates:
                for template in service_desk_templates:
                    print(template)
            else:
                print("  ❌ No service desk templates found")

            return templates

        else:
            print(f"❌ Failed to get templates: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error checking templates: {e}")
        return None

def create_project_with_epic_support(templates):
    """Try to create a project with Epic support using available templates."""

    if not templates:
        return False

    # Load Jira configuration
    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    # Find software templates (which have Epic support)
    software_templates = []
    for template in templates.get('values', []):
        project_type = template.get('projectTypeKey', '').lower()
        if 'software' in project_type:
            software_templates.append(template)

    if not software_templates:
        print("❌ No software templates available for Epic support")
        return False

    # Use the first available software template
    template = software_templates[0]
    template_key = template.get('key')
    template_name = template.get('name')

    print(f"🚀 Using software template: {template_name} ({template_key})")

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
    except Exception as e:
        print(f"❌ Error getting user info: {e}")
        return False

    # Create a project with a different key since TEST is taken
    project_key = "EPIC"  # Use EPIC instead of TEST

    api_url = f"{jira_url.rstrip('/')}/rest/api/3/project"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    project_payload = {
        "key": project_key,
        "name": "Epic Test Project for MCP",
        "projectTypeKey": "software",
        "projectTemplateKey": template_key,
        "description": "Test software project for MCP real API testing with Epic functionality.",
        "leadAccountId": account_id,
        "assigneeType": "PROJECT_LEAD"
    }

    try:
        print(f"📤 Creating {project_key} project with Epic support...")
        response = requests.post(api_url, headers=headers, auth=auth, json=project_payload, timeout=30)
        print(f"📊 Project creation status: {response.status_code}")

        if response.status_code == 201:
            project_data = response.json()
            print("✅ Successfully created project with Epic support!")
            print(f"📋 Project details:")
            print(f"   - Key: {project_data.get('key')}")
            print(f"   - Name: {project_data.get('name')}")
            print(f"   - Type: {project_data.get('projectTypeKey')}")
            return project_key
        else:
            print(f"❌ Failed to create project: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error creating project: {e}")
        return None

def main():
    """Main function to check templates and create Epic-enabled project."""
    print("🔍 Checking available Jira project templates for Epic support...")

    templates = check_available_templates()

    if templates:
        print(f"\n🚀 Attempting to create a project with Epic support...")
        epic_project_key = create_project_with_epic_support(templates)

        if epic_project_key:
            print(f"\n✅ SUCCESS: Created {epic_project_key} project with Epic support!")
            print("🎯 You can now use this project for Epic testing in MCP!")
        else:
            print(f"\n❌ Could not create project with Epic support")
    else:
        print(f"\n❌ Could not retrieve project templates")

if __name__ == "__main__":
    main()