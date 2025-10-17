#!/usr/bin/env python3
"""
Test script to validate the automated test setup functionality.
"""

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.utils.test_setup import setup_test_environment, TestProjectSetup


async def test_setup():
    """Test the automated test setup."""
    print("🚀 Starting automated test setup validation...")

    try:
        # Test Jira setup
        print("\n📋 Setting up Jira test environment...")
        setup = TestProjectSetup()
        project_key = await setup.setup_jira_test_environment(create_project=False)
        print(f"✅ Jira test project ready: {project_key}")

        # Test Confluence setup
        print("\n📄 Setting up Confluence test environment...")
        space_key = await setup.setup_confluence_test_environment(create_space=False)
        print(f"✅ Confluence test space ready: {space_key}")

        # Test the combined setup function
        print("\n🔄 Testing combined setup function...")
        combined_setup = await setup_test_environment(
            jira=True,
            confluence=True,
            create_jira_project=False,
            create_confluence_space=False
        )

        print(f"✅ Combined setup ready:")
        print(f"   Jira Project: {combined_setup.get_jira_project_key()}")
        print(f"   Confluence Space: {combined_setup.get_confluence_space_key()}")

        # Cleanup
        print("\n🧹 Cleaning up test resources...")
        await combined_setup.cleanup_test_environment()
        await setup.cleanup_test_environment()

        print("\n✅ Test setup validation completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Test setup validation failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_setup())
    sys.exit(0 if success else 1)