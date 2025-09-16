# ============================================
# PYTHON CODE EXECUTION TOOL
# ============================================

from ast import Dict
from typing import Any
from capstone.agent_v2.tool import Tool


class PythonTool(Tool):
    """Execute Python code for complex operations"""
    
    @property
    def name(self) -> str:
        return "python"
    
    @property
    def description(self) -> str:
        return "Execute Python code for complex logic, data processing, and custom operations. Code should set 'result' variable."
    
    async def execute(self, code: str, context: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute Python code in controlled namespace.
        Code has access to standard libraries and must set 'result' variable.
        """
        
        # Create safe namespace
        safe_namespace = {
            "__builtins__": {
                # Basic functions
                "print": print, "len": len, "range": range, "enumerate": enumerate,
                "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict, "set": set, "tuple": tuple,
                "sum": sum, "min": min, "max": max, "abs": abs,
                "round": round, "sorted": sorted, "reversed": reversed,
                "zip": zip, "map": map, "filter": filter,
                "any": any, "all": all, "isinstance": isinstance,
                "open": open,  # Use with caution
                "__import__": __import__,
            },
            "context": context or {},
        }
        
        # Import common libraries
        import_code = """
import os, sys, json, re, pathlib, shutil
import subprocess, datetime, time, random
import base64, hashlib, tempfile, csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
"""
        
        try:
            # Execute imports
            exec(import_code, safe_namespace)
            
            # Execute user code
            exec(code, safe_namespace)
            
            # Extract result
            result_value = safe_namespace.get('result', None)
            
            # Get all user-defined variables
            user_vars = {
                k: v for k, v in safe_namespace.items()
                if not k.startswith('_') 
                and k not in ['os', 'sys', 'json', 're', 'pathlib', 'shutil',
                             'subprocess', 'datetime', 'time', 'random',
                             'base64', 'hashlib', 'tempfile', 'csv', 'Path',
                             'timedelta', 'Dict', 'List', 'Any', 'Optional', 'context']
            }
            
            return {
                "success": True,
                "result": result_value,
                "variables": user_vars,
                "context_updated": safe_namespace.get('context', {})
            }
            
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
