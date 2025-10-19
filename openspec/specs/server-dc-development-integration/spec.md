## MODIFIED Requirements

### Requirement: Server/Data Center Development Information API Compatibility
The system SHALL handle differences between Cloud and Server/Data Center development information APIs with automatic adaptation.

#### Scenario: Convert issue keys to numeric IDs for Server/DC APIs
- **WHEN** querying development information for Server/Data Center instances
- **THEN** the system SHALL automatically convert issue keys (e.g., LQC-25567) to numeric IDs (e.g., 2688920)
- **AND** the system SHALL use the numeric ID for Server/DC API endpoint calls
- **AND** the system SHALL handle the conversion process transparently without requiring user intervention

#### Scenario: Handle Cloud and Server/DC API endpoint differences
- **WHEN** retrieving development information from different instance types
- **THEN** the system SHALL use Cloud API endpoint `/rest/api/3/issue/{issueIdOrKey}/development` for Cloud instances
- **AND** the system SHALL use Server/DC legacy endpoint `/rest/dev-status/latest/issue/detail` for Server/Data Center instances
- **AND** the system SHALL fall back to legacy endpoint for Cloud instances when needed

#### Scenario: Manage API response format variations
- **WHEN** processing development information responses
- **THEN** the system SHALL handle different response formats between Cloud and Server/DC APIs
- **AND** the system SHALL normalize data structures to maintain consistent interface
- **AND** the system SHALL preserve provider-specific information when available

### Requirement: Server/DC Development Information Limitations Handling
The system SHALL gracefully handle limitations in Server/DC development information availability.

#### Scenario: Handle limited development data in Server/DC configurations
- **WHEN** Server/DC instances provide only summary-level development information
- **THEN** the system SHALL work with available summary data (counts of PRs, commits, states)
- **AND** the system SHALL inform users when detailed information is not accessible
- **AND** the system SHALL not fail when only summary information is available

#### Scenario: Check multiple endpoints for complete data
- **WHEN** detail endpoint returns empty or incomplete data
- **THEN** the system SHALL also check summary endpoint to confirm development data existence
- **AND** the system SHALL combine information from multiple endpoints when possible
- **AND** the system SHALL provide clear indication of data completeness

#### Scenario: Handle Bitbucket Server integration limitations
- **WHEN** Bitbucket Server integration doesn't fully expose data through REST API
- **THEN** the system SHALL identify configuration limitations through API response analysis
- **AND** the system SHALL suggest alternative approaches for accessing development information
- **AND** the system SHALL provide guidance on enabling full API access

### Requirement: Error Handling for Server/DC Development Information
The system SHALL provide robust error handling specific to Server/DC development information challenges.

#### Scenario: Handle issue key to ID conversion failures
- **WHEN** unable to convert issue keys to numeric IDs
- **THEN** the system SHALL provide clear error messages explaining the conversion requirement
- **AND** the system SHALL suggest troubleshooting steps for conversion issues
- **AND** the system SHALL log conversion failures for debugging purposes

#### Scenario: Handle missing development panel configuration
- **WHEN** Server/DC instances do not have development panel or integration configured
- **THEN** the system SHALL return empty development information with appropriate explanation
- **AND** the system SHALL not fail when development information is unavailable
- **AND** the system SHALL provide guidance on enabling development integrations

#### Scenario: Handle permission and access issues
- **WHEN** users lack permission to access development information
- **THEN** the system SHALL return appropriate permission errors
- **AND** the system SHALL not expose sensitive development data
- **AND** the system SHALL suggest permission configuration steps

### Requirement: Server/DC Authentication Integration
The system SHALL ensure proper authentication integration for Server/DC development information access.

#### Scenario: Authenticate with Server/DC using Personal Access Tokens
- **WHEN** accessing development information from Server/DC instances
- **THEN** the system SHALL use Bearer authentication for Personal Access Tokens
- **AND** the system SHALL ensure authentication is properly configured for development information endpoints
- **AND** the system SHALL handle authentication requirements specific to development information APIs

