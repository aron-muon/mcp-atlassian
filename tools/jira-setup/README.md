# JIRA Setup Tools

This directory contains scripts for setting up JIRA projects and testing infrastructure for MCP Atlassian development.

## Project Creation Scripts

### Core Setup Scripts
- **`check_available_templates.py`** - Checks available JIRA project templates and identifies which ones support Epic functionality
- **`create_software_project_with_epics.py`** - Creates a software project with Epic support using Scrum template
- **`create_epic_project_simple.py`** - Simplified version for creating software projects with Epic functionality
- **`setup_epic_support.py`** - Tests and sets up Epic support in existing projects

### Test Project Setup
- **`create_test_project.py`** - Creates TEST project using async API with scrum template for epics
- **`create_test_project_api.py`** - Creates TEST project using REST API (fixed version)
- **`create_test_project.json`** - Configuration file for TEST project creation
- **`simple_project_check.py`** - Simple script to check existing projects and test basic functionality

## Usage

All scripts require proper JIRA credentials configured in your `.env` file:

```bash
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your-api-token
```

## Recommendations

For most use cases:
1. Use `check_available_templates.py` first to see what templates are available
2. Use `create_software_project_with_epics.py` to create a project with full Epic support
3. Use `setup_epic_support.py` to verify Epic functionality is working

The scripts are organized to provide different approaches for the same goal, allowing you to choose the method that works best for your JIRA instance and permissions.