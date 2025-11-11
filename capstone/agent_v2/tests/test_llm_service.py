"""
Unit tests for LLMService.

Tests cover:
- Initialization and configuration loading
- Model resolution (aliases)
- Parameter mapping (GPT-4 vs GPT-5)
- Completion methods
- Retry logic
- Error handling
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from capstone.agent_v2.services.llm_service import LLMService


@pytest.fixture
def mock_config(tmp_path):
    """Create temporary config file."""
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
providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
logging:
  log_token_usage: true
  log_parameter_mapping: true
"""
    config_file = tmp_path / "llm_config.yaml"
    config_file.write_text(config_content, encoding="utf-8")
    return str(config_file)


class TestLLMServiceInitialization:
    """Test LLMService initialization and configuration loading."""

    def test_init_loads_config(self, mock_config):
        """Test that initialization loads config successfully."""
        service = LLMService(config_path=mock_config)
        assert service.default_model == "main"
        assert "main" in service.models
        assert service.models["main"] == "gpt-4.1"

    def test_init_missing_config_raises_error(self):
        """Test that missing config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            LLMService(config_path="nonexistent.yaml")

    def test_init_sets_retry_policy(self, mock_config):
        """Test that retry policy is loaded from config."""
        service = LLMService(config_path=mock_config)
        assert service.retry_policy.max_attempts == 3
        assert service.retry_policy.backoff_multiplier == 2
        assert service.retry_policy.timeout == 30

    def test_init_sets_logging_config(self, mock_config):
        """Test that logging configuration is loaded."""
        service = LLMService(config_path=mock_config)
        assert service.logging_config.get("log_token_usage") is True
        assert service.logging_config.get("log_parameter_mapping") is True

    def test_init_empty_config_raises_error(self, tmp_path):
        """Test that empty config file raises ValueError."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty or invalid"):
            LLMService(config_path=str(config_file))

    def test_init_missing_models_raises_error(self, tmp_path):
        """Test that config without models raises ValueError."""
        config_content = """
default_model: "main"
model_params: {}
"""
        config_file = tmp_path / "no_models.yaml"
        config_file.write_text(config_content, encoding="utf-8")
        with pytest.raises(ValueError, match="at least one model"):
            LLMService(config_path=str(config_file))


class TestModelResolution:
    """Test model alias resolution."""

    def test_resolve_model_with_alias(self, mock_config):
        """Test resolving model alias to actual name."""
        service = LLMService(config_path=mock_config)
        assert service._resolve_model("main") == "gpt-4.1"
        assert service._resolve_model("powerful") == "gpt-5"

    def test_resolve_model_with_none_uses_default(self, mock_config):
        """Test that None resolves to default model."""
        service = LLMService(config_path=mock_config)
        assert service._resolve_model(None) == "gpt-4.1"

    def test_resolve_model_with_direct_name(self, mock_config):
        """Test that direct model names pass through."""
        service = LLMService(config_path=mock_config)
        # If not an alias, should return as-is
        assert service._resolve_model("gpt-4-turbo") == "gpt-4-turbo"


