# ============================================
# PYTHON CODE EXECUTION TOOL
# ============================================
from typing import Any, Dict
import os
from pathlib import Path
from capstone.agent_v2.tool import Tool


class PythonTool(Tool):
    """Execute Python code for complex operations"""
    
    @property
    def name(self) -> str:
        return "python"
    
    @property
    def description(self) -> str:
        return (
            "Execute Python code for complex logic, data processing, and custom operations. "
            "Your code must assign the final output to a variable named 'result'. "
            "Pre-imported modules: os, sys, json, re, pathlib, shutil, subprocess, datetime, time, random, "
            "base64, hashlib, tempfile, csv, pandas as pd, matplotlib.pyplot as plt, and typing types (Dict, List, Any, Optional); "
            "from datetime: datetime, timedelta. "
            "Builtins available include common utilities (print, len, range, enumerate, str, int, float, bool, list, dict, set, tuple, "
            "sum, min, max, abs, round, sorted, reversed, zip, map, filter, next, any, all, isinstance, open, __import__, locals). "
            "If you need input variables (e.g., 'data'), pass them in via the 'context' dict; its keys are exposed as top-level variables."
        )
    
    async def execute(self, code: str, context: Dict[str, Any] = None, cwd: str = None, **kwargs) -> Dict[str, Any]:
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
                "next": next,
                "any": any, "all": all, "isinstance": isinstance,
                "open": open,  # Use with caution
                "__import__": __import__,
                "locals": locals,
            },
            "context": context or {},
        }

        # Expose context keys as top-level variables when safe
        if context:
            for key, value in context.items():
                if isinstance(key, str) and key.isidentifier() and key not in safe_namespace:
                    safe_namespace[key] = value
        
        # Import common libraries
        import_code = """
import os, sys, json, re, pathlib, shutil
import subprocess, datetime, time, random
import base64, hashlib, tempfile, csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import matplotlib.pyplot as plt
"""
        
        # Optionally change working directory
        original_cwd = os.getcwd()
        cwd_path = None
        if cwd is not None:
            if not isinstance(cwd, str):
                return {"success": False, "error": "cwd must be a string path"}
            sanitized = cwd.strip()
            if (sanitized.startswith('"') and sanitized.endswith('"')) or (sanitized.startswith("'") and sanitized.endswith("'")):
                sanitized = sanitized[1:-1]
            sanitized = os.path.expandvars(os.path.expanduser(sanitized))
            if os.name == "nt":
                sanitized = sanitized.replace("/", "\\")
            p = Path(sanitized)
            if not p.exists() or not p.is_dir():
                return {"success": False, "error": f"cwd does not exist or is not a directory: {sanitized}"}
            cwd_path = str(p)

        try:
            if cwd_path:
                os.chdir(cwd_path)
            # Execute imports
            exec(import_code, safe_namespace)
            
            # Execute user code
            exec(code, safe_namespace)
            
            # Extract result and sanitize outputs to ensure they are pickle/JSON safe
            def _sanitize(value, depth: int = 0):
                if depth > 4:
                    return repr(value)
                # Simple primitives
                if value is None or isinstance(value, (bool, int, float, str)):
                    return value
                # Bytes → decode to utf-8 (fallback to repr)
                if isinstance(value, (bytes, bytearray)):
                    try:
                        return bytes(value).decode('utf-8', errors='replace')
                    except Exception:
                        return repr(value)
                # Paths → str
                if isinstance(value, Path):
                    return str(value)
                # Collections
                if isinstance(value, (list, tuple, set)):
                    return [_sanitize(v, depth + 1) for v in value]
                if isinstance(value, dict):
                    return {
                        str(_sanitize(k, depth + 1)): _sanitize(v, depth + 1)
                        for k, v in value.items()
                    }
                # Fallback: ensure JSON-safe by stringifying unknown objects
                try:
                    return repr(value)
                except Exception:
                    return f"<unserializable {type(value).__name__}>"

            result_value = _sanitize(safe_namespace.get('result', None))

            # Get all user-defined variables
            raw_user_vars = {
                k: v for k, v in safe_namespace.items()
                if not k.startswith('_') 
                and k not in ['os', 'sys', 'json', 're', 'pathlib', 'shutil',
                             'subprocess', 'datetime', 'time', 'random',
                             'base64', 'hashlib', 'tempfile', 'csv', 'Path', 'pd', 'plt',
                             'timedelta', 'Dict', 'List', 'Any', 'Optional', 'context']
            }
            user_vars = {k: _sanitize(v) for k, v in raw_user_vars.items()}

            return {
                "success": True,
                "result": result_value,
                "variables": user_vars,
                "context_updated": _sanitize(safe_namespace.get('context', {}))
            }
            
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "cwd": cwd_path or original_cwd,
            }
        finally:
            try:
                os.chdir(original_cwd)
            except Exception:
                pass
