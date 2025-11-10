# ============================================
# LLM TEXT GENERATION TOOL
# ============================================

import json
import time
from typing import Any, Dict, Optional
import structlog
import litellm
from capstone.agent_v2.tool import Tool


class LLMTool(Tool):
    """Generic LLM tool for natural language text generation"""
    
    def __init__(self, llm, model: str = "gpt-4.1"):
        """
        Initialize LLMTool with an LLM instance.
        
        Args:
            llm: The LLM instance (typically litellm or a configured LLM provider)
            model: The LLM model to use (default: "gpt-4.1")
        """
        self.llm = llm
        self.model = model
        self.logger = structlog.get_logger()
    
    @property
    def name(self) -> str:
        return "llm_generate"
    
    @property
    def description(self) -> str:
        return (
            "Use the LLM to generate natural language text based on a prompt. "
            "Useful for: formulating user responses, summarizing information, "
            "formatting data, translating content, creative writing."
        )
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """Override to provide detailed parameter descriptions"""
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt/instruction for the LLM"
                },
                "context": {
                    "type": "object",
                    "description": "Structured data to include as context (e.g., search results, document lists)"
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum response length in tokens (default: 500)"
                },
                "temperature": {
                    "type": "number",
                    "description": "Creativity control from 0.0 (deterministic) to 1.0 (creative) (default: 0.7)"
                }
            },
            "required": ["prompt"]
        }
    
    async def execute(
        self, 
        prompt: str, 
        context: Optional[Dict[str, Any]] = None, 
        max_tokens: int = 500, 
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute LLM text generation.
        
        Args:
            prompt: The prompt/instruction for the LLM
            context: Optional structured data to include as context
            max_tokens: Maximum response length (default: 500)
            temperature: Creativity control 0.0-1.0 (default: 0.7)
            
        Returns:
            Dictionary with:
            - success: True if generation succeeded, False otherwise
            - generated_text: The generated text (if successful)
            - tokens_used: Total tokens consumed
            - prompt_tokens: Tokens in the prompt
            - completion_tokens: Tokens in the completion
            - error: Error message (if failed)
            - type: Error type (if failed)
            - hints: Suggestions for fixing errors (if failed)
            
        Example:
            >>> tool = LLMTool(llm=litellm)
            >>> result = await tool.execute(
            ...     prompt="Summarize this data",
            ...     context={"documents": [{"title": "doc1.pdf", "chunks": 214}]}
            ... )
            >>> print(result["generated_text"])
        """
        start_time = time.time()
        
        try:
            # Build full prompt with context if provided
            context_str = ""
            if context:
                context_str = self._serialize_context(context)
                full_prompt = f"""Context Data:
{context_str}

Task: {prompt}
"""
            else:
                full_prompt = prompt
            
            # Log metadata only (privacy-safe)
            context_size = len(context_str)
            self.logger.info(
                "llm_generate_started",
                tool="llm_generate",
                prompt_length=len(full_prompt),
                has_context=context is not None,
                context_size=context_size
            )
            
            # Warn about large contexts
            if context_size > 2000:
                self.logger.warning(
                    "llm_generate_large_context",
                    context_size=context_size,
                    hint="Consider reducing context size for better performance"
                )
            
            # Call LLM using litellm.acompletion
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            # Extract text and token counts
            generated_text = response.choices[0].message.content
            usage = response.usage if hasattr(response, 'usage') else {}
            
            # Handle both dict and object forms of usage
            if isinstance(usage, dict):
                tokens_used = usage.get("total_tokens", 0)
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
            else:
                tokens_used = getattr(usage, "total_tokens", 0)
                prompt_tokens = getattr(usage, "prompt_tokens", 0)
                completion_tokens = getattr(usage, "completion_tokens", 0)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            self.logger.info(
                "llm_generate_completed",
                tokens_used=tokens_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms
            )
            
            return {
                "success": True,
                "generated_text": generated_text,
                "tokens_used": tokens_used,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens
            }
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_type = type(e).__name__
            error_msg = str(e)
            
            self.logger.error(
                "llm_generate_failed",
                error_type=error_type,
                error=error_msg[:200],  # Truncate for logging
                latency_ms=latency_ms
            )
            
            # Determine hints based on error type
            hints = self._get_error_hints(error_type, error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "type": error_type,
                "hints": hints
            }
    
    def _serialize_context(self, context: Any) -> str:
        """
        Serialize context to a clean JSON string.
        
        Args:
            context: Context data (dict, list, or string)
            
        Returns:
            JSON-formatted string representation
        """
        if isinstance(context, str):
            return context
        
        try:
            return json.dumps(context, indent=2, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # Fallback to string representation if not JSON-serializable
            self.logger.warning(
                "context_serialization_fallback",
                error=str(e),
                hint="Context is not JSON-serializable, using string representation"
            )
            return str(context)
    
    def _get_error_hints(self, error_type: str, error_msg: str) -> list:
        """
        Generate helpful hints based on error type.
        
        Args:
            error_type: The type of exception
            error_msg: The error message
            
        Returns:
            List of hint strings
        """
        hints = ["Check LLM configuration", "Verify API credentials"]
        
        # Token limit errors
        if "token" in error_msg.lower() or "length" in error_msg.lower():
            hints.append("Reduce prompt size or increase max_tokens parameter")
        
        # Network/timeout errors
        if error_type in ["TimeoutError", "ConnectionError", "ClientError"]:
            hints.append("Retry the request")
            hints.append("Check network connectivity")
        
        # Authentication errors
        if "auth" in error_msg.lower() or "api key" in error_msg.lower():
            hints.append("Verify API key is set correctly")
        
        return hints

