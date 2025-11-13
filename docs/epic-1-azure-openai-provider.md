# Epic 1: Add Azure OpenAI Provider Support

**Status:** Ready for Development
**Priority:** High
**Version:** 1.0
**Created:** 2025-11-12
**Ready Date:** 2025-11-12
**Owner:** Development Team

---

## Epic Goal

Enable the LLM service to support Azure OpenAI endpoints as an alternative to direct OpenAI API, allowing enterprise deployments with Azure-hosted models while maintaining full backward compatibility with existing OpenAI configurations.

---

## Epic Description

### Existing System Context

**Current Relevant Functionality:**
- The LLM service (`llm_service.py`) currently supports OpenAI API exclusively through LiteLLM
- Configuration-driven model aliases (main, fast, powerful, legacy) map to OpenAI model names (gpt-4.1, gpt-4.1-mini, gpt-5, etc.)
- Environment variable-based authentication using OPENAI_API_KEY
- Model-aware parameter mapping that handles GPT-4 (traditional params) and GPT-5 (effort/reasoning params)
- Retry logic with exponential backoff for transient API errors

**Technology Stack:**
- Python 3.11 with async/await patterns
- LiteLLM - Multi-provider LLM abstraction library
- structlog - Structured logging
- PyYAML - Configuration management
- Windows development environment with `uv` package manager

**Integration Points:**
- `_load_config()` - YAML configuration loading and validation
- `_initialize_provider()` - Provider-specific setup (currently OpenAI only)
- `_resolve_model()` - Model alias to model name resolution
- `complete()` - Main completion method that calls LiteLLM
- `generate()` - Convenience wrapper around complete()

### Enhancement Details

**What's Being Added/Changed:**

1. **Configuration Schema Extension**
   - Add `azure` section under `providers` in `llm_config.yaml`
   - Include Azure-specific settings: endpoint URL, API version, deployment mappings
   - Make Azure opt-in with `enabled: false` default

2. **Azure Provider Initialization**
   - New `_initialize_azure_provider()` method to handle Azure authentication
   - Environment variable support for AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT
   - Validation of Azure endpoint format and configuration

3. **Model Resolution Enhancement**
   - Extend `_resolve_model()` to map aliases to Azure deployment names when Azure is enabled
   - Maintain existing OpenAI model name resolution as fallback

4. **Completion Routing**
   - Update `complete()` to pass Azure-specific parameters to LiteLLM
   - Ensure parameter mapping works identically for Azure models
   - Add provider-aware logging and error handling

5. **Testing & Documentation**
   - Comprehensive integration tests for Azure provider
   - Setup documentation with examples and troubleshooting guide

**How It Integrates:**
- Azure configuration is additive - existing configs continue to work unchanged
- Provider selection happens during initialization based on config
- Model resolution automatically routes to appropriate provider (OpenAI or Azure)
- Completion execution remains transparent to callers (same API surface)
- LiteLLM handles the actual Azure API calls (leveraging native support)

**Success Criteria:**
- ✅ Azure OpenAI deployments can be configured and used for LLM completions
- ✅ 100% backward compatibility - existing OpenAI configs work without modification
- ✅ Performance parity - Azure calls have similar latency to OpenAI calls (±10%)
- ✅ Clear error messages for Azure-specific failures (deployment not found, invalid endpoint, etc.)
- ✅ Comprehensive test coverage with no regressions in existing OpenAI tests
- ✅ Documentation enables users to set up Azure without trial and error

---

## Stories

This epic consists of **7 sequenced stories** that build upon each other:

### Story 1.1: Extend Configuration Schema for Azure Provider
**Status:** Ready for Development
**Estimated Effort:** Small
**Description:** Add Azure provider configuration section to `llm_config.yaml` with fields for endpoint, API version, and deployment mappings. Ensure backward compatibility with existing configs.

**Key Deliverables:**
- Extended YAML schema with Azure section
- Configuration validation for Azure settings
- Example Azure configuration in comments

### Story 1.2: Implement Azure Provider Initialization
**Status:** Ready for Development
**Estimated Effort:** Medium
**Description:** Create Azure-specific provider initialization logic that reads environment variables, validates endpoint URLs, and prepares the service for Azure API calls.

