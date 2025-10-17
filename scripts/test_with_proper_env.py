#!/usr/bin/env python3
"""
Test script that sets up proper environment variables for tests.
"""
import os
import sys
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

# Set additional test environment variables that might be needed
os.environ["JIRA_TEST_PROJECT_KEY"] = "TEST"  # You can change this to your actual project
os.environ["JIRA_TEST_ISSUE_KEY"] = "TEST-1"  # You can change this to an actual issue
os.environ["JIRA_TEST_EPIC_KEY"] = "TEST-1"  # You can change this to an actual epic
os.environ["CONFLUENCE_TEST_SPACE_KEY"] = "TEST"  # You can change this to your actual space
os.environ["CONFLUENCE_TEST_PAGE_ID"] = "123456"  # You can change this to an actual page

print("Environment variables set for testing:")
print(f"JIRA_URL: {os.getenv('JIRA_URL')}")
print(f"JIRA_USERNAME: {os.getenv('JIRA_USERNAME')}")
print(f"JIRA_API_TOKEN: {'SET' if os.getenv('JIRA_API_TOKEN') else 'NOT SET'}")
print(f"CONFLUENCE_URL: {os.getenv('CONFLUENCE_URL')}")
print(f"CONFLUENCE_USERNAME: {os.getenv('CONFLUENCE_USERNAME')}")
print(f"CONFLUENCE_API_TOKEN: {'SET' if os.getenv('CONFLUENCE_API_TOKEN') else 'NOT SET'}")

# Run the pytest command with the proper environment
if __name__ == "__main__":
    import subprocess

    # Run a simple test to verify Jira authentication works
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_real_api_validation.py::test_jira_get_issue_link_types",
        "-v"
    ]

    print(f"\nRunning command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
    print(f"Return code: {result.returncode}")