class TestParameterMapping:
    """Test GPT-4 vs GPT-5 parameter mapping."""

    def test_gpt4_parameters_passed_through(self, mock_config):
        """Test GPT-4 parameters are passed through unchanged."""
        service = LLMService(config_path=mock_config)
        params = {"temperature": 0.7, "top_p": 1.0, "max_tokens": 2000}
        mapped = service._map_parameters_for_model("gpt-4.1", params)
        assert mapped["temperature"] == 0.7
        assert mapped["top_p"] == 1.0
        assert mapped["max_tokens"] == 2000

    def test_gpt5_temperature_mapped_to_effort_low(self, mock_config):
        """Test GPT-5 low temperature conversion to effort."""
        service = LLMService(config_path=mock_config)
        mapped = service._map_parameters_for_model("gpt-5", {"temperature": 0.2})
        assert mapped["effort"] == "low"

    def test_gpt5_temperature_mapped_to_effort_medium(self, mock_config):
        """Test GPT-5 medium temperature conversion to effort."""
        service = LLMService(config_path=mock_config)
        mapped = service._map_parameters_for_model("gpt-5", {"temperature": 0.5})
        assert mapped["effort"] == "medium"

    def test_gpt5_temperature_mapped_to_effort_high(self, mock_config):
        """Test GPT-5 high temperature conversion to effort."""
        service = LLMService(config_path=mock_config)
        mapped = service._map_parameters_for_model("gpt-5", {"temperature": 0.9})
        assert mapped["effort"] == "high"

    def test_gpt5_deprecated_params_filtered(self, mock_config):
        """Test GPT-5 filters out deprecated parameters."""
        service = LLMService(config_path=mock_config)
        params = {
            "temperature": 0.7,
            "top_p": 1.0,
            "max_tokens": 2000,
            "frequency_penalty": 0.5,
        }
        mapped = service._map_parameters_for_model("gpt-5", params)

        # Should have effort and max_tokens, but not deprecated params
        assert "temperature" not in mapped
        assert "top_p" not in mapped
        assert "frequency_penalty" not in mapped
        assert "max_tokens" in mapped
        assert "effort" in mapped

    def test_gpt5_effort_preserved_when_provided(self, mock_config):
        """Test that explicit effort parameter is preserved."""
        service = LLMService(config_path=mock_config)
        params = {"effort": "high", "max_tokens": 3000}
        mapped = service._map_parameters_for_model("gpt-5", params)
        assert mapped["effort"] == "high"
        assert mapped["max_tokens"] == 3000

    def test_gpt5_reasoning_preserved_when_provided(self, mock_config):
        """Test that reasoning parameter is preserved."""
        service = LLMService(config_path=mock_config)
        params = {"reasoning": "careful", "max_tokens": 3000}
        mapped = service._map_parameters_for_model("gpt-5", params)
        assert mapped["reasoning"] == "careful"

    def test_gpt5_temperature_boundary_at_0_3(self, mock_config):
        """Test boundary condition: temperature=0.3 should map to medium."""
        service = LLMService(config_path=mock_config)
        mapped = service._map_parameters_for_model("gpt-5", {"temperature": 0.3})
        assert mapped["effort"] == "medium"

    def test_gpt5_temperature_boundary_at_0_7(self, mock_config):
        """Test boundary condition: temperature=0.7 should map to medium."""
        service = LLMService(config_path=mock_config)
        mapped = service._map_parameters_for_model("gpt-5", {"temperature": 0.7})
        assert mapped["effort"] == "medium"

    def test_gpt5_temperature_just_above_0_7(self, mock_config):
        """Test boundary condition: temperature=0.71 should map to high."""
        service = LLMService(config_path=mock_config)
        mapped = service._map_parameters_for_model("gpt-5", {"temperature": 0.71})
        assert mapped["effort"] == "high"


class TestParameterRetrieval:
    """Test getting model parameters from config."""

    def test_get_model_parameters_exact_match(self, mock_config):
        """Test exact model match retrieves correct parameters."""
        service = LLMService(config_path=mock_config)
        params = service._get_model_parameters("gpt-4.1")
        assert params["temperature"] == 0.7
        assert params["max_tokens"] == 2000

    def test_get_model_parameters_family_match(self, mock_config):
        """Test model family prefix matching."""
        service = LLMService(config_path=mock_config)
        # gpt-4.1-turbo should match gpt-4.1 params
        params = service._get_model_parameters("gpt-4.1-turbo")
        assert params["temperature"] == 0.7

    def test_get_model_parameters_defaults_fallback(self, mock_config):
        """Test fallback to defaults for unknown models."""
        service = LLMService(config_path=mock_config)
        params = service._get_model_parameters("unknown-model")
        assert params["temperature"] == 0.7  # default
        assert params["max_tokens"] == 2000  # default


