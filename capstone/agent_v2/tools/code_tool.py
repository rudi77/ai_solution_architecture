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
        import contextlib
        
        # 1. CWD mit Context Manager
        @contextlib.contextmanager
        def safe_chdir(path):
            original = os.getcwd()
            try:
                if path:
                    os.chdir(path)
                yield
            finally:
                try:
                    os.chdir(original)
                except (OSError, FileNotFoundError):
                    pass
        
        # Validate and prepare cwd
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
        
        # 2. Separate Import-Behandlung
        import_code = """
import os, sys, json, re, pathlib, shutil
import subprocess, datetime, time, random
import base64, hashlib, tempfile, csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
"""
        
        # Try to import pandas and matplotlib (optional)
        optional_imports = """
try:
    import pandas as pd
except ImportError:
    pd = None
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None
"""
        
        # Normalize context parameter to dict
        context_dict = {}
        if context:
            if isinstance(context, dict):
                context_dict = context
            elif isinstance(context, str):
                # Try to parse as JSON if it's a string
                try:
                    import json
                    context_dict = json.loads(context)
                except (json.JSONDecodeError, TypeError):
                    # If parsing fails, ignore or wrap in a dict
                    pass
            else:
                # For other types, ignore
                pass
        
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
            "context": context_dict,
        }
        
        # Expose context keys as top-level variables when safe
        if context_dict:
            for key, value in context_dict.items():
                if isinstance(key, str) and key.isidentifier() and key not in safe_namespace:
                    safe_namespace[key] = value
        
        try:
            # Imports zuerst (mit spezifischem Error)
            exec(import_code, safe_namespace)
            exec(optional_imports, safe_namespace)
        except ImportError as e:
            return {
                "success": False,
                "error": f"Missing library: {e.name}",
                "hint": f"Install with: pip install {e.name}",
                "type": "ImportError"
            }
        
        try:
            with safe_chdir(cwd_path):
                exec(code, safe_namespace)
            
            # 3. Result-Check
            if 'result' not in safe_namespace:
                return {
                    "success": False,
                    "error": "Code must assign output to 'result' variable",
                    "hint": "Add: result = your_output",
                    "variables": list(safe_namespace.keys())
                }
            
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
                "context_updated": _sanitize(context_dict)
            }
            
        except Exception as e:
            import traceback
            
            # Provide helpful hints for common errors
            hints = []
            error_type = type(e).__name__
            error_msg = str(e)
            
            if error_type == "NameError" and "not defined" in error_msg:
                var_name = error_msg.split("'")[1] if "'" in error_msg else "unknown"
                hints.append(f"Variable '{var_name}' is not defined.")
                hints.append(f"REMEMBER: Each Python call has an ISOLATED namespace!")
                hints.append(f"  1. If '{var_name}' is from a previous step, you must:")
                hints.append(f"     → Re-read the source data (CSV, JSON, etc.), OR")
                hints.append(f"     → Request it via 'context' parameter")
                hints.append(f"  2. If '{var_name}' should be created here, define it in your code")
                hints.append(f"  3. Check the file path and make sure the data source exists")
                
            elif error_type == "KeyError":
                hints.append("KeyError: Check if the key exists in the dictionary")
                hints.append("Use .get() method or check with 'if key in dict'")
                
            elif error_type == "FileNotFoundError":
                hints.append("File not found. Check:")
                hints.append("  1. The file path is correct")
                hints.append("  2. The file exists in the current directory")
                hints.append("  3. Use absolute path or set 'cwd' parameter")
                
            elif error_type == "ImportError":
                hints.append("Import failed. The library may not be installed.")
                hints.append("Try using pd, plt, or other pre-imported libraries")
                
            elif error_type == "AttributeError":
                hints.append("AttributeError: Check if you're calling the right method/attribute")
                hints.append("Make sure the object is of the expected type")
                hints.append("Use type() or isinstance() to verify object types")
            
            return {
                "success": False,
                "error": error_msg,
                "type": error_type,
                "traceback": traceback.format_exc(),
                "hints": hints,
                "code_snippet": code[:200] + "..." if len(code) > 200 else code
            }
