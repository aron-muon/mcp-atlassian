## Why
Consolidate all LLM-generated documentation into OpenSpec-compliant structure to maintain clear separation between upstream content and AI-generated specifications while following OpenSpec conventions. This reorganization ensures that all MCP commands and functionality are properly documented with requirements and scenarios that align with our mission of ensuring complete MCP command functionality.

## What Changes
- Extract development workflow content from AGENTS.md and CLAUDE.md into development-workflow spec
- Convert feature documentation (JIRA_GET_COMMENTS.md, DEVELOPMENT_INFO.md, etc.) into proper specs with requirements and scenarios
- Convert fix documentation (AUTH_FIX.md, SERVER_DC_DEV_INFO_FIX.md) into MODIFIED requirements
- Organize offline deployment and testing documentation into specs
- Clean up root directory to contain only upstream files and OpenSpec managed blocks
- Create comprehensive specs that ensure all MCP commands are fully documented and validated

## Impact
- Affected specs: New specs for jira-comments, development-information, authentication-bearer-tokens, server-dc-development-integration, offline-deployment, live-testing, development-workflow
- Affected code: No code changes, only documentation reorganization
- **BREAKING**: Root directory AGENTS.md and CLAUDE.md now contain only OpenSpec managed blocks
- Mission alignment: All MCP commands will have comprehensive specifications ensuring full functionality coverage