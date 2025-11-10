"""Unit tests for LLMTool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from capstone.agent_v2.tools.llm_tool import LLMTool


@pytest.fixture
def mock_llm():
    """Mock LLM instance for testing."""
    return MagicMock()


@pytest.fixture
def llm_tool(mock_llm):
    """Create LLMTool instance for testing."""
    return LLMTool(llm=mock_llm)


class TestLLMTool:
    """Test suite for LLMTool."""

    def test_tool_properties(self, llm_tool):
        """Test that tool properties are correctly defined."""
        assert llm_tool.name == "llm_generate"
        assert "natural language" in llm_tool.description.lower()
        assert "formulating user responses" in llm_tool.description.lower()
        assert "summarizing information" in llm_tool.description.lower()

    def test_parameters_schema_structure(self, llm_tool):
        """Test parameter schema has correct structure."""
        schema = llm_tool.parameters_schema

        # Check all properties are defined
        assert "prompt" in schema["properties"]
        assert "context" in schema["properties"]
        assert "max_tokens" in schema["properties"]
        assert "temperature" in schema["properties"]

        # Check types
        assert schema["properties"]["prompt"]["type"] == "string"
        assert schema["properties"]["context"]["type"] == "object"
        assert schema["properties"]["max_tokens"]["type"] == "integer"
        assert schema["properties"]["temperature"]["type"] == "number"

        # Check required fields
        assert schema["required"] == ["prompt"]

    @pytest.mark.asyncio
    async def test_successful_generation_without_context(self, llm_tool):
        """Test successful text generation without context."""
        # Mock litellm.acompletion response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated response text"
        mock_response.usage = {
            "total_tokens": 150,
            "prompt_tokens": 50,
            "completion_tokens": 100
        }

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            result = await llm_tool.execute(prompt="What is AI?")

        # Verify success
        assert result["success"] is True
        assert result["generated_text"] == "Generated response text"
        assert result["tokens_used"] == 150
        assert result["prompt_tokens"] == 50
        assert result["completion_tokens"] == 100

    @pytest.mark.asyncio
    async def test_successful_generation_with_context(self, llm_tool):
        """Test successful text generation with context."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "There are 2 documents: doc1.pdf and doc2.pdf"
        mock_response.usage = {
            "total_tokens": 200,
            "prompt_tokens": 120,
            "completion_tokens": 80
        }

        context = {
            "documents": [
                {"title": "doc1.pdf", "chunks": 214},
                {"title": "doc2.pdf", "chunks": 15}
            ]
        }

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_acompletion:
            result = await llm_tool.execute(
                prompt="List the documents",
                context=context
            )

        # Verify success
        assert result["success"] is True
        assert "doc1.pdf" in result["generated_text"] or "doc2.pdf" in result["generated_text"]

        # Verify context was included in the prompt
        call_args = mock_acompletion.call_args
        prompt_sent = call_args.kwargs["messages"][0]["content"]
        assert "Context Data:" in prompt_sent
        assert "doc1.pdf" in prompt_sent
        assert "doc2.pdf" in prompt_sent

    @pytest.mark.asyncio
    async def test_complex_context_structures(self, llm_tool):
        """Test handling of complex nested context structures."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary of nested data"
        mock_response.usage = {"total_tokens": 100, "prompt_tokens": 60, "completion_tokens": 40}

        # Complex nested context
        context = {
            "results": [
                {
                    "id": "1",
                    "data": {
                        "nested": {
                            "values": [1, 2, 3]
                        }
                    }
                },
                {
                    "id": "2",
                    "data": {
                        "nested": {
                            "values": [4, 5, 6]
                        }
                    }
                }
            ]
        }

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_acompletion:
            result = await llm_tool.execute(
                prompt="Summarize the data",
                context=context
            )

        # Verify success and JSON serialization worked
        assert result["success"] is True
        
        # Verify context was serialized as JSON
        call_args = mock_acompletion.call_args
        prompt_sent = call_args.kwargs["messages"][0]["content"]
        assert '"results"' in prompt_sent
        assert '"nested"' in prompt_sent

    @pytest.mark.asyncio
    async def test_parameter_handling(self, llm_tool):
        """Test that max_tokens and temperature parameters are passed correctly."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_acompletion:
            await llm_tool.execute(
                prompt="Test prompt",
                max_tokens=1000,
                temperature=0.9
            )

        # Verify parameters were passed
        call_args = mock_acompletion.call_args
        assert call_args.kwargs["max_tokens"] == 1000
        assert call_args.kwargs["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_default_parameter_values(self, llm_tool):
        """Test that default values are used when parameters not provided."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_acompletion:
            await llm_tool.execute(prompt="Test prompt")

        # Verify default values were used
        call_args = mock_acompletion.call_args
        assert call_args.kwargs["max_tokens"] == 500  # Default
        assert call_args.kwargs["temperature"] == 0.7  # Default

    @pytest.mark.asyncio
    async def test_llm_api_error_handling(self, llm_tool):
        """Test handling of LLM API failures."""
        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("API Error: Rate limit exceeded")):
            result = await llm_tool.execute(prompt="Test prompt")

        # Verify error is handled gracefully
        assert result["success"] is False
        assert "API Error" in result["error"]
        assert result["type"] == "Exception"
        assert "hints" in result
        assert len(result["hints"]) > 0

    @pytest.mark.asyncio
    async def test_token_limit_exceeded_error(self, llm_tool):
        """Test handling of token limit exceeded errors."""
        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("Token limit exceeded")):
            result = await llm_tool.execute(prompt="Very long prompt...")

        # Verify error and hints
        assert result["success"] is False
        assert "Token limit exceeded" in result["error"]
        
        # Check for token-related hint
        hints_str = " ".join(result["hints"]).lower()
        assert "token" in hints_str or "reduce" in hints_str

    @pytest.mark.asyncio
    async def test_network_timeout_error(self, llm_tool):
        """Test handling of network timeout errors."""
        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=TimeoutError("Request timed out")):
            result = await llm_tool.execute(prompt="Test prompt")

        # Verify error and hints
        assert result["success"] is False
        assert result["type"] == "TimeoutError"
        
        # Check for retry hint
        hints_str = " ".join(result["hints"]).lower()
        assert "retry" in hints_str or "network" in hints_str

    @pytest.mark.asyncio
    async def test_authentication_error(self, llm_tool):
        """Test handling of authentication errors."""
        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("Invalid API key")):
            result = await llm_tool.execute(prompt="Test prompt")

        # Verify error and hints
        assert result["success"] is False
        assert "Invalid API key" in result["error"]
        
        # Check for API key hint
        hints_str = " ".join(result["hints"]).lower()
        assert "api key" in hints_str or "credentials" in hints_str

    @pytest.mark.asyncio
    async def test_logging_metadata_not_full_text(self, llm_tool):
        """Test that logging captures metadata but not full text (privacy)."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated response"
        mock_response.usage = {"total_tokens": 100, "prompt_tokens": 60, "completion_tokens": 40}

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            with patch.object(llm_tool.logger, "info") as mock_log_info:
                await llm_tool.execute(prompt="Secret prompt", context={"secret": "data"})

                # Verify logging was called
                assert mock_log_info.called
                
                # Get all log calls
                log_calls = [call[0] for call in mock_log_info.call_args_list]
                
                # Verify privacy: full text should NOT be in logs
                for call_args in log_calls:
                    if len(call_args) > 0:
                        # First arg is the event name, check it's not the actual prompt
                        assert call_args[0] != "Secret prompt"

    @pytest.mark.asyncio
    async def test_tool_schema_validation(self, llm_tool):
        """Test that tool schema is valid for OpenAI function calling."""
        schema = llm_tool.function_tool_schema

        # Verify structure
        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "llm_generate"
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]
        
        # Verify parameters schema
        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params
        assert "prompt" in params["required"]

    @pytest.mark.asyncio
    async def test_context_serialization_with_string(self, llm_tool):
        """Test context serialization when context is already a string."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}

        string_context = "This is plain text context"

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_acompletion:
            result = await llm_tool.execute(
                prompt="Test",
                context=string_context
            )

        # Verify string context was used directly
        call_args = mock_acompletion.call_args
        prompt_sent = call_args.kwargs["messages"][0]["content"]
        assert "This is plain text context" in prompt_sent

    @pytest.mark.asyncio
    async def test_large_context_warning(self, llm_tool):
        """Test that large contexts trigger a warning log."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = {"total_tokens": 500, "prompt_tokens": 400, "completion_tokens": 100}

        # Create a large context (>2000 chars)
        large_context = {"data": "x" * 2500}

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            with patch.object(llm_tool.logger, "warning") as mock_log_warning:
                await llm_tool.execute(prompt="Test", context=large_context)

                # Verify warning was logged for large context
                assert mock_log_warning.called
                
                # Check that the warning mentions large context
                warning_calls = [str(call) for call in mock_log_warning.call_args_list]
                assert any("large_context" in str(call).lower() for call in warning_calls)

    @pytest.mark.asyncio
    async def test_usage_as_object_attribute(self, llm_tool):
        """Test handling when usage is an object with attributes (not dict)."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        
        # Create usage as object with attributes
        mock_usage = MagicMock()
        mock_usage.total_tokens = 150
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_response.usage = mock_usage

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            result = await llm_tool.execute(prompt="Test")

        # Verify token counts extracted correctly
        assert result["success"] is True
        assert result["tokens_used"] == 150
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50

