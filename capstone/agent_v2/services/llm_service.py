"""
LLM Service for centralized LLM interactions.

This module provides a centralized service for all LLM interactions with support
for model-aware parameter mapping, retry logic, and configuration management.
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import litellm
import structlog
import yaml


@dataclass
class RetryPolicy:
    """Retry policy configuration."""

    max_attempts: int = 3
    backoff_multiplier: float = 2.0
    timeout: int = 30
    retry_on_errors: List[str] = field(default_factory=list)


class LLMService:
    """
    Centralized service for LLM interactions with model-aware parameter mapping.

    Supports both GPT-4 (traditional parameters) and GPT-5 (reasoning parameters).
    Provides unified interface for all LLM calls with retry logic and error handling.
    """

    def __init__(self, config_path: str = "configs/llm_config.yaml"):
        """
        Initialize LLMService with configuration.

        Args:
            config_path: Path to YAML configuration file

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        self.logger = structlog.get_logger()
        self._load_config(config_path)
        self._initialize_provider()

        self.logger.info(
            "llm_service_initialized",
            default_model=self.default_model,
            model_aliases=list(self.models.keys()),
        )

    def _load_config(self, config_path: str) -> None:
        """
        Load and validate configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"LLM config not found: {config_path}")

        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Validate config structure
        if config is None:
            raise ValueError(f"Config file is empty or invalid: {config_path}")

        # Extract configuration sections
        self.default_model = config.get("default_model", "main")
        self.models = config.get("models", {})
        self.model_params = config.get("model_params", {})
        self.default_params = config.get("default_params", {})

        # Validate essential config
        if not self.models:
            raise ValueError("Config must define at least one model in 'models' section")

        # Retry policy
        retry_config = config.get("retry_policy", {})
        self.retry_policy = RetryPolicy(
            max_attempts=retry_config.get("max_attempts", 3),
            backoff_multiplier=retry_config.get("backoff_multiplier", 2.0),
            timeout=retry_config.get("timeout", 30),
            retry_on_errors=retry_config.get("retry_on_errors", []),
        )

        # Logging preferences
        self.logging_config = config.get("logging", {})

        # Provider configuration
        self.provider_config = config.get("providers", {})
        
        # Validate Azure configuration if enabled
        self._validate_azure_config()

    def _validate_azure_config(self) -> None:
        """
        Validate Azure configuration if enabled.
        
        Raises:
            ValueError: If Azure is enabled but required fields are missing
        """
        azure_config = self.provider_config.get("azure", {})
        
        # Skip validation if Azure is not enabled or section doesn't exist
        if not azure_config or not azure_config.get("enabled", False):
            return
        
        # Required fields when Azure is enabled
        required_fields = ["api_key_env", "endpoint_url_env", "api_version", "deployment_mapping"]
        missing_fields = []
        
        for field in required_fields:
            if field not in azure_config or azure_config[field] is None:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(
                f"Azure provider is enabled but missing required fields: {', '.join(missing_fields)}. "
                "Please provide all required fields or set enabled: false."
            )
        
        # Validate deployment_mapping is a dictionary
        if not isinstance(azure_config["deployment_mapping"], dict):
            raise ValueError(
                "Azure deployment_mapping must be a dictionary mapping model aliases to deployment names"
            )
        
        self.logger.info(
            "azure_config_validated",
            endpoint_env=azure_config["api_key_env"],
            api_version=azure_config["api_version"],
            deployment_count=len(azure_config["deployment_mapping"]),
        )
    
    def _initialize_provider(self) -> None:
        """Initialize LLM provider with API keys from environment."""
        # Check if Azure is enabled
        azure_config = self.provider_config.get("azure", {})
        if azure_config.get("enabled", False):
            self._initialize_azure_provider()
            self.logger.info(
                "provider_selected",
                provider="azure",
                api_version=azure_config.get("api_version"),
            )
        else:
            # Default to OpenAI
            openai_config = self.provider_config.get("openai", {})

            # Load API key from environment
            api_key_env = openai_config.get("api_key_env", "OPENAI_API_KEY")
            api_key = os.getenv(api_key_env)

            if not api_key:
                self.logger.warning(
                    "openai_api_key_missing",
                    env_var=api_key_env,
                    hint="Set environment variable for API access",
                )
            
            self.logger.info("provider_selected", provider="openai")

    def _initialize_azure_provider(self) -> None:
        """
        Initialize Azure OpenAI provider with credentials from environment.
        
        Reads Azure-specific environment variables, validates endpoint URL format,
        and configures LiteLLM for Azure OpenAI support.
        
        Raises:
            ValueError: If endpoint URL format is invalid
        """
        azure_config = self.provider_config.get("azure", {})
        
        # Get environment variable names from config
        api_key_env = azure_config.get("api_key_env", "AZURE_OPENAI_API_KEY")
        endpoint_env = azure_config.get("endpoint_url_env", "AZURE_OPENAI_ENDPOINT")
        
        # Read from environment
        self.azure_api_key = os.getenv(api_key_env)
        self.azure_endpoint = os.getenv(endpoint_env)
        self.azure_api_version = azure_config.get("api_version")
        
        # Warn if credentials are missing
        if not self.azure_api_key:
            self.logger.warning(
                "azure_api_key_missing",
                env_var=api_key_env,
                hint="Set environment variable for Azure OpenAI API access",
            )
        
        if not self.azure_endpoint:
            self.logger.warning(
                "azure_endpoint_missing",
                env_var=endpoint_env,
                hint="Set environment variable for Azure OpenAI endpoint URL",
            )
        
        # Validate endpoint URL format if provided
        if self.azure_endpoint:
            # Azure endpoint should be HTTPS and contain 'openai.azure.com'
            if not self.azure_endpoint.startswith("https://"):
                raise ValueError(
                    f"Azure endpoint must use HTTPS protocol: {self.azure_endpoint}"
                )
            
            if "openai.azure.com" not in self.azure_endpoint and "api.cognitive.microsoft.com" not in self.azure_endpoint:
                self.logger.warning(
                    "azure_endpoint_format_unusual",
                    endpoint=self.azure_endpoint,
                    hint="Expected endpoint to contain 'openai.azure.com' or 'api.cognitive.microsoft.com'",
                )
        
        # Set LiteLLM environment variables for Azure OpenAI
        # LiteLLM uses these for Azure OpenAI requests
        if self.azure_api_key:
            os.environ["AZURE_API_KEY"] = self.azure_api_key
        
        if self.azure_endpoint:
            os.environ["AZURE_API_BASE"] = self.azure_endpoint
        
        if self.azure_api_version:
            os.environ["AZURE_API_VERSION"] = self.azure_api_version
        
        self.logger.info(
            "azure_provider_initialized",
            endpoint=self.azure_endpoint,
            api_version=self.azure_api_version,
            api_key_set=bool(self.azure_api_key),
        )

    def _resolve_model(self, model_alias: Optional[str]) -> str:
        """
        Resolve model alias to actual model name or Azure deployment name.
        
        When Azure provider is enabled:
        - Resolves model alias through Azure deployment_mapping
        - Falls back to OpenAI model name if alias not in deployment_mapping
        - Raises ValueError if Azure enabled and alias has no deployment mapping (strict mode)
        
        When Azure provider is disabled:
        - Uses traditional OpenAI model name resolution
        
        Args:
            model_alias: Model alias or None (uses default)
        
        Returns:
            Actual model name (OpenAI) or deployment name (Azure)
        
        Raises:
            ValueError: If Azure enabled and alias has no deployment mapping
        """
        if model_alias is None:
            model_alias = self.default_model
        
        # Check if Azure is enabled
        azure_config = self.provider_config.get("azure", {})
        azure_enabled = azure_config.get("enabled", False)
        
        if azure_enabled:
            # Azure provider: resolve through deployment_mapping
            deployment_mapping = azure_config.get("deployment_mapping", {})
            
            # First, resolve alias to OpenAI model name
            openai_model = self.models.get(model_alias, model_alias)
            
            # Check if deployment mapping exists for this alias
            if model_alias in deployment_mapping:
                deployment_name = deployment_mapping[model_alias]
                
                self.logger.info(
                    "model_resolved",
                    provider="azure",
                    model_alias=model_alias,
                    deployment_name=deployment_name,
                    openai_model=openai_model,
                )
                
                return f"azure/{deployment_name}"
            else:
                # No deployment mapping for this alias
                # Check if fallback to OpenAI model name is allowed
                # (For now, we'll be strict and raise an error)
                raise ValueError(
                    f"Azure provider is enabled but no deployment mapping found for model alias '{model_alias}'. "
                    f"Please add '{model_alias}' to deployment_mapping in azure provider configuration, "
                    f"or set azure.enabled to false to use OpenAI models."
                )
        else:
            # OpenAI provider: traditional resolution
            resolved_model = self.models.get(model_alias, model_alias)
            
            self.logger.info(
                "model_resolved",
                provider="openai",
                model_alias=model_alias,
                resolved_model=resolved_model,
            )
            
            return resolved_model

    def _get_model_parameters(self, model: str) -> Dict[str, Any]:
        """
        Get parameters for specific model.

        Args:
            model: Actual model name

        Returns:
            Model-specific parameters or defaults
        """
        # Check for exact model match
        if model in self.model_params:
            return self.model_params[model].copy()

        # Check for model family match (e.g., "gpt-4" matches "gpt-4-turbo")
        for model_key, params in self.model_params.items():
            if model.startswith(model_key):
                return params.copy()

        # Fallback to defaults
        return self.default_params.copy()

    def _map_parameters_for_model(
        self, model: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Map parameters based on model family (GPT-4 vs GPT-5).

        GPT-4 uses traditional parameters: temperature, top_p, max_tokens, etc.
        GPT-5 uses new parameters: effort, reasoning, max_tokens.

        Args:
            model: Actual model name
            params: Input parameters (may contain traditional or new parameters)

        Returns:
            Mapped parameters suitable for the model
        """
        # Detect GPT-5 models
        if "gpt-5" in model.lower():
            mapped = {}

            # Max tokens is universal
            if "max_tokens" in params:
                mapped["max_tokens"] = params["max_tokens"]

            # Map temperature to effort if temperature provided
            # Ranges: <0.3=low, 0.3-0.7=medium, >0.7=high
            if "temperature" in params and "effort" not in params:
                temp = params["temperature"]
                if temp < 0.3:
                    mapped["effort"] = "low"
                elif temp <= 0.7:
                    mapped["effort"] = "medium"
                else:
                    mapped["effort"] = "high"

                if self.logging_config.get("log_parameter_mapping", True):
                    self.logger.info(
                        "parameter_mapped_gpt5",
                        model=model,
                        temperature=temp,
                        mapped_effort=mapped["effort"],
                    )

            # Use configured effort/reasoning if available
            if "effort" in params:
                mapped["effort"] = params["effort"]
            if "reasoning" in params:
                mapped["reasoning"] = params["reasoning"]

            # Log if deprecated parameters were provided
            deprecated = [
                k
                for k in params.keys()
                if k
                in [
                    "temperature",
                    "top_p",
                    "logprobs",
                    "frequency_penalty",
                    "presence_penalty",
                ]
            ]
            if deprecated and self.logging_config.get("log_parameter_mapping", True):
                self.logger.warning(
                    "deprecated_parameters_ignored_gpt5",
                    model=model,
                    deprecated_params=deprecated,
                    hint="These parameters are not supported by GPT-5",
                )

            return mapped
        else:
            # GPT-4 and other models: use traditional parameters
            allowed_params = [
                "temperature",
                "top_p",
                "max_tokens",
                "frequency_penalty",
                "presence_penalty",
            ]
            return {k: v for k, v in params.items() if k in allowed_params}

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform LLM completion with retry logic.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model alias or None (uses default)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Dict with:
            - success: bool
            - content: str (if successful)
            - usage: Dict with token counts
            - error: str (if failed)

        Example:
            >>> result = await llm_service.complete(
            ...     messages=[
            ...         {"role": "system", "content": "You are helpful"},
            ...         {"role": "user", "content": "Hello"}
            ...     ],
            ...     model="main",
            ...     temperature=0.7
            ... )
        """
        # Resolve model and parameters
        actual_model = self._resolve_model(model)
        base_params = self._get_model_parameters(actual_model)

        # Merge with provided kwargs (kwargs override base_params)
        merged_params = {**base_params, **kwargs}

        # Map parameters for model family
        final_params = self._map_parameters_for_model(actual_model, merged_params)

        # Retry logic
        for attempt in range(self.retry_policy.max_attempts):
            try:
                start_time = time.time()

                self.logger.info(
                    "llm_completion_started",
                    model=actual_model,
                    attempt=attempt + 1,
                    message_count=len(messages),
                )

                # Call LiteLLM
                response = await litellm.acompletion(
                    model=actual_model,
                    messages=messages,
                    timeout=self.retry_policy.timeout,
                    **final_params,
                )

                # Extract content and usage
                content = response.choices[0].message.content
                usage = getattr(response, "usage", {})

                # Handle both dict and object forms
                if isinstance(usage, dict):
                    token_stats = usage
                else:
                    token_stats = {
                        "total_tokens": getattr(usage, "total_tokens", 0),
                        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage, "completion_tokens", 0),
                    }

                latency_ms = int((time.time() - start_time) * 1000)

                if self.logging_config.get("log_token_usage", True):
                    self.logger.info(
                        "llm_completion_success",
                        model=actual_model,
                        tokens=token_stats.get("total_tokens", 0),
                        latency_ms=latency_ms,
                    )

                return {
                    "success": True,
                    "content": content,
                    "usage": token_stats,
                    "model": actual_model,
                    "latency_ms": latency_ms,
                }

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)

                # Check if should retry (check both error type and message)
                should_retry = attempt < self.retry_policy.max_attempts - 1 and any(
                    err_type in error_type or err_type in error_msg
                    for err_type in self.retry_policy.retry_on_errors
                )

                if should_retry:
                    backoff_time = self.retry_policy.backoff_multiplier**attempt
                    self.logger.warning(
                        "llm_completion_retry",
                        model=actual_model,
                        error_type=error_type,
                        attempt=attempt + 1,
                        backoff_seconds=backoff_time,
                    )
                    await asyncio.sleep(backoff_time)
                else:
                    self.logger.error(
                        "llm_completion_failed",
                        model=actual_model,
                        error_type=error_type,
                        error=error_msg[:200],
                        attempts=attempt + 1,
                    )

                    return {
                        "success": False,
                        "error": error_msg,
                        "error_type": error_type,
                        "model": actual_model,
                    }

        # Should not reach here, but handle anyway
        return {
            "success": False,
            "error": "Max retries exceeded",
            "model": actual_model,
        }

    async def generate(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate text from a single prompt (convenience wrapper).

        Args:
            prompt: The prompt text
            context: Optional structured context to include
            model: Model alias or None (uses default)
            **kwargs: Additional parameters

        Returns:
            Same as complete()

        Example:
            >>> result = await llm_service.generate(
            ...     prompt="Explain quantum computing",
            ...     model="fast",
            ...     max_tokens=500
            ... )
        """
        # Format prompt with context if provided
        if context:
            context_str = yaml.dump(context, default_flow_style=False)
            full_prompt = f"""Context:
{context_str}

Task: {prompt}
"""
        else:
            full_prompt = prompt

        # Use complete() method
        messages = [{"role": "user", "content": full_prompt}]
        result = await self.complete(messages, model=model, **kwargs)

        # Alias 'content' to 'generated_text' for compatibility
        if result.get("success"):
            result["generated_text"] = result["content"]

        return result

