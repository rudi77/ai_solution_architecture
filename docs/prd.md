# AI Solution Architecture - Agent v2: Azure OpenAI Provider Support PRD

**Version:** 1.0
**Date:** 2025-11-12
**Author:** John (PM Agent)

---

## 1. Intro Project Analysis and Context

### Analysis Source
**IDE-based fresh analysis** - Working with provided source files

### Current Project State

Based on analysis of the LLM Service (`llm_service.py`) and configuration (`llm_config.yaml`):

**Current Capabilities:**
- Centralized LLM service supporting multiple OpenAI model families (GPT-4, GPT-4.1, GPT-5)
- Model-aware parameter mapping that automatically translates traditional parameters (temperature, top_p) to GPT-5 parameters (effort, reasoning)
- Configuration-driven model aliases (main, fast, powerful, legacy)
- Retry logic with exponential backoff for transient errors
- Comprehensive logging of token usage, latency, and parameter mapping
- Support for OpenAI provider via LiteLLM library

**Architecture:**
- Python-based service using async/await patterns
- LiteLLM as the abstraction layer for LLM calls
- YAML-based configuration for model definitions and retry policies
- Environment variable-based API key management (OPENAI_API_KEY)

### Enhancement Scope Definition

**Enhancement Type:** Integration with New Systems

**Enhancement Description:**
Enable support for Azure OpenAI GPTs (Azure-hosted OpenAI models) in the existing LLM service. This allows the agent to use Azure OpenAI endpoints in addition to the current direct OpenAI API support.

**Impact Assessment:** Moderate Impact (some existing code changes)

**Rationale:** The enhancement requires:
- Adding Azure provider configuration alongside existing OpenAI config
- Modifying the `_initialize_provider()` method to support Azure endpoints
- Updating the configuration schema to include Azure-specific settings (endpoint URL, API version, deployment names)
- The core completion logic and parameter mapping can remain largely unchanged since LiteLLM supports Azure OpenAI

### Goals and Background Context

**Goals:**
- Enable agent to use Azure OpenAI deployments as an alternative to direct OpenAI API
- Maintain backward compatibility with existing OpenAI configuration
- Support Azure-specific authentication and endpoint configuration
- Preserve existing parameter mapping and retry logic for Azure models

**Background Context:**

Many enterprise environments use Azure OpenAI Service instead of direct OpenAI API access due to:
1. **Data residency requirements** - Keep data within specific geographic boundaries
2. **Enterprise security** - Leverage Azure's security infrastructure and compliance certifications
3. **Existing Azure investments** - Utilize existing Azure subscriptions and billing
4. **Private networking** - Access models through private endpoints within Azure VNets

The current LLM service only supports direct OpenAI API endpoints. Adding Azure OpenAI support will make the agent viable for enterprise deployments that require Azure-hosted models. Since LiteLLM already supports Azure OpenAI, the integration should be straightforward, primarily requiring configuration changes and authentication setup.

### Change Log

| Change | Date | Version | Description | Author |
|--------|------|---------|-------------|--------|
| Initial PRD | 2025-11-12 | 1.0 | Azure GPT integration enhancement | John (PM Agent) |

---

## 2. Requirements

### Functional Requirements

**FR1:** The LLM service shall support Azure OpenAI provider configuration in addition to the existing OpenAI provider configuration.

**FR2:** The system shall allow users to configure Azure-specific settings including Azure endpoint URL, API version, and deployment names via the YAML configuration file.

**FR3:** The service shall support Azure authentication using API keys from environment variables (e.g., AZURE_OPENAI_API_KEY).

**FR4:** Model aliases in the configuration shall be able to map to either OpenAI model names or Azure deployment names based on the selected provider.

**FR5:** The service shall automatically route LLM requests to the appropriate provider (OpenAI or Azure) based on the model configuration.

**FR6:** The system shall maintain existing parameter mapping logic (GPT-4 vs GPT-5 parameters) for both OpenAI and Azure OpenAI models.

**FR7:** The service shall provide clear logging to indicate which provider (OpenAI or Azure) is being used for each completion request.

### Non-Functional Requirements

**NFR1:** Enhancement must maintain existing performance characteristics - Azure OpenAI calls should have similar latency profiles to direct OpenAI calls (within 10% variance).

