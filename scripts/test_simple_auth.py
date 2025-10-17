#!/usr/bin/env python3
"""
Simple test script to verify authentication setup works.
"""
import os
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
                print(f"Loaded: {key.strip()}")

# Test the authentication
def test_jira_auth():
    """Test Jira authentication."""
    from src.mcp_atlassian.jira.config import JiraConfig
    import requests

    print("\n=== Testing Jira Authentication ===")

    # Check environment variables
    required_vars = ["JIRA_URL", "JIRA_USERNAME", "JIRA_API_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Missing environment variables: {missing_vars}")
        return False

    try:
        config = JiraConfig.from_env()

        print(f"URL: {config.url}")
        print(f"Username: {config.username}")
        print(f"Has API Token: {'Yes' if config.api_token else 'No'}")
        print(f"Auth Type: {config.auth_type}")

        # Test basic auth session
        session = requests.Session()
        session.auth = (config.username, config.api_token)
        response = session.get(f"{config.url}rest/api/3/myself")
        print(f"Auth test status: {response.status_code}")

        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Connected as: {user_data.get('displayName', 'Unknown')}")
            return True
        else:
            print(f"❌ Authentication failed: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_confluence_auth():
    """Test Confluence authentication."""
    from src.mcp_atlassian.confluence.config import ConfluenceConfig
    import requests

    print("\n=== Testing Confluence Authentication ===")

    # Check environment variables
    required_vars = ["CONFLUENCE_URL", "CONFLUENCE_USERNAME", "CONFLUENCE_API_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Missing environment variables: {missing_vars}")
        return False

    try:
        config = ConfluenceConfig.from_env()

        print(f"URL: {config.url}")
        print(f"Username: {config.username}")
        print(f"Has API Token: {'Yes' if config.api_token else 'No'}")
        print(f"Auth Type: {config.auth_type}")

        # Test basic auth session
        session = requests.Session()
        session.auth = (config.username, config.api_token)
        response = session.get(f"{config.url}rest/api/user/current")
        print(f"Auth test status: {response.status_code}")

        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Connected as: {user_data.get('displayName', 'Unknown')}")
            return True
        else:
            print(f"❌ Authentication failed: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing MCP Atlassian Authentication Setup")
    print("=" * 50)

    jira_ok = test_jira_auth()
    confluence_ok = test_confluence_auth()

    print("\n" + "=" * 50)
    if jira_ok and confluence_ok:
        print("✅ All authentication tests passed!")
        print("Your API token is working correctly.")
    elif jira_ok:
        print("⚠️  Jira authentication works, but Confluence failed")
    elif confluence_ok:
        print("⚠️  Confluence authentication works, but Jira failed")
    else:
        print("❌ Both authentication tests failed")