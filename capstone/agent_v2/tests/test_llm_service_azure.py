"""
Integration tests for Azure OpenAI provider support in LLMService.

This test suite provides comprehensive coverage for Azure OpenAI integration:
- Azure configuration loading and validation
- Azure provider initialization with environment variables
- Azure deployment model resolution  
- Azure completion execution with proper provider context
- Error scenario handling (missing env vars, invalid deployments, network failures)
- Backward compatibility verification (OpenAI tests pass unchanged)
- Response structure equivalence between Azure and OpenAI providers
"""

import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from capstone.agent_v2.services.llm_service import LLMService


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture
def azure_config_disabled(tmp_path):
    """Create config with Azure disabled (backward compatibility)."""
    config_content = """
default_model: "main"
models:
  main: "gpt-4.1"
  fast: "gpt-4.1-mini"
model_params:
  gpt-4.1:
    temperature: 0.7
    max_tokens: 2000
default_params:
  temperature: 0.7
  max_tokens: 2000
retry_policy:
  max_attempts: 3
  backoff_multiplier: 2
  timeout: 30
  retry_on_errors:
    - "RateLimitError"
providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
  azure:
    enabled: false
logging:
  log_token_usage: true
  log_parameter_mapping: true
"""
    config_file = tmp_path / "azure_disabled_config.yaml"
    config_file.write_text(config_content, encoding="utf-8")
    return str(config_file)


@pytest.fixture
def azure_config_enabled(tmp_path):
    """Create config with Azure enabled and proper deployment mapping."""
    config_content = """
default_model: "main"
models:
  main: "gpt-4.1"
  fast: "gpt-4.1-mini"
  powerful: "gpt-5"
model_params:
  gpt-4.1:
    temperature: 0.7
    max_tokens: 2000
  gpt-5:
    effort: "medium"
    reasoning: "balanced"
    max_tokens: 4000
default_params:
  temperature: 0.7
  max_tokens: 2000
retry_policy:
  max_attempts: 3
  backoff_multiplier: 2
  timeout: 30
  retry_on_errors:
    - "RateLimitError"
    - "DeploymentNotFound"
    - "InvalidApiVersion"
    - "AuthenticationError"
providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
  azure:
    enabled: true
    api_key_env: "AZURE_OPENAI_API_KEY"
    endpoint_url_env: "AZURE_OPENAI_ENDPOINT"
    api_version: "2024-02-15-preview"
    deployment_mapping:
      main: "gpt-4-deployment-prod"
      fast: "gpt-4-mini-deployment-prod"
      powerful: "gpt-5-deployment-prod"
logging:
  log_token_usage: true
  log_parameter_mapping: true
"""
    config_file = tmp_path / "azure_enabled_config.yaml"
    config_file.write_text(config_content, encoding="utf-8")
    return str(config_file)


@pytest.fixture
def azure_env_vars(monkeypatch):
    """Setup Azure environment variables."""
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-azure-key-12345")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test-resource.openai.azure.com")
    # Clean up OpenAI key to ensure Azure is used
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def openai_env_vars(monkeypatch):
    """Setup OpenAI environment variables (backward compatibility)."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-12345")
    # Clean up Azure keys to ensure OpenAI is used
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)


@pytest.fixture
def mock_azure_response():
    """Create mock Azure OpenAI API response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Azure test response"
    mock_response.usage = {
        "total_tokens": 100,
        "prompt_tokens": 50,
        "completion_tokens": 50,
    }
    return mock_response