@pytest.mark.asyncio
class TestCompletionMethod:
    """Test complete() method."""

    async def test_successful_completion(self, mock_config):
        """Test successful LLM completion."""
        service = LLMService(config_path=mock_config)

        # Mock litellm response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = {
            "total_tokens": 100,
            "prompt_tokens": 50,
            "completion_tokens": 50,
        }

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await service.complete(
                messages=[{"role": "user", "content": "Hello"}], model="main"
            )

        assert result["success"] is True
        assert result["content"] == "Test response"
        assert result["usage"]["total_tokens"] == 100

    async def test_completion_with_usage_object(self, mock_config):
        """Test handling usage as object instead of dict."""
        service = LLMService(config_path=mock_config)

        # Mock usage as object
        mock_usage = MagicMock()
        mock_usage.total_tokens = 100
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 50

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = mock_usage

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await service.complete(
                messages=[{"role": "user", "content": "Hello"}]
            )

        assert result["success"] is True
        assert result["usage"]["total_tokens"] == 100

    async def test_retry_on_rate_limit(self, mock_config):
        """Test retry logic on rate limit error."""
        service = LLMService(config_path=mock_config)

        # Mock to fail twice then succeed
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Success"
        mock_response.usage = {
            "total_tokens": 10,
            "prompt_tokens": 5,
            "completion_tokens": 5,
        }

        call_count = 0

        async def mock_acompletion(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("RateLimitError: Too many requests")
            return mock_response

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}], model="main"
            )

        assert result["success"] is True
        assert call_count == 3  # Should have retried twice

    async def test_failure_after_max_retries(self, mock_config):
        """Test that failures return error after max retries."""
        service = LLMService(config_path=mock_config)

        async def mock_acompletion(*args, **kwargs):
            raise Exception("RateLimitError: Too many requests")

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}], model="main"
            )

        assert result["success"] is False
        assert "error" in result
        assert result["error_type"] == "Exception"

    async def test_no_retry_on_non_retryable_error(self, mock_config):
        """Test that non-retryable errors fail immediately."""
        service = LLMService(config_path=mock_config)

        call_count = 0

        async def mock_acompletion(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            result = await service.complete(
                messages=[{"role": "user", "content": "Test"}], model="main"
            )

        assert result["success"] is False
        assert call_count == 1  # Should not retry


@pytest.mark.asyncio
class TestGenerateMethod:
    """Test generate() convenience method."""

    async def test_generate_simple_prompt(self, mock_config):
        """Test generate with simple prompt."""
        service = LLMService(config_path=mock_config)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated text"
        mock_response.usage = {"total_tokens": 50, "prompt_tokens": 10, "completion_tokens": 40}

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await service.generate(prompt="Explain AI", model="fast")

        assert result["success"] is True
        assert result["content"] == "Generated text"
        assert result["generated_text"] == "Generated text"

    async def test_generate_with_context(self, mock_config):
        """Test generate with structured context."""
        service = LLMService(config_path=mock_config)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response with context"
        mock_response.usage = {"total_tokens": 50, "prompt_tokens": 20, "completion_tokens": 30}

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=mock_response
        ) as mock_completion:
            result = await service.generate(
                prompt="Summarize",
                context={"topic": "AI", "length": "short"},
                model="main",
            )

        assert result["success"] is True
        # Verify context was included in the message
        call_args = mock_completion.call_args
        messages = call_args[1]["messages"]
        assert "topic" in messages[0]["content"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_service_with_real_config():
    """Integration test with actual config file."""
    config_path = "capstone/agent_v2/configs/llm_config.yaml"
    
    # Only run if config exists
    if not Path(config_path).exists():
        pytest.skip("Config file not found")
    
    service = LLMService(config_path=config_path)

    # Test model resolution
    assert service._resolve_model("main") is not None

    # Test parameter mapping
    params = service._get_model_parameters("gpt-4.1")
    assert "temperature" in params or "effort" in params

