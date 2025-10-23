## ADDED Requirements

### Requirement: JIRA Project Metadata Retrieval
The system SHALL provide comprehensive project metadata retrieval capabilities without using deprecated API endpoints.

#### Scenario: Get complete project configuration
- **WHEN** a user requests metadata for a specific project
- **THEN** the system SHALL retrieve basic project information using /rest/api/3/project/{key}
- **AND** the system SHALL get available issue types using /rest/api/3/project/{key}/issuetypes
- **AND** the system SHALL retrieve all available fields using /rest/api/3/field
- **AND** the system SHALL organize metadata in a structured, easy-to-consume format

#### Scenario: Get project-specific priority information
- **WHEN** a user needs priority information for a project
- **THEN** the system SHALL attempt to retrieve project-specific priority scheme
- **AND** the system SHALL fall back to global priorities if project-specific scheme is not available
- **AND** the system SHALL include priority IDs, names, descriptions, and default status
- **AND** the system SHALL use /rest/api/3/priority/search with project filtering when available

#### Scenario: Get project field configurations
- **WHEN** a user needs to understand field availability for a project
- **THEN** the system SHALL retrieve field configuration information where accessible
- **AND** the system SHALL identify which fields are always available vs configurable
- **AND** the system SHALL provide guidance on field usage and requirements
- **AND** the system SHALL handle cases where field configuration API is not available

### Requirement: JIRA Issue Type Validation and Information
The system SHALL provide comprehensive issue type validation and metadata retrieval.

#### Scenario: Validate issue types for project
- **WHEN** a user provides an issue type for creation or validation
- **THEN** the system SHALL retrieve all available issue types for the project
- **AND** the system SHALL validate the provided issue type exists and is accessible
- **AND** the system SHALL provide a list of valid issue types when validation fails
- **AND** the system SHALL handle both standard and custom issue types correctly

#### Scenario: Get detailed issue type information
- **WHEN** a user needs detailed information about an issue type
- **THEN** the system SHALL retrieve issue type metadata including icon, description, and subtask status
- **AND** the system SHALL identify required fields for the issue type
- **AND** the system SHALL provide workflow information when available
- **AND** the system SHALL handle hierarchical issue type relationships

#### Scenario: Handle issue type hierarchy
- **WHEN** working with projects that have subtasks
- **THEN** the system SHALL identify parent-child relationships between issue types
- **AND** the system SHALL validate that subtasks are only created under appropriate parent issues
- **AND** the system SHALL provide guidance on issue type usage in hierarchical contexts

### Requirement: JIRA Priority System Integration
The system SHALL provide comprehensive priority validation and retrieval capabilities.

#### Scenario: Validate and retrieve priority by name
- **WHEN** a user provides a priority name for issue creation or update
- **THEN** the system SHALL search for the priority using /rest/api/3/priority/search
- **AND** the system SHALL perform case-insensitive matching for priority names
- **AND** the system SHALL return the priority ID and complete metadata when found
- **AND** the system SHALL provide a list of available priorities when validation fails

#### Scenario: Validate and retrieve priority by ID
- **WHEN** a user provides a priority ID for issue operations
- **THEN** the system SHALL validate the priority ID exists and is accessible
- **AND** the system SHALL return the complete priority metadata
- **AND** the system SHALL handle both numeric and string priority ID formats

#### Scenario: Get project-specific priority schemes
- **WHEN** a user needs priority information specific to a project
- **THEN** the system SHALL attempt to retrieve priority scheme for the project
- **AND** the system SHALL use /rest/api/3/priorityscheme/project/{projectId} when available
- **AND** the system SHALL fall back to global priorities when project-specific scheme is not accessible
- **AND** the system SHALL identify default priorities for the project

### Requirement: JIRA Field Configuration Analysis
The system SHALL provide comprehensive field analysis and validation capabilities.

#### Scenario: Analyze available fields for JIRA instance
- **WHEN** the system needs to understand available fields
- **THEN** the system SHALL retrieve all fields using /rest/api/3/field
- **AND** the system SHALL categorize fields by type (system, custom, etc.)
- **AND** the system SHALL identify field schemas and allowed values
- **AND** the system SHALL cache field information to improve performance

#### Scenario: Validate field availability for projects
- **WHEN** validating fields for issue creation or updates
- **THEN** the system SHALL check if fields are available for the specific project
- **AND** the system SHALL handle always-available fields (summary, description, etc.)
- **AND** the system SHALL validate custom field availability against project configuration
- **AND** the system SHALL provide clear error messages for unavailable fields

#### Scenario: Handle field schema and validation
- **WHEN** processing field values for API operations
- **THEN** the system SHALL understand field schema types and requirements
- **AND** the system SHALL validate field values against schema constraints
- **AND** the system SHALL handle complex field types (cascading selects, multi-selects, etc.)
- **AND** the system SHALL format field values correctly for API consumption

### Requirement: JIRA Project Configuration Caching
The system SHALL provide efficient caching strategies for project metadata to improve performance.

#### Scenario: Cache project metadata effectively
- **WHEN** retrieving project metadata
- **THEN** the system SHALL cache project information with appropriate expiration
- **AND** the system SHALL prioritize caching for frequently accessed projects
- **AND** the system SHALL invalidate cache when project configuration changes
- **AND** the system SHALL provide cache statistics and management options

#### Scenario: Handle cache invalidation gracefully
- **WHEN** project configuration changes are detected
- **THEN** the system SHALL invalidate relevant cache entries
- **AND** the system SHALL handle partial cache invalidation for specific data types
- **AND** the system SHALL provide mechanisms to manually refresh cached data
- **AND** the system SHALL log cache operations for debugging and monitoring

### Requirement: Cross-Instance Metadata Compatibility
The system SHALL handle metadata differences across JIRA deployment types consistently.

#### Scenario: Handle Cloud-specific metadata
- **WHEN** connected to JIRA Cloud instances
- **THEN** the system SHALL handle Cloud-specific project features (next-gen projects)
- **AND** the system SHALL process Cloud-specific field types and configurations
- **AND** the system SHALL adapt to Cloud API response formats and limitations
- **AND** the system SHALL support Cloud-specific project types and workflows

#### Scenario: Handle Server/Data Center metadata
- **WHEN** connected to JIRA Server/Data Center instances
- **THEN** the system SHALL support classic project configurations
- **AND** the system SHALL handle Server/DC-specific field types and schemes
- **AND** the system SHALL adapt to Server/DC API response formats
- **AND** the system SHALL support advanced administration features when available

#### Scenario: Handle mixed-environment scenarios
- **WHEN** the system operates across multiple JIRA instances
- **THEN** the system SHALL adapt metadata handling to each instance's capabilities
- **AND** the system SHALL provide consistent abstraction over instance differences
- **AND** the system SHALL handle version-specific API differences gracefully
- **AND** the system SHALL provide clear error messages for unsupported features