@pytest.fixture
def mock_openai_response():
    """Create mock OpenAI API response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "OpenAI test response"
    mock_response.usage = {
        "total_tokens": 100,
        "prompt_tokens": 50,
        "completion_tokens": 50,
    }
    return mock_response


# ============================================================================
# Test Class: Azure Configuration Loading
# ============================================================================


class TestAzureConfigurationLoading:
    """Test Azure configuration loading and validation (AC1)."""

    def test_azure_config_loads_when_enabled(self, azure_config_enabled, azure_env_vars):
        """
        Given: Valid Azure configuration with enabled=true
        When: LLMService initializes
        Then: Azure configuration is loaded successfully
        """
        service = LLMService(config_path=azure_config_enabled)
        
        azure_config = service.provider_config.get("azure", {})
        assert azure_config.get("enabled") is True
        assert azure_config.get("api_key_env") == "AZURE_OPENAI_API_KEY"
        assert azure_config.get("endpoint_url_env") == "AZURE_OPENAI_ENDPOINT"
        assert azure_config.get("api_version") == "2024-02-15-preview"
        assert "main" in azure_config.get("deployment_mapping", {})

    def test_azure_config_ignored_when_disabled(self, azure_config_disabled, openai_env_vars):
        """
        Given: Azure configuration with enabled=false
        When: LLMService initializes
        Then: Azure is disabled and OpenAI is used (backward compatibility)
        """
        service = LLMService(config_path=azure_config_disabled)
        
        azure_config = service.provider_config.get("azure", {})
        assert azure_config.get("enabled") is False
        
        # Verify OpenAI provider is selected
        assert not hasattr(service, "azure_api_key") or service.azure_api_key is None

    def test_azure_config_validates_required_fields(self, tmp_path):
        """
        Given: Azure config enabled but missing required fields
        When: LLMService initializes
        Then: Raises ValueError with clear message
        """
        config_content = """
default_model: "main"
models:
  main: "gpt-4.1"
providers:
  azure:
    enabled: true
    api_key_env: "AZURE_OPENAI_API_KEY"
    # Missing: endpoint_url_env, api_version, deployment_mapping
"""
        config_file = tmp_path / "azure_incomplete.yaml"
        config_file.write_text(config_content, encoding="utf-8")
        
        with pytest.raises(ValueError, match="missing required fields"):
            LLMService(config_path=str(config_file))

    def test_backward_compatibility_no_azure_section(self, tmp_path, openai_env_vars):
        """
        Given: Config file without Azure section (legacy)
        When: LLMService initializes
        Then: Initializes successfully with OpenAI provider (backward compatibility)
        """
        config_content = """
default_model: "main"
models:
  main: "gpt-4.1"
providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
"""
        config_file = tmp_path / "legacy_config.yaml"
        config_file.write_text(config_content, encoding="utf-8")
        
        service = LLMService(config_path=str(config_file))
        
        # Verify service initialized without Azure
        assert "azure" not in service.provider_config or not service.provider_config.get("azure")


# ============================================================================
# Test Class: Azure Provider Initialization
# ============================================================================


class TestAzureProviderInitialization:
    """Test Azure provider initialization with environment variables (AC2)."""

    def test_azure_provider_initializes_with_env_vars(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure enabled and environment variables set
        When: LLMService initializes
        Then: Azure provider credentials are loaded
        """
        service = LLMService(config_path=azure_config_enabled)
        
        assert service.azure_api_key == "test-azure-key-12345"
        assert service.azure_endpoint == "https://test-resource.openai.azure.com"
        assert service.azure_api_version == "2024-02-15-preview"
        
        # Verify LiteLLM environment variables are set
        assert os.getenv("AZURE_API_KEY") == "test-azure-key-12345"
        assert os.getenv("AZURE_API_BASE") == "https://test-resource.openai.azure.com"
        assert os.getenv("AZURE_API_VERSION") == "2024-02-15-preview"

    def test_azure_provider_warns_missing_api_key(self, azure_config_enabled, monkeypatch):
        """
        Given: Azure enabled but API key environment variable not set
        When: LLMService initializes
        Then: Warning logged and azure_api_key is None
        """
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        
        service = LLMService(config_path=azure_config_enabled)
        
        assert service.azure_api_key is None

    def test_azure_provider_warns_missing_endpoint(self, azure_config_enabled, monkeypatch):
        """
        Given: Azure enabled but endpoint environment variable not set
        When: LLMService initializes
        Then: Warning logged and azure_endpoint is None
        """
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        
        service = LLMService(config_path=azure_config_enabled)
        
        assert service.azure_endpoint is None

    def test_azure_provider_rejects_non_https_endpoint(self, azure_config_enabled, monkeypatch):
        """
        Given: Azure enabled with non-HTTPS endpoint
        When: LLMService initializes
        Then: Raises ValueError for security
        """
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "http://insecure.openai.azure.com")
        
        with pytest.raises(ValueError, match="must use HTTPS protocol"):
            LLMService(config_path=azure_config_enabled)


# ============================================================================
# Test Class: Azure Model Resolution
# ============================================================================


