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
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        pass
    
    def validate_params(self, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate parameters before execution"""
        sig = inspect.signature(self.execute)
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'kwargs']:
                continue
            
            if param.default == inspect.Parameter.empty and param_name not in kwargs:
                return False, f"Missing required parameter: {param_name}"
        
        return True, None
