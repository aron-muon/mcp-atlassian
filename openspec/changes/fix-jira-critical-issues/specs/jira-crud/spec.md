## ADDED Requirements

### Requirement: JIRA Issue Creation with Field Validation
The system SHALL provide a robust JIRA issue creation tool with comprehensive field validation and correct API format handling.

#### Scenario: Create issue with priority using correct format
- **WHEN** a user creates an issue with priority parameter
- **THEN** the system SHALL validate the priority exists and retrieve its ID
- **AND** the system SHALL use the correct {"id": "priorityId"} format in the API payload
- **AND** the system SHALL reject invalid priorities with a helpful error message listing available priorities

#### Scenario: Create issue with comprehensive field validation
- **WHEN** a user creates an issue with multiple optional fields
- **THEN** the system SHALL validate each field against the project's configuration
- **AND** the system SHALL provide clear error messages for fields that are not available
- **AND** the system SHALL handle both accountId and username formats for user fields
- **AND** the system SHALL validate issue types against the project's available types

#### Scenario: Create issue without using deprecated endpoints
- **WHEN** the system needs to validate fields for issue creation
- **THEN** the system SHALL NOT use the deprecated /rest/api/3/issue/createmeta endpoint
- **AND** the system SHALL use /rest/api/3/field for available field information
- **AND** the system SHALL use /rest/api/3/project/{key}/issuetypes for issue type validation

### Requirement: JIRA Issue Update with Correct Field Formats
The system SHALL provide an issue update tool that handles field formats correctly and supports assignment operations.

#### Scenario: Update issue priority with correct format
- **WHEN** a user updates an issue's priority
- **THEN** the system SHALL validate the priority and convert to correct ID format
- **AND** the system SHALL use {"priority": {"id": "priorityId"}} format in the update payload
- **AND** the system SHALL handle priority updates without requiring field restructure

#### Scenario: Update issue with assignee assignment
- **WHEN** a user assigns an issue to a user
- **THEN** the system SHALL handle both accountId and username formats
- **AND** the system SHALL use the correct API endpoint for assignment operations
- **AND** the system SHALL support unassigning by setting accountId to null
- **AND** the system SHALL provide clear error messages for invalid user identifiers

#### Scenario: Update issue with multiple field changes
- **WHEN** a user updates multiple fields simultaneously
- **THEN** the system SHALL validate all fields before making the update
- **AND** the system SHALL use the correct nested {"fields": {...}} structure
- **AND** the system SHALL apply all changes atomically or fail cleanly

### Requirement: JIRA Issue Transition and Status Management
The system SHALL provide enhanced issue transition functionality with comprehensive status metadata.

#### Scenario: Get available transitions with status metadata
- **WHEN** a user requests available transitions for an issue
- **THEN** the system SHALL return all valid transitions with detailed metadata
- **AND** the system SHALL include status category information (To Do, In Progress, Done)
- **AND** the system SHALL provide color coding and visual indicators for status categories
- **AND** the system SHALL handle permission restrictions gracefully

#### Scenario: Execute issue transition with validation
- **WHEN** a user transitions an issue to a new status
- **THEN** the system SHALL validate the transition is available for the current status
- **AND** the system SHALL handle required fields for the transition
- **AND** the system SHALL provide clear error messages for invalid transitions

### Requirement: JIRA Field Validation and Metadata
The system SHALL provide comprehensive field validation capabilities using current API endpoints.

#### Scenario: Validate field availability for project
- **WHEN** validating fields for issue creation or updates
- **THEN** the system SHALL check field availability against project configuration
- **AND** the system SHALL use /rest/api/3/field to retrieve all available fields
- **AND** the system SHALL handle both always-available and configurable fields
- **AND** the system SHALL provide clear guidance when fields are not available

#### Scenario: Handle different field types correctly
- **WHEN** processing field values for API calls
- **THEN** the system SHALL format priority fields as {"id": "priorityId"}
- **AND** the system SHALL format user fields as {"accountId": "..."} or {"name": "..."}
- **AND** the system SHALL format date fields in ISO 8601 format
- **AND** the system SHALL handle array fields like components and labels correctly

### Requirement: JIRA API Endpoint Modernization
The system SHALL use current, non-deprecated API endpoints for all operations.

#### Scenario: Replace deprecated createmeta endpoint
- **WHEN** the system needs field metadata for issue creation
- **THEN** the system SHALL NOT use /rest/api/3/issue/createmeta (deprecated 2024-06-03)
- **AND** the system SHALL use /rest/api/3/field for field information
- **AND** the system SHALL use /rest/api/3/project/{key}/issuetypes for issue types
- **AND** the system SHALL handle validation through individual API calls

#### Scenario: Use dedicated endpoints for specific operations
- **WHEN** performing user assignment operations
- **THEN** the system SHALL use /rest/api/3/issue/{key}/assignee endpoint
- **AND** the system SHALL use the correct payload format for the dedicated endpoint
- **AND** the system SHALL fall back to field-based updates when appropriate