#### Scenario: Validate development information access permissions
- **WHEN** configuring authentication for development information access
- **THEN** the system SHALL validate that credentials have permission to access development data
- **AND** the system SHALL check for required scopes or permissions
- **AND** the system SHALL provide guidance on configuring appropriate access levels

### Requirement: Development Information Fallback and Recovery
The system SHALL provide fallback mechanisms when Server/DC development information is limited or unavailable.

#### Scenario: Fallback to summary information when detail is unavailable
- **WHEN** detailed development information cannot be retrieved
- **THEN** the system SHALL fallback to available summary information
- **AND** the system SHALL clearly indicate the level of detail available
- **AND** the system SHALL provide the most complete information possible

#### Scenario: Suggest alternative access methods
- **WHEN** Server/DC API limitations prevent complete development information retrieval
- **THEN** the system SHALL suggest alternative approaches such as direct Bitbucket API access
- **AND** the system SHALL provide guidance on configuring alternative access methods
- **AND** the system SHALL document the limitations and possible solutions

### Requirement: Performance Optimization for Server/DC Integration
The system SHALL optimize performance when working with Server/DC development information APIs.

#### Scenario: Cache issue key to ID mappings
- **WHEN** frequently accessing development information for the same issues
- **THEN** the system SHALL cache issue key to numeric ID mappings
- **AND** the system SHALL avoid repeated conversion operations
- **AND** the system SHALL manage cache invalidation appropriately

#### Scenario: Handle Server/DC API rate limiting
- **WHEN** encountering rate limiting from Server/DC development information APIs
- **THEN** the system SHALL implement appropriate retry logic
- **AND** the system SHALL respect rate limit headers and backoff requirements
- **AND** the system SHALL provide clear feedback about rate limiting situations

### Requirement: Configuration and Troubleshooting Support
The system SHALL provide comprehensive configuration and troubleshooting support for Server/DC development information.

#### Scenario: Provide Server/DC configuration guidance
- **WHEN** setting up development information access for Server/DC instances
- **THEN** the system SHALL provide detailed configuration instructions
- **AND** the system SHALL document required permissions and settings
- **AND** the system SHALL include troubleshooting steps for common issues

#### Scenario: Diagnose Server/DC integration issues
- **WHEN** experiencing problems with Server/DC development information access
- **THEN** the system SHALL provide diagnostic tools and logging
- **AND** the system SHALL help identify configuration vs. API limitation issues
- **AND** the system SHALL suggest specific corrective actions based on error types

### Requirement: Integration with Direct Provider APIs
The system SHALL support integration with direct development provider APIs when Server/DC limitations are encountered.

#### Scenario: Support direct Bitbucket API integration
- **WHEN** Server/DC development information is limited
- **THEN** the system SHALL support direct Bitbucket API access as alternative
- **AND** the system SHALL provide tools for searching pull requests by issue key
- **AND** the system SHALL integrate Bitbucket API results with existing development information structures

#### Scenario: Aggregate development information from multiple sources
- **WHEN** development information is available from multiple providers
- **THEN** the system SHALL aggregate information from all available sources
- **AND** the system SHALL deduplicate and merge related development activities
- **AND** the system SHALL provide comprehensive development timelines across providers

### Requirement: Server/DC Plugin and Integration Detection
The system SHALL detect and report the status of development information plugins and integrations.

#### Scenario: Detect available development integrations
- **WHEN** accessing development information from Server/DC instances
- **THEN** the system SHALL detect which development integrations are configured (Bitbucket, GitHub, GitLab)
- **AND** the system SHALL report integration status and capabilities
- **AND** the system SHALL adapt behavior based on available integrations

#### Scenario: Report integration configuration status
- **WHEN** development information is incomplete or missing
- **THEN** the system SHALL report the status of development integration configuration
- **AND** the system SHALL identify missing or misconfigured integrations
- **AND** the system SHALL provide guidance on resolving integration issues