**Key Deliverables:**
- `_initialize_azure_provider()` method
- Environment variable handling for Azure credentials
- Provider selection logging

### Story 1.3: Implement Azure Model Resolution Logic
**Status:** Ready for Development
**Estimated Effort:** Medium
**Description:** Extend model resolution to map aliases to Azure deployment names when Azure is enabled, while preserving OpenAI model name resolution.

**Key Deliverables:**
- Enhanced `_resolve_model()` with provider detection
- Deployment name mapping logic
- Clear error messages for unmapped aliases

### Story 1.4: Update Completion Method for Azure Support
**Status:** Ready for Development
**Estimated Effort:** Large
**Description:** Modify the `complete()` method to route requests to Azure endpoints with appropriate parameters, ensuring parameter mapping and retry logic work correctly.

**Key Deliverables:**
- Azure-aware completion execution
- Provider-specific LiteLLM parameter passing
- Integration of Azure authentication and endpoint routing

### Story 1.5: Add Azure-Specific Error Handling and Logging
**Status:** Ready for Development
**Estimated Effort:** Medium
**Description:** Enhance error handling and logging to provide clear diagnostics for Azure-specific failures, including connection test utility.

**Key Deliverables:**
- Azure error types in retry configuration
- Enhanced logging with provider context
- `test_azure_connection()` diagnostic method

### Story 1.6: Create Integration Tests for Azure Provider
**Status:** Ready for Development
**Estimated Effort:** Large
**Description:** Develop comprehensive test suite for Azure provider functionality, ensuring backward compatibility and preventing regressions.

**Key Deliverables:**
- `test_llm_service_azure.py` test file
- Test coverage for all Azure code paths
- Backward compatibility verification tests

### Story 1.7: Document Azure Configuration and Setup
**Status:** Ready for Development
**Estimated Effort:** Small
**Description:** Create clear documentation for Azure setup, including configuration examples, environment variables, and troubleshooting guide.

**Key Deliverables:**
- Updated module and method docstrings
- Example Azure configuration
- Troubleshooting documentation

---

## Compatibility Requirements

- ✅ **Existing APIs remain unchanged** - `complete()` and `generate()` maintain their signatures
- ✅ **Configuration is backward compatible** - Configs without Azure section continue to work
- ✅ **Parameter mapping follows existing patterns** - GPT-4/GPT-5 parameter logic unchanged
- ✅ **Performance impact is minimal** - Configuration loading and provider init remain fast (<100ms)
- ✅ **Environment variables don't conflict** - Azure vars (AZURE_OPENAI_*) separate from OpenAI vars

---

## Risk Mitigation

### Primary Risk: Backward Compatibility Break
**Risk:** Configuration changes or provider initialization modifications could break existing OpenAI-only deployments.

**Mitigation:**
- Make Azure opt-in with explicit `enabled: false` default
- Extensive testing with existing configurations
- Configuration validation that catches invalid Azure settings early
- Separate initialization paths for OpenAI and Azure

**Rollback Plan:**
- Revert to previous config version (remove Azure section)
- Service automatically falls back to OpenAI-only mode when Azure disabled
- No database or persistent state changes required

### Secondary Risk: LiteLLM Compatibility
**Risk:** Current LiteLLM version may not support latest Azure OpenAI features or API versions.

**Mitigation:**
- Document minimum LiteLLM version requirement
- Make Azure API version configurable (not hardcoded)
- Add version check during initialization with clear warnings

**Rollback Plan:**
- Downgrade LiteLLM if needed (Azure features are isolated)
- Continue using OpenAI provider while resolving LiteLLM issues

### Tertiary Risk: Azure Deployment Configuration Errors
**Risk:** Users may configure incorrect Azure deployment names, causing runtime failures.

**Mitigation:**
- Add `test_azure_connection()` diagnostic method
- Validate deployment accessibility during initialization (optional check)
- Clear error messages with deployment name and endpoint in context

**Rollback Plan:**
- Fix deployment names in configuration
- Use OpenAI provider temporarily while resolving Azure deployment issues

---

## Definition of Done