class TestAzureModelResolution:
    """Test Azure deployment model resolution (AC2)."""

    def test_azure_resolves_alias_to_deployment(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure enabled with deployment mapping
        When: Model alias is resolved
        Then: Returns Azure deployment name with 'azure/' prefix
        """
        service = LLMService(config_path=azure_config_enabled)
        
        assert service._resolve_model("main") == "azure/gpt-4-deployment-prod"
        assert service._resolve_model("fast") == "azure/gpt-4-mini-deployment-prod"
        assert service._resolve_model("powerful") == "azure/gpt-5-deployment-prod"

    def test_azure_resolves_default_model(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure enabled with default model mapped
        When: None is passed for model
        Then: Resolves to default model's deployment
        """
        service = LLMService(config_path=azure_config_enabled)
        
        resolved = service._resolve_model(None)
        assert resolved == "azure/gpt-4-deployment-prod"

    def test_azure_raises_error_unmapped_alias(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure enabled but alias not in deployment_mapping
        When: Model alias is resolved
        Then: Raises ValueError with clear guidance
        """
        service = LLMService(config_path=azure_config_enabled)
        
        with pytest.raises(ValueError, match="no deployment mapping found"):
            service._resolve_model("unmapped-alias")

    def test_openai_resolution_unchanged_when_azure_disabled(self, azure_config_disabled, openai_env_vars):
        """
        Given: Azure disabled
        When: Model alias is resolved
        Then: Uses OpenAI model names (backward compatibility verified)
        """
        service = LLMService(config_path=azure_config_disabled)
        
        assert service._resolve_model("main") == "gpt-4.1"
        assert service._resolve_model("fast") == "gpt-4.1-mini"
        assert service._resolve_model(None) == "gpt-4.1"


# ============================================================================
# Test Class: Azure Completion Execution
# ============================================================================


@pytest.mark.asyncio
class TestAzureCompletionExecution:
    """Test Azure completion execution with proper provider context (AC3)."""

    async def test_azure_completion_success(self, azure_config_enabled, azure_env_vars, mock_azure_response):
        """
        Given: Azure enabled and configured
        When: Completion is executed
        Then: Returns successful response with Azure provider
        """
        service = LLMService(config_path=azure_config_enabled)
        
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_azure_response) as mock_completion:
            result = await service.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="main"
            )
        
        # Verify success
        assert result["success"] is True
        assert result["content"] == "Azure test response"
        assert result["usage"]["total_tokens"] == 100
        
        # Verify Azure deployment format was used
        call_args = mock_completion.call_args
        assert call_args[1]["model"] == "azure/gpt-4-deployment-prod"

    async def test_azure_completion_with_parameters(self, azure_config_enabled, azure_env_vars, mock_azure_response):
        """
        Given: Azure enabled
        When: Completion with custom parameters
        Then: Parameters are correctly passed to Azure API
        """
        service = LLMService(config_path=azure_config_enabled)
        
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_azure_response) as mock_completion:
            await service.complete(
                messages=[{"role": "user", "content": "Test"}],
                model="main",
                temperature=0.5,
                max_tokens=1000
            )
        
        # Verify parameters
        call_args = mock_completion.call_args
        assert call_args[1]["temperature"] == 0.5
        assert call_args[1]["max_tokens"] == 1000

    async def test_openai_completion_unchanged_when_azure_disabled(
        self, azure_config_disabled, openai_env_vars, mock_openai_response
    ):
        """
        Given: Azure disabled (backward compatibility test)
        When: Completion is executed
        Then: Uses OpenAI provider as before (AC4: backward compatibility)
        """
        service = LLMService(config_path=azure_config_disabled)
        
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_openai_response) as mock_completion:
            result = await service.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="main"
            )
        
        # Verify OpenAI is used
        assert result["success"] is True
        call_args = mock_completion.call_args
        assert call_args[1]["model"] == "gpt-4.1"
        assert not call_args[1]["model"].startswith("azure/")


# ============================================================================
# Test Class: Response Structure Equivalence
# ============================================================================


@pytest.mark.asyncio
class TestResponseStructureEquivalence:
    """Test that Azure and OpenAI produce equivalent response structures (AC7)."""

    async def test_response_structure_matches_openai(self, azure_config_enabled, azure_env_vars, mock_azure_response):
        """
        Given: Azure completion
        When: Response is returned
        Then: Structure matches OpenAI response (success, content, usage, model, latency_ms)
        """
        service = LLMService(config_path=azure_config_enabled)
        
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_azure_response):
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}],
                model="main"
            )
        
        # Verify response structure
        assert "success" in result
        assert "content" in result
        assert "usage" in result
        assert "model" in result
        assert "latency_ms" in result
        
        # Verify usage structure
        assert "total_tokens" in result["usage"]
        assert "prompt_tokens" in result["usage"]
        assert "completion_tokens" in result["usage"]

    async def test_error_response_structure_matches_openai(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure completion fails
        When: Error response is returned
        Then: Structure matches OpenAI error response
        """
        service = LLMService(config_path=azure_config_enabled)
        
        async def mock_error(*args, **kwargs):
            raise ValueError("Test error")
        
        with patch("litellm.acompletion", side_effect=mock_error):
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}],
                model="main"
            )
        
        # Verify error response structure
        assert result["success"] is False
        assert "error" in result
        assert "error_type" in result
        assert "model" in result


