#!/usr/bin/env python3
"""
Live test runner for MCP Atlassian functions.

This script provides a convenient way to run the live MCP tests that
interact with real Jira and Confluence instances.

Usage:
    python tests/run_live_tests.py --help
    python tests/run_live_tests.py --jira-only
    python tests/run_live_tests.py --confluence-only
    python tests/run_live_tests.py --cleanup-after
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def check_environment():
    """Check if required environment variables are set."""
    missing_vars = []

    # Check for Jira environment
    jira_vars = ["JIRA_URL", "JIRA_TEST_PROJECT_KEY"]
    if not any(os.getenv(var) for var in ["JIRA_USERNAME", "JIRA_API_TOKEN", "JIRA_PERSONAL_TOKEN"]):
        missing_vars.extend(jira_vars + ["JIRA_USERNAME or JIRA_API_TOKEN or JIRA_PERSONAL_TOKEN"])
    elif not os.getenv("JIRA_URL"):
        missing_vars.append("JIRA_URL")

    # Check for Confluence environment
    confluence_vars = ["CONFLUENCE_URL", "CONFLUENCE_TEST_SPACE_KEY"]
    if not any(os.getenv(var) for var in ["CONFLUENCE_USERNAME", "CONFLUENCE_API_TOKEN", "CONFLUENCE_PERSONAL_TOKEN"]):
        missing_vars.extend(confluence_vars + ["CONFLUENCE_USERNAME or CONFLUENCE_API_TOKEN or CONFLUENCE_PERSONAL_TOKEN"])
    elif not os.getenv("CONFLUENCE_URL"):
        missing_vars.append("CONFLUENCE_URL")

    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in sorted(set(missing_vars)):
            print(f"   - {var}")
        print("\nPlease set up your .env file with proper Atlassian credentials.")
        print("See CLAUDE.md for configuration instructions.")
        return False

    return True


def run_tests(test_type="all", cleanup_after=False, verbose=False):
    """Run the specified type of live tests."""
    project_root = Path(__file__).parent.parent
    test_files = []

    if test_type in ["all", "jira"]:
        test_files.append("tests/integration/test_jira_mcp_live.py")
    if test_type in ["all", "confluence"]:
        test_files.append("tests/integration/test_confluence_mcp_live.py")

    if not test_files:
        print("❌ No test files specified")
        return False

    # Build pytest command
    cmd = [
        sys.executable, "-m", "pytest",
        "--integration",
        "--use-real-data",
        "-v" if verbose else "-q",
        "--tb=short",
    ] + test_files

    if cleanup_after:
        cmd.extend(["--cleanup-after"])

    print(f"🚀 Running live tests for: {', '.join(test_files)}")
    print(f"📋 Command: {' '.join(cmd)}")
    print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    try:
        # Run the tests
        result = subprocess.run(cmd, cwd=project_root, capture_output=False)

        print("-" * 60)
        if result.returncode == 0:
            print("✅ All live tests passed!")
        else:
            print("❌ Some tests failed. Check the output above for details.")

        return result.returncode == 0

    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run live MCP Atlassian tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all live tests
  python tests/run_live_tests.py

  # Run only Jira tests
  python tests/run_live_tests.py --jira-only

  # Run only Confluence tests
  python tests/run_live_tests.py --confluence-only

  # Run with verbose output
  python tests/run_live_tests.py --verbose

  # Check environment without running tests
  python tests/run_live_tests.py --check-only
        """
    )

    parser.add_argument(
        "--jira-only",
        action="store_true",
        help="Run only Jira MCP function tests"
    )
    parser.add_argument(
        "--confluence-only",
        action="store_true",
        help="Run only Confluence MCP function tests"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose test output"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check environment setup, don't run tests"
    )

    args = parser.parse_args()

    print("🔍 MCP Atlassian Live Test Runner")
    print("=" * 40)

    # Check environment first
    if not check_environment():
        sys.exit(1)

    if args.check_only:
        print("✅ Environment check passed - ready to run live tests!")
        sys.exit(0)

    # Determine test type
    if args.jira_only and args.confluence_only:
        print("❌ Cannot specify both --jira-only and --confluence-only")
        sys.exit(1)
    elif args.jira_only:
        test_type = "jira"
    elif args.confluence_only:
        test_type = "confluence"
    else:
        test_type = "all"

    # Run the tests
    success = run_tests(
        test_type=test_type,
        verbose=args.verbose
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()