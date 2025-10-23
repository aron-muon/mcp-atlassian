## ADDED Requirements

### Requirement: JIRA User Search Functionality
The system SHALL provide comprehensive user search capabilities specifically for JIRA users, not relying on Confluence user search.

#### Scenario: Search users by name or partial match
- **WHEN** a user searches for other JIRA users with a query string
- **THEN** the system SHALL use /rest/api/3/user/search endpoint
- **AND** the system SHALL return users matching the query by name, username, or email
- **AND** the system SHALL support pagination with configurable limits (default 50, max 1000)
- **AND** the system SHALL include user metadata like accountId, displayName, and email

#### Scenario: Search users with pagination
- **WHEN** a user needs to browse through large user lists
- **THEN** the system SHALL support startAt parameter for pagination
- **AND** the system SHALL return total count for UI pagination controls
- **AND** the system SHALL handle rate limiting gracefully for large searches

#### Scenario: Search users with filtering
- **WHEN** a user needs to find users with specific criteria
- **THEN** the system SHALL support filtering by active status
- **AND** the system SHALL support filtering by project membership if available
- **AND** the system SHALL provide relevant user context (groups, roles) when available

### Requirement: JIRA User Details Retrieval
The system SHALL provide functionality to retrieve detailed user information by different identifiers.

#### Scenario: Get user details by accountId
- **WHEN** a user requests details for a specific accountId
- **THEN** the system SHALL use /rest/api/3/user endpoint with accountId parameter
- **AND** the system SHALL return complete user profile information
- **AND** the system SHALL include availability status and timezone information

#### Scenario: Get user details by username
- **WHEN** a user requests details by traditional username
- **THEN** the system SHALL use /rest/api/3/user endpoint with username parameter
- **AND** the system SHALL handle both modern Cloud (accountId) and legacy Server/DC formats
- **AND** the system SHALL provide deprecation warnings for username-based lookups

#### Scenario: Get user details by email
- **WHEN** a user requests details by email address
- **THEN** the system SHALL use /rest/api/3/user endpoint with email parameter
- **AND** the system SHALL validate email format before making the request
- **AND** the system SHALL handle cases where email is not found gracefully

### Requirement: JIRA User Assignment Operations
The system SHALL provide robust user assignment functionality with proper identifier handling.

#### Scenario: Assign issue using accountId
- **WHEN** a user assigns an issue using an accountId
- **THEN** the system SHALL use the correct format {"accountId": "..."} in the API payload
- **AND** the system SHALL validate the accountId exists and is accessible
- **AND** the system SHALL use the dedicated /rest/api/3/issue/{key}/assignee endpoint
- **AND** the system SHALL handle assignment permission errors gracefully

#### Scenario: Assign issue using username (legacy)
- **WHEN** a user assigns an issue using a traditional username
- **THEN** the system SHALL convert username to the correct format {"name": "..."}
- **AND** the system SHALL provide guidance to migrate to accountId format
- **AND** the system SHALL support both Cloud and Server/DC username formats

#### Scenario: Unassign issue or assign to default
- **WHEN** a user wants to unassign an issue or assign to default assignee
- **THEN** the system SHALL support setting accountId to null for unassignment
- **AND** the system SHALL support "-1" username for default assignee in Server/DC
- **AND** the system SHALL validate permission to unassign before proceeding

### Requirement: User Identifier Format Handling
The system SHALL provide intelligent handling of different user identifier formats across JIRA deployments.

#### Scenario: Detect and process accountId format
- **WHEN** the system receives a user identifier
- **THEN** the system SHALL detect accountId format (contains ':')
- **AND** the system SHALL use appropriate API parameters for accountId-based operations
- **AND** the system SHALL validate accountId format before API calls

#### Scenario: Handle legacy username formats
- **WHEN** the system receives a traditional username
- **THEN** the system SHALL use appropriate API parameters for username-based operations
- **AND** the system SHALL provide migration guidance to accountId format
- **AND** the system SHALL handle cases where username format is not supported

#### Scenario: Automatic format conversion
- **WHEN** a user provides an identifier in one format but API requires another
- **THEN** the system SHALL attempt to lookup the user and convert formats
- **AND** the system SHALL cache user lookups to improve performance
- **AND** the system SHALL provide clear error messages when conversion fails

### Requirement: User Search Performance and Caching
The system SHALL provide efficient user search with appropriate caching strategies.

#### Scenario: Cache frequently accessed users
- **WHEN** the system retrieves user information
- **THEN** the system SHALL cache user details for a reasonable time period
- **AND** the system SHALL prioritize caching for frequently accessed users
- **AND** the system SHALL invalidate cache when user information changes

#### Scenario: Handle large user directories efficiently
- **WHEN** searching in organizations with many users
- **THEN** the system SHALL implement efficient pagination strategies
- **AND** the system SHALL provide search result limits to prevent performance issues
- **AND** the system SHALL implement rate limiting for search operations

### Requirement: Cross-Platform User Compatibility
The system SHALL work consistently across different JIRA deployment types and authentication methods.

#### Scenario: Handle Cloud user directories
- **WHEN** connected to JIRA Cloud instances
- **THEN** the system SHALL use accountId-based user operations
- **AND** the system SHALL handle Atlassian Account integration properly
- **AND** the system SHALL support Cloud-specific user attributes

#### Scenario: Handle Server/Data Center user directories
- **WHEN** connected to JIRA Server/Data Center instances
- **THEN** the system SHALL support both username and accountId formats
- **AND** the system SHALL handle LDAP and internal directory integration
- **AND** the system SHALL support Server/DC-specific user management features

#### Scenario: Handle Bearer token authentication for users
- **WHEN** using Personal Access Tokens for authentication
- **THEN** the system SHALL properly handle user identification in Bearer token context
- **AND** the system SHALL validate token permissions for user operations
- **AND** the system SHALL handle token-specific user context correctly