"""Tool execution guards and validation.

This module provides execution-time validation to ensure tools
operate within the expected working directory constraints.
"""

from __future__ import annotations
import asyncio
import functools
from pathlib import Path
from typing import Any, Dict, Callable, Union
import structlog
from .path_manager import get_working_directory, validate_path

logger = structlog.get_logger()

def validate_working_directory(func: Callable) -> Callable:
    """Decorator to validate working directory before tool execution.
    
    This decorator ensures that:
    1. The current working directory hasn't changed unexpectedly
    2. Any path parameters are within the working directory
    3. The tool operates in a predictable directory context
    """
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # Get expected working directory
        expected_wd = get_working_directory()
        current_wd = Path.cwd()
        
        # Warn if working directory has changed
        if current_wd.resolve() != expected_wd.resolve():
            logger.warning(
                "working_directory_drift_detected",
                expected=str(expected_wd),
                current=str(current_wd),
                tool=func.__name__
            )
        
        # Validate path parameters
        path_params = ['target_dir', 'repo_path', 'directory', 'path', 'file_path']
        for param_name in path_params:
            if param_name in kwargs:
                param_value = kwargs[param_name]
                if param_value:
                    try:
                        validated_path = validate_path(param_value)
                        kwargs[param_name] = str(validated_path)
                        logger.debug(
                            "path_parameter_validated",
                            tool=func.__name__,
                            param=param_name,
                            original=param_value,
                            validated=str(validated_path)
                        )
                    except ValueError as e:
                        logger.error(
                            "path_parameter_validation_failed",
                            tool=func.__name__,
                            param=param_name,
                            value=param_value,
                            error=str(e)
                        )
                        return {
                            "success": False,
                            "error": f"Invalid path parameter '{param_name}': {str(e)}"
                        }
        
        # Execute the tool
        result = await func(*args, **kwargs)
        
        # Log execution completion
        logger.debug(
            "tool_execution_completed",
            tool=func.__name__,
            success=result.get("success", False) if isinstance(result, dict) else True
        )
        
        return result
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        # Get expected working directory  
        expected_wd = get_working_directory()
        current_wd = Path.cwd()
        
        # Warn if working directory has changed
        if current_wd.resolve() != expected_wd.resolve():
            logger.warning(
                "working_directory_drift_detected", 
                expected=str(expected_wd),
                current=str(current_wd),
                tool=func.__name__
            )
        
        # Validate path parameters (same logic as async version)
        path_params = ['target_dir', 'repo_path', 'directory', 'path', 'file_path']
        for param_name in path_params:
            if param_name in kwargs:
                param_value = kwargs[param_name]
                if param_value:
                    try:
                        validated_path = validate_path(param_value)
                        kwargs[param_name] = str(validated_path)
                    except ValueError as e:
                        logger.error(
                            "path_parameter_validation_failed",
                            tool=func.__name__,
                            param=param_name, 
                            value=param_value,
                            error=str(e)
                        )
                        return {
                            "success": False,
                            "error": f"Invalid path parameter '{param_name}': {str(e)}"
                        }
        
        # Execute the tool
        result = func(*args, **kwargs)
        
        return result
    
    # Return appropriate wrapper based on whether function is async
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def ensure_repos_directory():
    """Ensure the repos directory exists and is properly initialized."""
    from .path_manager import get_repos_directory
    repos_dir = get_repos_directory()
    logger.info("repos_directory_ensured", path=str(repos_dir))
    return repos_dir