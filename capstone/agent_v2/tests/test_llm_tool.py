"""Unit tests for LLMTool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from capstone.agent_v2.tools.llm_tool import LLMTool
from capstone.agent_v2.services.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    """Create mock LLMService for testing."""
    service = MagicMock(spec=LLMService)
    service.generate = AsyncMock()
    return service


@pytest.fixture
def llm_tool(mock_llm_service):
    """Create LLMTool instance for testing."""
    return LLMTool(llm_service=mock_llm_service, model_alias="main")


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
    async def test_successful_generation_without_context(self, llm_tool, mock_llm_service):
        """Test successful text generation without context."""
        # Mock service response
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Generated response text",
            "content": "Generated response text",
            "usage": {
                "total_tokens": 150,
                "prompt_tokens": 50,
                "completion_tokens": 100
            },
            "latency_ms": 250
        }
        
        result = await llm_tool.execute(prompt="What is AI?")

        # Verify success
        assert result["success"] is True
        assert result["generated_text"] == "Generated response text"
        assert result["tokens_used"] == 150
        assert result["prompt_tokens"] == 50
        assert result["completion_tokens"] == 100
        
        # Verify service was called correctly
        mock_llm_service.generate.assert_called_once()
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["prompt"] == "What is AI?"
        assert call_args.kwargs["model"] == "main"

    @pytest.mark.asyncio
    async def test_successful_generation_with_context(self, llm_tool, mock_llm_service):
        """Test text generation with context data."""
        context = {
            "documents": [
                {"title": "doc1.pdf", "chunks": 214},
                {"title": "doc2.pdf", "chunks": 15}
            ]
        }

        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "There are 2 documents: doc1.pdf and doc2.pdf",
            "usage": {"total_tokens": 200, "prompt_tokens": 120, "completion_tokens": 80}
        }
        
        result = await llm_tool.execute(
            prompt="List the documents",
            context=context
        )

        # Verify success
        assert result["success"] is True
        assert "doc1.pdf" in result["generated_text"] or "doc2.pdf" in result["generated_text"]

        # Verify context was passed to service
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["context"] == context

    @pytest.mark.asyncio
    async def test_complex_context_structures(self, llm_tool, mock_llm_service):
        """Test handling of complex nested context structures."""
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

        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Summary of nested data",
            "usage": {"total_tokens": 100, "prompt_tokens": 60, "completion_tokens": 40}
        }
        
        result = await llm_tool.execute(
            prompt="Summarize the data",
            context=context
        )

        # Verify success
        assert result["success"] is True
        
        # Verify context was passed to service
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["context"] == context

    @pytest.mark.asyncio
    async def test_parameter_handling(self, llm_tool, mock_llm_service):
        """Test that max_tokens and temperature parameters are passed correctly."""
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Test response",
            "usage": {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}
        }

        await llm_tool.execute(
            prompt="Test prompt",
            max_tokens=1000,
            temperature=0.9
        )

        # Verify parameters were passed
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["max_tokens"] == 1000
        assert call_args.kwargs["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_default_parameter_values(self, llm_tool, mock_llm_service):
        """Test that default values are used when parameters not provided."""
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Test response",
            "usage": {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}
        }

        await llm_tool.execute(prompt="Test prompt")

        # Verify default values were used
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["max_tokens"] == 500  # Default
        assert call_args.kwargs["temperature"] == 0.7  # Default

    @pytest.mark.asyncio
    async def test_llm_api_error_handling(self, llm_tool, mock_llm_service):
        """Test handling of LLM service failures."""
        # Mock service failure
        mock_llm_service.generate.return_value = {
            "success": False,
            "error": "API Error: Rate limit exceeded",
            "error_type": "RateLimitError"
        }

        result = await llm_tool.execute(prompt="Test prompt")

        # Verify error is handled gracefully
        assert result["success"] is False
        assert "API Error" in result["error"]
        assert "RateLimitError" in result["type"]
        assert "hints" in result
        assert len(result["hints"]) > 0

    @pytest.mark.asyncio
    async def test_token_limit_exceeded_error(self, llm_tool, mock_llm_service):
        """Test handling of token limit exceeded errors."""
        # Mock service failure with token error
        mock_llm_service.generate.return_value = {
            "success": False,
            "error": "Token limit exceeded",
            "error_type": "TokenLimitError"
        }

        result = await llm_tool.execute(prompt="Very long prompt...")

        # Verify error and hints
        assert result["success"] is False
        assert "Token limit exceeded" in result["error"]
        
        # Check for token-related hint
        hints_str = " ".join(result["hints"]).lower()
        assert "token" in hints_str or "reduce" in hints_str

    @pytest.mark.asyncio
    async def test_network_timeout_error(self, llm_tool, mock_llm_service):
        """Test handling of network timeout errors."""
        # Mock to raise timeout exception
        mock_llm_service.generate.side_effect = TimeoutError("Request timed out")

        result = await llm_tool.execute(prompt="Test prompt")

        # Verify error and hints
        assert result["success"] is False
        assert result["type"] == "TimeoutError"
        
        # Check for retry hint
        hints_str = " ".join(result["hints"]).lower()
        assert "retry" in hints_str or "network" in hints_str

    @pytest.mark.asyncio
    async def test_authentication_error(self, llm_tool, mock_llm_service):
        """Test handling of authentication errors."""
        # Mock service failure with auth error
        mock_llm_service.generate.return_value = {
            "success": False,
            "error": "Invalid API key",
            "error_type": "AuthenticationError"
        }

        result = await llm_tool.execute(prompt="Test prompt")

        # Verify error and hints
        assert result["success"] is False
        assert "Invalid API key" in result["error"]
        
        # Check for API key hint
        hints_str = " ".join(result["hints"]).lower()
        assert "api key" in hints_str or "credentials" in hints_str

    @pytest.mark.asyncio
    async def test_logging_metadata_not_full_text(self, llm_tool, mock_llm_service):
        """Test that logging captures metadata but not full text (privacy)."""
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Generated response",
            "usage": {"total_tokens": 100, "prompt_tokens": 60, "completion_tokens": 40}
        }

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
    async def test_context_serialization_with_string(self, llm_tool, mock_llm_service):
        """Test context serialization when context is already a string."""
        string_context = "This is plain text context"

        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Response",
            "usage": {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}
        }

        result = await llm_tool.execute(
            prompt="Test",
            context=string_context
        )

        # Verify string context was passed to service
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["context"] == string_context

    @pytest.mark.asyncio
    async def test_large_context_handling(self, llm_tool, mock_llm_service):
        """Test handling of large contexts passed to service."""
        # Create a large context (>2000 chars)
        large_context = {"data": "x" * 2500}

        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Response",
            "usage": {"total_tokens": 500, "prompt_tokens": 400, "completion_tokens": 100}
        }

        result = await llm_tool.execute(prompt="Test", context=large_context)

        # Verify large context was passed to service (service handles warnings)
        assert result["success"] is True
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["context"] == large_context

    @pytest.mark.asyncio
    async def test_usage_dict_extraction(self, llm_tool, mock_llm_service):
        """Test correct extraction of usage stats from service response."""
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Response",
            "usage": {
                "total_tokens": 150,
                "prompt_tokens": 100,
                "completion_tokens": 50
            }
        }

        result = await llm_tool.execute(prompt="Test")

        # Verify token counts extracted correctly
        assert result["success"] is True
        assert result["tokens_used"] == 150
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50

    @pytest.mark.asyncio
    async def test_uses_configured_model_alias(self, mock_llm_service):
        """Test that tool uses configured model alias."""
        tool = LLMTool(llm_service=mock_llm_service, model_alias="powerful")
        
        mock_llm_service.generate.return_value = {
            "success": True,
            "generated_text": "Response",
            "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5}
        }
        
        await tool.execute(prompt="Test")
        
        # Verify correct alias used
        call_args = mock_llm_service.generate.call_args
        assert call_args.kwargs["model"] == "powerful"

    @pytest.mark.asyncio
    async def test_unexpected_exception_handling(self, llm_tool, mock_llm_service):
        """Test handling of unexpected exceptions."""
        # Mock to raise exception
        mock_llm_service.generate.side_effect = RuntimeError("Unexpected error")
        
        result = await llm_tool.execute(prompt="Test")
        
        assert result["success"] is False
        assert result["type"] == "RuntimeError"
        assert "Unexpected error" in result["error"]

