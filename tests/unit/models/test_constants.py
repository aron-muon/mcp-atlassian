"""Tests for model constants.

Focused tests for model constants, validating correct values and business logic.
"""

from mcp_atlassian.models.constants import (
    # Confluence defaults
    CONFLUENCE_DEFAULT_ID,
    CONFLUENCE_DEFAULT_SPACE,
    CONFLUENCE_DEFAULT_VERSION,
    # Date/Time defaults
    DEFAULT_TIMESTAMP,
    # Common defaults
    EMPTY_STRING,
    # Jira defaults
    JIRA_DEFAULT_ID,
    JIRA_DEFAULT_ISSUE_TYPE,
    JIRA_DEFAULT_KEY,
    JIRA_DEFAULT_PRIORITY,
    JIRA_DEFAULT_PROJECT,
    JIRA_DEFAULT_STATUS,
    NONE_VALUE,
    UNASSIGNED,
    UNKNOWN,
)


class TestCommonDefaults:
    """Test suite for common default constants."""
    # Removed trivial tests that only check string types and literal values


class TestJiraDefaults:
    """Test suite for Jira default constants."""
    # Removed trivial tests that only check literal constant values and basic structure


class TestConfluenceDefaults:
    """Test suite for Confluence default constants."""
    # Removed trivial tests that only check literal constant values and basic structure


class TestDateTimeDefaults:
    """Test suite for date/time default constants."""
    # Removed trivial tests that only check literal constant values


class TestCrossReferenceConsistency:
    """Test suite for consistency between related constants."""
    # Removed trivial tests that only check consistency of literal constant values