# ============================================================================
# Test Class: Error Scenarios
# ============================================================================


@pytest.mark.asyncio
class TestAzureErrorScenarios:
    """Test error scenarios for Azure provider (AC5)."""

    async def test_missing_env_vars_error(self, azure_config_enabled, monkeypatch):
        """
        Given: Azure enabled but environment variables not set
        When: Connection test is run
        Then: Returns clear error about missing credentials
        """
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        
        service = LLMService(config_path=azure_config_enabled)
        result = await service.test_azure_connection()
        
        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert any("API key" in error for error in result["errors"])
        assert any("endpoint" in error for error in result["errors"])

    async def test_invalid_deployment_error(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure enabled with invalid deployment name
        When: Completion is attempted
        Then: Returns error with deployment troubleshooting guidance
        """
        service = LLMService(config_path=azure_config_enabled)
        
        async def mock_deployment_error(*args, **kwargs):
            raise Exception("DeploymentNotFound: deployment 'wrong-deployment' not found")
        
        with patch("litellm.acompletion", side_effect=mock_deployment_error):
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}],
                model="main"
            )
        
        assert result["success"] is False
        assert "parsed_error" in result
        assert "deployment_name" in result["parsed_error"]
        assert "hint" in result["parsed_error"]

    async def test_invalid_api_version_error(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure with invalid API version
        When: Completion is attempted
        Then: Returns error with API version guidance
        """
        service = LLMService(config_path=azure_config_enabled)
        
        async def mock_version_error(*args, **kwargs):
            raise Exception("InvalidApiVersion: API version '2021-01-01' not supported")
        
        with patch("litellm.acompletion", side_effect=mock_version_error):
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}],
                model="main"
            )
        
        assert result["success"] is False
        assert "parsed_error" in result
        assert "api_version" in result["parsed_error"]

    async def test_network_failure_error(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure configured
        When: Network failure occurs
        Then: Returns error with network troubleshooting guidance
        """
        service = LLMService(config_path=azure_config_enabled)
        
        async def mock_network_error(*args, **kwargs):
            raise Exception("Endpoint https://test.openai.azure.com not reachable")
        
        with patch("litellm.acompletion", side_effect=mock_network_error):
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}],
                model="main"
            )
        
        assert result["success"] is False
        assert "error" in result

    async def test_retry_logic_for_azure_errors(self, azure_config_enabled, azure_env_vars, mock_azure_response):
        """
        Given: Azure configured with retry policy
        When: Azure-specific retryable error occurs
        Then: Retries and eventually succeeds
        """
        service = LLMService(config_path=azure_config_enabled)
        
        call_count = 0
        
        async def mock_retry_scenario(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("DeploymentNotFound: temporary issue")
            return mock_azure_response
        
        with patch("litellm.acompletion", side_effect=mock_retry_scenario):
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}],
                model="main"
            )
        
        assert result["success"] is True
        assert call_count == 2  # Should have retried once


# ============================================================================
# Test Class: Azure Connection Diagnostic
# ============================================================================


@pytest.mark.asyncio
class TestAzureConnectionDiagnostic:
    """Test Azure connection diagnostic method (AC6)."""

    async def test_connection_test_when_disabled(self, azure_config_disabled):
        """
        Given: Azure disabled
        When: Connection test is run
        Then: Returns error indicating Azure is disabled
        """
        service = LLMService(config_path=azure_config_disabled)
        result = await service.test_azure_connection()
        
        assert result["success"] is False
        assert "not enabled" in result["error"]

    async def test_connection_test_successful(self, azure_config_enabled, azure_env_vars, mock_azure_response):
        """
        Given: Azure properly configured
        When: Connection test is run
        Then: Returns success with deployment availability
        """
        service = LLMService(config_path=azure_config_enabled)
        
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_azure_response):
            result = await service.test_azure_connection()
        
        assert result["success"] is True
        assert result["endpoint_reachable"] is True
        assert result["authentication_valid"] is True
        assert len(result["deployments_available"]) > 0

    async def test_connection_test_deployment_failure(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure configured but deployment fails
        When: Connection test is run
        Then: Returns failure with specific deployment issues
        """
        service = LLMService(config_path=azure_config_enabled)
        
        async def mock_deployment_error(*args, **kwargs):
            raise Exception("DeploymentNotFound: deployment not found")
        
        with patch("litellm.acompletion", side_effect=mock_deployment_error):
            result = await service.test_azure_connection()
        
        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert len(result["recommendations"]) > 0


# ============================================================================
# Test Class: Backward Compatibility Integration
# ============================================================================


@pytest.mark.asyncio
class TestBackwardCompatibilityIntegration:
    """Integration tests verifying backward compatibility (AC4)."""

    async def test_existing_openai_code_works_unchanged(self, azure_config_disabled, openai_env_vars, mock_openai_response):
        """
        Given: Azure disabled (legacy config)
        When: Existing OpenAI code runs
        Then: Works exactly as before without changes
        """
        service = LLMService(config_path=azure_config_disabled)
        
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_openai_response):
            # Simulate existing code that uses OpenAI
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}],
                model="main"
            )
        
        assert result["success"] is True
        assert "content" in result
        assert "usage" in result

    async def test_openai_and_azure_coexist(self, tmp_path, monkeypatch, mock_azure_response):
        """
        Given: Config with both OpenAI and Azure providers
        When: Azure is enabled
        Then: Azure is used, but OpenAI config remains valid
        """
        config_content = """
default_model: "main"
models:
  main: "gpt-4.1"
providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
  azure:
    enabled: true
    api_key_env: "AZURE_OPENAI_API_KEY"
    endpoint_url_env: "AZURE_OPENAI_ENDPOINT"
    api_version: "2024-02-15-preview"
    deployment_mapping:
      main: "azure-deployment"
"""
        config_file = tmp_path / "coexist_config.yaml"
        config_file.write_text(config_content, encoding="utf-8")
        
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        
        service = LLMService(config_path=str(config_file))
        
        # Verify both providers are configured
        assert "openai" in service.provider_config
        assert "azure" in service.provider_config
        assert service.provider_config["azure"]["enabled"] is True