- ✅ All 7 stories completed with acceptance criteria met
- ✅ Existing OpenAI functionality verified through full test suite (100% pass rate)
- ✅ Azure integration tested with mock or test deployments
- ✅ Configuration backward compatibility verified (old configs load successfully)
- ✅ Documentation updated with Azure setup instructions and examples
- ✅ No performance regression in configuration loading or provider initialization
- ✅ Error handling provides clear, actionable messages for Azure failures
- ✅ Code review completed with focus on backward compatibility
- ✅ Integration tests pass for both OpenAI and Azure providers

---

## Dependencies

**External Dependencies:**
- LiteLLM library with Azure OpenAI support (verify version compatibility)
- Azure OpenAI service with deployed models (for testing)
- Access to Azure environment variables and endpoints

**Internal Dependencies:**
- Existing LLM service implementation (`llm_service.py`)
- Configuration infrastructure (`llm_config.yaml`)
- Test infrastructure (pytest, fixtures)

---

## Technical Notes

**Key Architecture Decisions:**
1. **Single Provider Per Model Alias**: Each model alias maps to either OpenAI or Azure, not both simultaneously
2. **LiteLLM Native Support**: Use LiteLLM's built-in Azure support rather than custom wrappers
3. **Configuration-Driven**: All provider selection happens at config load time, not runtime
4. **Opt-In Design**: Azure must be explicitly enabled to avoid surprises for existing users

**Implementation Considerations:**
- Parameter mapping (`_map_parameters_for_model()`) should work identically for Azure
- Retry logic must include Azure-specific error types
- Logging must distinguish between providers for observability
- Environment variable names must not conflict with existing OpenAI variables

**Testing Strategy:**
- Unit tests for configuration loading and validation
- Integration tests with mock Azure endpoints
- Backward compatibility tests with existing OpenAI configs
- Performance tests to ensure no regression in latency or initialization time

---

## Related Documentation

- **PRD:** `docs/prd.md` - Full Product Requirements Document
- **LLM Service:** `capstone/agent_v2/services/llm_service.py` - Current implementation
- **Configuration:** `capstone/agent_v2/configs/llm_config.yaml` - Configuration file
- **Project Instructions:** `CLAUDE.md` - Development environment and architecture overview

---

## Story Manager Handoff

**Story Manager Handoff:**

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is an enhancement to an existing LLM service running Python 3.11 with LiteLLM, structlog, and async/await patterns
- Integration points:
  - `_load_config()` for configuration loading
  - `_initialize_provider()` for provider setup
  - `_resolve_model()` for model/deployment resolution
  - `complete()` for LLM API calls
- Existing patterns to follow:
  - Private methods prefixed with `_`
  - PEP8 compliance with type annotations
  - Structured logging with structlog
  - Configuration-driven behavior via YAML
  - Retry logic with exponential backoff
- Critical compatibility requirements:
  - Zero breaking changes for existing OpenAI configurations
  - Public method signatures (`complete()`, `generate()`) remain unchanged
  - Azure configuration must be opt-in with `enabled: false` default
  - Environment variables must not conflict (AZURE_* vs OPENAI_*)
- Each story must include verification that existing OpenAI functionality remains intact

The epic should maintain system integrity while delivering Azure OpenAI provider support for enterprise deployments with data residency and security requirements."

---

## Progress Tracking

| Story | Status | Assignee | Ready Date | Started | Completed | Notes |
|-------|--------|----------|------------|---------|-----------|-------|
| 1.1 - Config Schema | Ready for Development | - | 2025-11-12 | - | - | Foundation story, no dependencies |
| 1.2 - Provider Init | Ready for Development | - | 2025-11-12 | - | - | Depends on Story 1.1 |
| 1.3 - Model Resolution | Ready for Development | - | 2025-11-12 | - | - | Depends on Story 1.2 |
| 1.4 - Completion Method | Ready for Development | - | 2025-11-12 | - | - | Depends on Story 1.3 |
| 1.5 - Error Handling | Ready for Development | - | 2025-11-12 | - | - | Depends on Story 1.4 |
| 1.6 - Integration Tests | Ready for Development | - | 2025-11-12 | - | - | Depends on Story 1.5 |
| 1.7 - Documentation | Ready for Development | - | 2025-11-12 | - | - | Depends on Story 1.6 |

---

**Last Updated:** 2025-11-12
