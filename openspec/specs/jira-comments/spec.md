## ADDED Requirements

### Requirement: Jira Issue Comments Retrieval Tool
The system SHALL provide a dedicated MCP tool to retrieve comments from Jira issues with configurable limits and automatic markdown conversion.

#### Scenario: Retrieve comments from existing issue
- **WHEN** a user requests comments for a valid Jira issue key using the jira_get_comments tool
- **THEN** the system SHALL return all comments in chronological order (oldest first)
- **AND** the system SHALL automatically convert Jira markup to Markdown format
- **AND** the system SHALL process user mentions properly
- **AND** the system SHALL format creation and update dates consistently
- **AND** the system SHALL support configurable comment limits between 1-1000

#### Scenario: Handle comments with HTML content
- **WHEN** retrieving comments that contain HTML markup
- **THEN** the system SHALL convert HTML content to readable text
- **AND** the system SHALL preserve the semantic meaning of the content

#### Scenario: Handle missing or invalid issue keys
- **WHEN** a user requests comments for an issue key that doesn't exist
- **THEN** the system SHALL return an appropriate error message
- **AND** the system SHALL log the error for debugging purposes

#### Scenario: Handle permission restrictions
- **WHEN** a user requests comments for an issue they don't have permission to access
- **THEN** the system SHALL return a permission error
- **AND** the system SHALL not expose any sensitive information

### Requirement: Comments Data Structure
The system SHALL return comments in a structured JSON format with comprehensive metadata.

#### Scenario: Return structured comment data
- **WHEN** successfully retrieving comments
- **THEN** the system SHALL return a JSON object containing the issue key, total comment count, and an array of comment objects
- **AND** each comment object SHALL include id, body (converted to markdown), created timestamp, updated timestamp, and author information
- **AND** the system SHALL handle cases where updated timestamp is not available

### Requirement: Integration with Existing Comment Infrastructure
The system SHALL integrate with existing comment management capabilities.

#### Scenario: Use existing comment retrieval methods
- **WHEN** implementing the jira_get_comments tool
- **THEN** the system SHALL integrate with the existing CommentsMixin.get_issue_comments method
- **AND** the system SHALL reuse existing comment processing logic
- **AND** the system SHALL maintain consistency with other comment-related tools

### Requirement: Tool Categorization and Filtering
The system SHALL properly categorize the comments tool for filtering purposes.

#### Scenario: Tool discovery and filtering
- **WHEN** tools are categorized or filtered by functionality
- **THEN** the jira_get_comments tool SHALL be tagged with appropriate categories
- **AND** the system SHALL identify it as a read-only operation
- **AND** the system SHALL make it discoverable alongside other Jira tools

### Requirement: Testing and Validation Support
The system SHALL provide comprehensive testing capabilities for the comments functionality.

#### Scenario: Test comment retrieval functionality
- **WHEN** testing the jira_get_comments tool
- **THEN** the system SHALL provide test scripts that validate both direct client methods and MCP server endpoints
- **AND** the system SHALL test with real Jira data when available
- **AND** the system SHALL validate comment structure and content processing

#### Scenario: Test comment creation alongside retrieval
- **WHEN** running comprehensive tests
- **THEN** the system SHALL optionally test adding comments (if not in read-only mode)
- **AND** the system SHALL verify that newly created comments can be retrieved
- **AND** the system SHALL clean up test data after validation

### Requirement: Compatibility Across Atlassian Instances
The system SHALL work consistently across different Atlassian deployment types.

#### Scenario: Retrieve comments from Cloud instances
- **WHEN** connecting to Atlassian Cloud instances
- **THEN** the system SHALL use appropriate authentication methods
- **AND** the system SHALL handle Cloud-specific API response formats

#### Scenario: Retrieve comments from Server/Data Center instances
- **WHEN** connecting to Atlassian Server/Data Center instances
- **THEN** the system SHALL use appropriate authentication methods including Bearer tokens for PATs
- **AND** the system SHALL handle Server/DC-specific API response formats

### Requirement: Error Handling and Logging
The system SHALL provide robust error handling and detailed logging.

#### Scenario: Handle API rate limiting
- **WHEN** encountering rate limiting from Jira APIs
- **THEN** the system SHALL implement appropriate retry logic
- **AND** the system SHALL log rate limiting events for monitoring

#### Scenario: Handle network connectivity issues
- **WHEN** experiencing network connectivity problems
- **THEN** the system SHALL provide clear error messages
- **AND** the system SHALL implement connection timeout handling