# ============================================================================
# Test Class: Performance Requirements
# ============================================================================


class TestAzurePerformanceRequirements:
    """Test performance requirements for Azure integration (IV3)."""

    def test_azure_initialization_performance(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure configuration
        When: LLMService initializes
        Then: Completes within acceptable time (< 100ms)
        """
        import time
        
        start_time = time.perf_counter()
        service = LLMService(config_path=azure_config_enabled)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        assert service is not None
        assert elapsed_ms < 100, f"Initialization took {elapsed_ms:.2f}ms, expected < 100ms"

    def test_model_resolution_performance(self, azure_config_enabled, azure_env_vars):
        """
        Given: Azure enabled with multiple deployments
        When: Model resolution is performed repeatedly
        Then: Performs efficiently (< 1ms per resolution)
        """
        import time
        
        service = LLMService(config_path=azure_config_enabled)
        
        iterations = 100
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            service._resolve_model("main")
            service._resolve_model("fast")
            service._resolve_model("powerful")
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        avg_ms = elapsed_ms / (iterations * 3)
        
        assert avg_ms < 1.0, f"Average resolution took {avg_ms:.3f}ms, expected < 1ms"


# ============================================================================
# Integration Test: Real Config File
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_azure_with_real_config():
    """
    Integration test with actual config file.
    Only runs if config file exists.
    """
    config_path = "capstone/agent_v2/configs/llm_config.yaml"
    
    if not Path(config_path).exists():
        pytest.skip("Config file not found")
    
    # This test verifies the actual config loads without errors
    service = LLMService(config_path=config_path)
    
    # Verify service initialized
    assert service is not None
    assert service.default_model is not None
    
    # If Azure is configured in the real config, verify it loaded
    azure_config = service.provider_config.get("azure", {})
    if azure_config.get("enabled"):
        assert service.azure_api_version is not None




