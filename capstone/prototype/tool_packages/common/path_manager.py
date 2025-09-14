"""Working directory and path management utilities.

This module provides centralized path handling to ensure all tools work
within the same working directory structure and validate paths consistently.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Union
import structlog

logger = structlog.get_logger()

class WorkingDirectoryManager:
    """Manages working directory state and path validation across all tools."""
    
    _instance: Optional['WorkingDirectoryManager'] = None
    _base_dir: Optional[Path] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._base_dir is None:
            # Always use the project root directory (ai_solution_architecture)
            # regardless of where tools are called from
            current = Path.cwd()
            if current.name == "prototype":
                self._base_dir = current.parent.parent  # capstone/prototype -> ai_solution_architecture
            elif current.name == "capstone":
                self._base_dir = current.parent  # capstone -> ai_solution_architecture  
            elif (current / "capstone").exists():
                self._base_dir = current  # already in ai_solution_architecture
            else:
                # Fallback: search upwards for capstone directory
                search_path = current
                while search_path.parent != search_path:
                    if (search_path / "capstone").exists():
                        self._base_dir = search_path
                        break
                    search_path = search_path.parent
                else:
                    # Ultimate fallback
                    self._base_dir = current
            
            logger.info("working_directory_initialized", base_dir=str(self._base_dir))
    
    @property
    def base_directory(self) -> Path:
        """Get the base working directory."""
        return self._base_dir
    
    def get_repos_directory(self) -> Path:
        """Get the repos subdirectory, creating it if needed."""
        repos_dir = self._base_dir / "repos"
        repos_dir.mkdir(exist_ok=True)
        return repos_dir
    
    def validate_path_in_working_dir(self, path: Union[str, Path]) -> Path:
        """Validate that a path is within the working directory.
        
        Args:
            path: Path to validate (absolute or relative)
            
        Returns:
            Normalized absolute Path object within working directory
            
        Raises:
            ValueError: If path is outside working directory
        """
        path_obj = Path(path)
        
        # Convert to absolute path relative to base directory
        if not path_obj.is_absolute():
            abs_path = self._base_dir / path_obj
        else:
            abs_path = path_obj
        
        # Resolve any .. or . components
        abs_path = abs_path.resolve()
        
        # Validate it's within base directory
        try:
            abs_path.relative_to(self._base_dir.resolve())
        except ValueError:
            raise ValueError(f"Path '{path}' is outside working directory '{self._base_dir}'")
        
        return abs_path
    
    def get_relative_path(self, path: Union[str, Path]) -> Path:
        """Get path relative to working directory.
        
        Args:
            path: Path to convert
            
        Returns:
            Path relative to working directory
        """
        abs_path = self.validate_path_in_working_dir(path)
        return abs_path.relative_to(self._base_dir.resolve())
    
    def ensure_subdirectory(self, subdir: str) -> Path:
        """Ensure a subdirectory exists within working directory.
        
        Args:
            subdir: Subdirectory name/path
            
        Returns:
            Absolute path to subdirectory
        """
        subdir_path = self.validate_path_in_working_dir(subdir)
        subdir_path.mkdir(parents=True, exist_ok=True)
        return subdir_path


# Global singleton instance
_wd_manager = WorkingDirectoryManager()

def get_working_directory() -> Path:
    """Get the current working directory."""
    return _wd_manager.base_directory

def get_repos_directory() -> Path:
    """Get the repos subdirectory."""
    return _wd_manager.get_repos_directory()

def validate_path(path: Union[str, Path]) -> Path:
    """Validate that a path is within the working directory."""
    return _wd_manager.validate_path_in_working_dir(path)

def get_relative_path(path: Union[str, Path]) -> Path:
    """Get path relative to working directory."""
    return _wd_manager.get_relative_path(path)

def ensure_subdirectory(subdir: str) -> Path:
    """Ensure a subdirectory exists within working directory."""
    return _wd_manager.ensure_subdirectory(subdir)