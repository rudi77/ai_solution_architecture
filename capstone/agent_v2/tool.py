# ============================================
# BASE TOOL INTERFACE
# ============================================

from abc import ABC, abstractmethod
import inspect
from typing import Any, Optional, Dict, List, Tuple


class Tool(ABC):
    """Base class for all tools"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        pass
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """Override to provide custom parameter schema for OpenAI function calling"""
        return self._generate_schema_from_signature()
    
    def _generate_schema_from_signature(self) -> Dict[str, Any]:
        """Auto-generate parameter schema from execute method signature"""
        sig = inspect.signature(self.execute)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'kwargs']:
                continue
            
            # Determine parameter type
            param_type = "string"  # Default
            param_desc = f"Parameter {param_name}"
            
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == Dict or param.annotation == dict:
                    param_type = "object"
                elif param.annotation == List or param.annotation == list:
                    param_type = "array"
            
            properties[param_name] = {
                "type": param_type,
                "description": param_desc
            }
            
            # Check if required
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }

    @property
    def function_tool_schema(self) -> Dict[str, Any]:
        """Return full OpenAI function tool schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        pass
    
    async def execute_safe(self, **kwargs) -> Dict[str, Any]:
        """
        Robust wrapper um execute() mit:
        - Validation
        - Retry-Logik
        - Error Handling
        - Timeout
        """
        import asyncio
        import traceback
        
        max_retries = 3
        timeout_seconds = 60
        
        for attempt in range(max_retries):
            try:
                # 1. Parameter validieren
                valid, error = self.validate_params(**kwargs)
                if not valid:
                    return {
                        "success": False,
                        "error": f"Invalid parameters: {error}",
                        "tool": self.name
                    }
                
                # 2. Execute mit Timeout
                result = await asyncio.wait_for(
                    self.execute(**kwargs),
                    timeout=timeout_seconds
                )
                
                # 3. Result validieren
                if not isinstance(result, dict):
                    return {
                        "success": False,
                        "error": f"Tool returned invalid type: {type(result)}",
                        "tool": self.name
                    }
                
                if "success" not in result:
                    result["success"] = False  # Default to False
                
                result["tool"] = self.name
                result["attempt"] = attempt + 1
                
                return result
                
            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": f"Tool timed out after {timeout_seconds}s",
                        "tool": self.name,
                        "retries": attempt + 1
                    }
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "traceback": traceback.format_exc(),
                        "tool": self.name,
                        "retries": attempt + 1
                    }
                await asyncio.sleep(2 ** attempt)
        
        return {"success": False, "error": "Should not reach here"}
    
    def validate_params(self, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate parameters before execution"""
        sig = inspect.signature(self.execute)
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'kwargs']:
                continue
            
            if param.default == inspect.Parameter.empty and param_name not in kwargs:
                return False, f"Missing required parameter: {param_name}"
        
        return True, None