**NFR2:** The configuration file schema changes must be backward compatible - existing configurations without Azure settings should continue to work without modification.

**NFR3:** Error messages for Azure-specific failures (endpoint unreachable, deployment not found) must be clear and actionable for troubleshooting.

**NFR4:** The service must support graceful fallback behavior if Azure endpoints are configured but unavailable.

**NFR5:** Documentation must be provided for Azure OpenAI configuration, including example configurations and required environment variables.

### Compatibility Requirements

**CR1: Existing Configuration Compatibility** - All existing `llm_config.yaml` files must continue to work without modification. Azure configuration should be purely additive.

**CR2: API Interface Compatibility** - The public methods `complete()` and `generate()` must maintain their existing signatures and behavior. Callers should not need code changes.

**CR3: LiteLLM Compatibility** - The integration must use LiteLLM's native Azure OpenAI support without custom wrapper logic, ensuring compatibility with LiteLLM updates.

**CR4: Environment Variable Compatibility** - New Azure-specific environment variables must not conflict with existing OpenAI variables (OPENAI_API_KEY, OPENAI_ORG_ID).

---

## 3. Technical Constraints and Integration Requirements

### Existing Technology Stack

**Languages**: Python 3.11

**Frameworks**:
- LiteLLM (LLM abstraction layer)
- asyncio (async/await patterns)
- structlog (structured logging)
- PyYAML (configuration management)

**Dependencies**:
- `litellm` - Multi-provider LLM client library
- `structlog` - Structured logging
- `pyyaml` - YAML parsing

**Infrastructure**:
- Windows-based development environment
- PowerShell 7+ for scripting
- `uv` package manager (not pip)

**External Dependencies**:
- OpenAI API (current)
- Azure OpenAI API (planned)
- Environment variable-based secrets management

### Integration Approach

**Azure Provider Integration Strategy**:
- Extend `_initialize_provider()` to support both OpenAI and Azure configurations
- Add Azure-specific configuration validation (endpoint URL format, API version, deployment names)
- Use LiteLLM's native Azure support by setting appropriate environment variables or passing Azure-specific parameters
- Maintain single active provider per model alias (validated at configuration load time)

**Configuration Integration Strategy**:
```yaml
# Proposed configuration extension
providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
    organization_env: "OPENAI_ORG_ID"
    base_url: null

  azure:
    enabled: false  # Opt-in
    api_key_env: "AZURE_OPENAI_API_KEY"
    endpoint_url_env: "AZURE_OPENAI_ENDPOINT"
    api_version: "2024-02-15-preview"
    deployment_mapping:
      main: "gpt-4-deployment-prod"
      fast: "gpt-4-mini-deployment-prod"
      powerful: "gpt-5-deployment-prod"
```

**Model Resolution Strategy**:
- Add provider detection logic in `_resolve_model()`
- If Azure enabled and deployment_mapping exists, map alias to Azure deployment name
- Otherwise, use existing OpenAI model name resolution
- Log provider selection for observability

**Retry and Error Handling Strategy**:
- Extend `retry_on_errors` list with Azure-specific error types (e.g., "DeploymentNotFound", "InvalidApiVersion")
- Add Azure-specific error message parsing for clearer diagnostics
- Maintain existing retry logic structure (exponential backoff, max attempts)

### Code Organization and Standards

**File Structure Approach**:
- All changes contained within `llm_service.py` (no new files required)
- Configuration schema changes in `llm_config.yaml`
- Follow existing code organization patterns (private methods prefixed with `_`)

**Naming Conventions**:
- Use `azure_` prefix for Azure-specific methods/variables (e.g., `_initialize_azure_provider()`)
- Maintain PEP8 compliance
- Use descriptive variable names (e.g., `azure_deployment_name` not `az_deploy`)

**Coding Standards**:
- Maintain existing patterns: type annotations, docstrings for all new methods
- Keep functions ≤30 lines (extract helper methods if needed)
- Use existing logger pattern (`structlog.get_logger()`)
- Follow defensive programming: validate Azure config before use

**Documentation Standards**:
- Update module docstring to mention Azure support
- Add comprehensive docstrings for new private methods
- Include examples in `complete()` and `generate()` docstrings showing Azure model usage
- Add inline comments for Azure-specific logic

### Deployment and Operations

