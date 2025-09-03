# ==================== LLM ABSTRACTION ====================

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
import structlog


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        pass
    
    @abstractmethod
    async def generate_structured_response(self, prompt: str, response_model: BaseModel, **kwargs) -> BaseModel:
        pass

    @abstractmethod
    async def call_tools(self, *, system_prompt: str, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Invoke vendor tool-calling if available.

        Returns a dict like {"name": str, "arguments": dict} when a tool is selected, otherwise None.
        """
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI/GPT implementation using official OpenAI SDK (no langchain)."""
    
    def __init__(self, api_key: str, model: str = "gpt-4.1", temperature: float = 0.1):
        from openai import AsyncOpenAI
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.logger = structlog.get_logger()
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        system_prompt = kwargs.get('system_prompt', '')
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            self.logger.error("llm_generation_failed", error=str(e))
            raise
    
    async def generate_structured_response(self, prompt: str, response_model: BaseModel, **kwargs) -> BaseModel:
        import json as _json
        
        # Support both model class and instance
        model_cls = response_model if isinstance(response_model, type) else response_model.__class__
        if hasattr(model_cls, 'model_json_schema'):
            schema = model_cls.model_json_schema()
        else:
            # Fallback for environments exposing .schema()
            schema = model_cls.schema()  # type: ignore[attr-defined]
        
        # 1) Preferred path: Vendor function-calling to force a validated JSON return
        # We expose a single function whose parameters are exactly the target schema.
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": kwargs.get('system_prompt', '')},
                    {"role": "user", "content": prompt},
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "return_structured",
                            "description": f"Return a JSON object that matches the provided schema for {model_cls.__name__}.",
                            "parameters": schema,
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": "return_structured"}},
            )
            choice = completion.choices[0]
            tool_calls = getattr(choice.message, "tool_calls", None)
            if tool_calls and len(tool_calls) > 0:
                args_str = tool_calls[0].function.arguments
                data = _json.loads(args_str)
                return model_cls(**data)
        except Exception as e:
            # Fall through to schema-guided JSON prompting
            self.logger.warning("openai_function_calling_failed", error=str(e), model=model_cls.__name__)
        
        # 2) Fallback: Schema-guided prompting with plain JSON response
        structured_prompt = f"""{prompt}
\nRespond with valid JSON matching this schema:
{_json.dumps(schema, indent=2)}
\nJSON Response:"""
        try:
            text = await self.generate_response(structured_prompt, **kwargs)
            json_str = text.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            data = _json.loads(json_str.strip())
            return model_cls(**data)
        except Exception as e:
            self.logger.error("structured_generation_failed", error=str(e), model=model_cls.__name__)
            raise

    async def call_tools(self, *, system_prompt: str, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Call OpenAI function/tool calling and return the chosen tool call if any."""
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                tools=tools,
                tool_choice="auto",
            )
            choice = completion.choices[0]
            tool_calls = getattr(choice.message, "tool_calls", None)
            if tool_calls and len(tool_calls) > 0:
                tool_call = tool_calls[0]
                name = tool_call.function.name
                import json as _json
                args = {}
                try:
                    args = _json.loads(tool_call.function.arguments or "{}")
                except Exception:
                    args = {}
                return {"name": name, "arguments": args}
            return None
        except Exception as e:
            self.logger.warning("openai_call_tools_failed", error=str(e))
            return None

class AnthropicProvider(LLMProvider):
    """Anthropic/Claude implementation"""
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229", temperature: float = 0.1):
        import anthropic
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.logger = structlog.get_logger()
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=self.temperature,
                system=kwargs.get('system_prompt', ''),
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            self.logger.error("anthropic_generation_failed", error=str(e))
            raise
    
    async def generate_structured_response(self, prompt: str, response_model: BaseModel, **kwargs) -> BaseModel:
        import json
        
        model_cls = response_model if isinstance(response_model, type) else response_model.__class__
        schema = model_cls.model_json_schema() if hasattr(model_cls, "model_json_schema") else model_cls.schema()  # type: ignore[attr-defined]
        structured_prompt = f"""{prompt}

Respond with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

JSON Response:"""
        
        try:
            response = await self.generate_response(structured_prompt, **kwargs)
            # Extract JSON from response
            json_str = response.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            
            data = json.loads(json_str.strip())
            return model_cls(**data)
        except Exception as e:
            self.logger.error("anthropic_structured_failed", error=str(e))
            raise

    async def call_tools(self, *, system_prompt: str, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Anthropic provider does not use function calling here; return None."""
        return None