**Build Process Integration**:
- No build process changes required (Python interpreted language)
- Existing `uv sync` workflow remains unchanged
- May need to update dependencies if LiteLLM version upgrade required

**Deployment Strategy**:
- Configuration file updates (add Azure section to `llm_config.yaml`)
- Set Azure environment variables in deployment environment:
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_ENDPOINT`
- Backward compatible: existing deployments work without changes
- Test Azure connectivity before rolling out broadly

**Monitoring and Logging**:
- Extend existing logging to include provider information:
  - "llm_completion_started" log includes provider="azure" or provider="openai"
  - Add "azure_deployment_name" to log context when using Azure
- Monitor Azure-specific metrics: endpoint availability, deployment-specific latencies
- Use existing structured logging patterns (no new logging framework)

**Configuration Management**:
- Azure configuration stored in `llm_config.yaml` (version controlled)
- Secrets (API keys, endpoints) in environment variables (not in config file)
- Support multiple environment configs (dev, staging, prod) through env-specific YAML files
- Configuration validation on service initialization with clear error messages

### Risk Assessment and Mitigation

**Technical Risks**:
1. **LiteLLM Version Compatibility** - Current LiteLLM version may not support latest Azure API features
   - *Mitigation*: Version check during initialization, document minimum LiteLLM version
2. **Azure API Version Changes** - Azure deprecating API versions could break integration
   - *Mitigation*: Make API version configurable, add warnings for deprecated versions
3. **Deployment Name Mismatch** - Incorrect deployment names cause runtime failures
   - *Mitigation*: Add connection test method, validate deployment accessibility on init

**Integration Risks**:
1. **Parameter Mapping Differences** - Azure may handle GPT-5 parameters differently than OpenAI
   - *Mitigation*: Test parameter mapping thoroughly with Azure GPT-5 deployments, add provider-specific parameter logic if needed
2. **Backward Compatibility Break** - Configuration changes could affect existing users
   - *Mitigation*: Extensive testing with existing configs, make Azure opt-in with explicit `enabled: false` default

**Deployment Risks**:
1. **Missing Environment Variables** - Azure config present but env vars not set
   - *Mitigation*: Clear validation errors on init, include setup checklist in documentation
2. **Network Connectivity** - Azure private endpoints may require VNet configuration
   - *Mitigation*: Document network requirements, provide connectivity troubleshooting guide

**Mitigation Strategies**:
- Comprehensive unit tests for Azure provider initialization
- Integration tests with actual Azure OpenAI endpoints (separate test deployments)
- Gradual rollout: test with single model alias before expanding to all models
- Rollback plan: revert to previous config version if issues arise

---

## 4. Epic and Story Structure

### Epic Approach

**Epic Structure Decision**: **Single Comprehensive Epic**

**Rationale**:
This enhancement involves adding Azure OpenAI provider support to an existing, well-structured LLM service. All work items are tightly related and sequential - configuration schema, provider initialization, model resolution, and testing are interdependent steps that build upon each other.

A single epic "Add Azure OpenAI Provider Support" ensures:
- Clear dependency chain across stories
- Unified testing strategy (each story builds on previous work)
- Minimal risk to existing OpenAI functionality (changes are isolated to provider initialization)
- Coherent documentation and rollout plan

---

## 5. Epic 1: Add Azure OpenAI Provider Support

**Epic Goal**: Enable the LLM service to support Azure OpenAI endpoints as an alternative to direct OpenAI API, allowing enterprise deployments with Azure-hosted models while maintaining full backward compatibility with existing OpenAI configurations.

**Integration Requirements**:
- Extend configuration schema to support Azure provider settings alongside existing OpenAI configuration
- Modify provider initialization to detect and configure Azure endpoints
- Update model resolution logic to map aliases to Azure deployment names
- Ensure parameter mapping (GPT-4/GPT-5) works identically for both providers
- Maintain existing retry logic and error handling with Azure-specific error types
- Preserve all existing functionality for OpenAI-only configurations (zero breaking changes)

---

### Story 1.1: Extend Configuration Schema for Azure Provider

As a **developer**,
I want **the configuration file to support Azure OpenAI settings**,
so that **I can configure Azure endpoints, API versions, and deployment mappings without breaking existing OpenAI configurations**.

**Acceptance Criteria:**

1. The `llm_config.yaml` schema includes a new `azure` section under `providers` with fields: `enabled`, `api_key_env`, `endpoint_url_env`, `api_version`, and `deployment_mapping`
2. Azure configuration is opt-in with `enabled: false` as the default
3. Existing configuration files without Azure section continue to load successfully
4. Configuration validation detects invalid Azure settings (missing required fields when enabled=true) and raises clear error messages
5. The `deployment_mapping` dictionary maps model aliases to Azure deployment names
6. Example Azure configuration is documented in comments within the config file

**Integration Verification:**

- **IV1: Existing Functionality Verification** - Load an existing `llm_config.yaml` (without Azure section) and verify service initializes without errors or warnings
- **IV2: Integration Point Verification** - Add Azure section with `enabled: false` to existing config and verify service behavior is identical to baseline
- **IV3: Performance Impact Verification** - Configuration loading time must not increase by more than 5% with Azure section present

---

### Story 1.2: Implement Azure Provider Initialization

As a **developer**,
I want **the LLM service to initialize Azure provider settings when enabled**,
so that **Azure OpenAI endpoints can be used for completion requests**.

**Acceptance Criteria:**

1. Create `_initialize_azure_provider()` method that reads Azure-specific environment variables (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT)
2. Modify `_initialize_provider()` to detect Azure enabled status and call Azure initialization
3. Azure initialization validates endpoint URL format and logs provider selection
4. Service logs clear warning if Azure enabled but environment variables are missing
5. Azure API key and endpoint are stored as instance variables for use in completion calls
6. LiteLLM environment variables are set appropriately for Azure OpenAI support (if required by LiteLLM version)

**Integration Verification:**

- **IV1: Existing Functionality Verification** - Verify OpenAI-only configuration (Azure disabled) continues to work identically, including API key loading and completion calls
- **IV2: Integration Point Verification** - Initialize service with Azure enabled but invalid endpoint, verify clear error message and graceful degradation
- **IV3: Performance Impact Verification** - Provider initialization time must remain under 100ms for both OpenAI and Azure configurations

---

### Story 1.3: Implement Azure Model Resolution Logic

As a **developer**,
I want **model aliases to resolve to Azure deployment names when using Azure provider**,
so that **completion requests route to the correct Azure OpenAI deployments**.

**Acceptance Criteria:**

1. Modify `_resolve_model()` to detect if Azure is enabled and a deployment mapping exists
2. When Azure enabled, resolve model alias through `deployment_mapping` dictionary (e.g., "main" → "gpt-4-deployment-prod")
3. When Azure disabled or no deployment mapping, use existing OpenAI model name resolution
4. Log provider and resolved model/deployment name at INFO level for observability
5. Raise clear error if Azure enabled but requested alias has no deployment mapping
6. Support fallback to OpenAI model name if deployment mapping is incomplete (optional behavior, configurable)

**Integration Verification:**

- **IV1: Existing Functionality Verification** - Verify model resolution for OpenAI configuration produces identical results to baseline (model aliases resolve to correct OpenAI model names)
- **IV2: Integration Point Verification** - Test hybrid scenario: Azure enabled for some aliases, OpenAI names for others, verify correct resolution path for each
- **IV3: Performance Impact Verification** - Model resolution must remain O(1) lookup time regardless of provider

---

### Story 1.4: Update Completion Method for Azure Support

As a **developer**,
I want **the `complete()` method to route requests to Azure endpoints when configured**,
so that **LLM completions use Azure OpenAI deployments without code changes in calling code**.

**Acceptance Criteria:**

1. Modify `complete()` to pass Azure-specific parameters to LiteLLM when Azure provider is active (endpoint URL, API version, deployment name)
2. LiteLLM call uses Azure authentication (API key from environment) when Azure is enabled
3. Existing parameter mapping logic (`_map_parameters_for_model()`) works identically for Azure models
4. Completion logs include provider name and deployment name (Azure) or model name (OpenAI)
5. Error messages from Azure API failures are captured and logged with clear context
6. Retry logic applies to Azure-specific errors (DeploymentNotFound, InvalidApiVersion, etc.)

**Integration Verification:**

- **IV1: Existing Functionality Verification** - Run existing test suite against OpenAI configuration, verify 100% pass rate with no behavior changes
- **IV2: Integration Point Verification** - Execute same completion request against OpenAI and Azure configurations, verify response format and content structure are identical
- **IV3: Performance Impact Verification** - Azure completion latency must be within 10% of OpenAI latency (excluding network differences), measured over 50 requests

---

### Story 1.5: Add Azure-Specific Error Handling and Logging

As an **operations engineer**,
I want **clear error messages and logs for Azure-specific failures**,
so that **I can quickly diagnose and resolve Azure configuration or connectivity issues**.

**Acceptance Criteria:**

1. Add Azure error types to `retry_on_errors` configuration (DeploymentNotFound, InvalidApiVersion, InvalidEndpoint)
2. Parse Azure API error responses and extract actionable information (deployment name, API version, endpoint URL)
3. Log Azure provider status at service initialization (enabled/disabled, endpoint URL, configured deployments)
4. Include provider name in all completion logs ("provider": "azure" or "openai")
5. Add diagnostic method `test_azure_connection()` that validates Azure endpoint accessibility and deployment availability
6. Document common Azure error scenarios and troubleshooting steps in code comments

**Integration Verification:**

- **IV1: Existing Functionality Verification** - Verify OpenAI error handling continues to work identically (rate limits, timeouts, etc.)
- **IV2: Integration Point Verification** - Simulate Azure-specific failures (wrong deployment name, invalid API version) and verify error messages guide user to resolution
- **IV3: Performance Impact Verification** - Error handling overhead must not increase baseline completion latency by more than 2%

---

### Story 1.6: Create Integration Tests for Azure Provider

As a **QA engineer**,
I want **comprehensive integration tests for Azure OpenAI support**,
so that **Azure configurations are validated and regressions are prevented**.

**Acceptance Criteria:**

1. Create test file `test_llm_service_azure.py` with Azure-specific test cases
2. Test cases cover: configuration loading, provider initialization, model resolution, completion execution
3. Use mock Azure endpoints or test Azure deployments (not production)
4. Tests verify backward compatibility: existing OpenAI tests pass without modification
5. Tests cover error scenarios: missing env vars, invalid deployments, network failures
6. Add pytest fixtures for Azure configuration setup and teardown
7. Tests validate that Azure and OpenAI produce equivalent response structures

**Integration Verification:**

- **IV1: Existing Functionality Verification** - Run full test suite (OpenAI + Azure) and verify no regressions in existing OpenAI tests
- **IV2: Integration Point Verification** - Tests explicitly verify that adding Azure configuration doesn't affect OpenAI behavior (side-by-side comparison)
- **IV3: Performance Impact Verification** - Test suite execution time must not increase by more than 20% with Azure tests added

---

### Story 1.7: Document Azure Configuration and Setup

As a **developer using the agent**,
I want **clear documentation for setting up Azure OpenAI support**,
so that **I can configure Azure deployments without trial and error**.

**Acceptance Criteria:**

1. Update `llm_service.py` module docstring to mention Azure support
2. Add comprehensive docstring to `_initialize_azure_provider()` explaining setup requirements
3. Create example Azure configuration in `configs/llm_config.yaml` (commented out by default)
4. Document required environment variables (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT) with examples
5. Add troubleshooting section to README or docs folder covering common Azure issues
6. Include example of hybrid configuration (some models via OpenAI, others via Azure)
7. Document Azure API version compatibility and how to update it

**Integration Verification:**

- **IV1: Existing Functionality Verification** - Verify documentation still accurately describes OpenAI-only setup (no outdated information)
- **IV2: Integration Point Verification** - Follow documentation as a new user and successfully configure Azure OpenAI from scratch
- **IV3: Performance Impact Verification** - N/A (documentation only)

---

## Summary

This PRD defines a comprehensive enhancement to add Azure OpenAI provider support to the existing LLM service. The single epic with 7 sequenced stories ensures:

- **Backward Compatibility**: Zero breaking changes for existing OpenAI users
- **Enterprise Viability**: Azure support enables enterprise deployments with data residency and security requirements
- **Maintainability**: All changes isolated to provider initialization, minimal code footprint
- **Testability**: Comprehensive testing strategy ensures quality and prevents regressions

The enhancement leverages LiteLLM's native Azure support, minimizing custom implementation complexity while providing a flexible, configuration-driven approach to multi-provider LLM access.
