"""File operations implementation."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import structlog

logger = structlog.get_logger()


async def file_create(path: str, content: str, **kwargs) -> Dict[str, Any]:
    """Create a new file with specified content.
    
    Args:
        path: File path to create
        content: File content to write
        
    Returns:
        Dict with success status and file info
    """
    logger.info("file_create_start", path=path, content_length=len(content))
    
    try:
        file_path = Path(path)
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file already exists
        if file_path.exists():
            return {
                "success": False,
                "error": f"File already exists: {path}"
            }
        
        # Write content to file
        file_path.write_text(content, encoding="utf-8")
        
        logger.info("file_create_success", path=path, size=len(content))
        return {
            "success": True,
            "path": str(file_path),
            "size": len(content),
            "message": f"File created: {path}"
        }
        
    except Exception as e:
        error = f"Failed to create file {path}: {str(e)}"
        logger.error("file_create_failed", path=path, error=error)
        return {"success": False, "error": error}


async def file_read(path: str, **kwargs) -> Dict[str, Any]:
    """Read content from a file.
    
    Args:
        path: File path to read
        
    Returns:
        Dict with success status and file content
    """
    logger.info("file_read_start", path=path)
    
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File does not exist: {path}"
            }
        
        if not file_path.is_file():
            return {
                "success": False,
                "error": f"Path is not a file: {path}"
            }
        
        content = file_path.read_text(encoding="utf-8")
        
        logger.info("file_read_success", path=path, content_length=len(content))
        return {
            "success": True,
            "path": str(file_path),
            "content": content,
            "size": len(content)
        }
        
    except Exception as e:
        error = f"Failed to read file {path}: {str(e)}"
        logger.error("file_read_failed", path=path, error=error)
        return {"success": False, "error": error}


async def file_write(path: str, content: str, **kwargs) -> Dict[str, Any]:
    """Write content to a file (overwrites existing content).
    
    Args:
        path: File path to write
        content: Content to write
        
    Returns:
        Dict with success status and file info
    """
    logger.info("file_write_start", path=path, content_length=len(content))
    
    try:
        file_path = Path(path)
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content to file
        file_path.write_text(content, encoding="utf-8")
        
        logger.info("file_write_success", path=path, size=len(content))
        return {
            "success": True,
            "path": str(file_path),
            "size": len(content),
            "message": f"File written: {path}"
        }
        
    except Exception as e:
        error = f"Failed to write file {path}: {str(e)}"
        logger.error("file_write_failed", path=path, error=error)
        return {"success": False, "error": error}


async def file_edit(path: str, old_content: str, new_content: str, **kwargs) -> Dict[str, Any]:
    """Edit a file by replacing old_content with new_content.
    
    Args:
        path: File path to edit
        old_content: Content to replace
        new_content: Replacement content
        
    Returns:
        Dict with success status and edit info
    """
    logger.info("file_edit_start", path=path, old_length=len(old_content), new_length=len(new_content))
    
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File does not exist: {path}"
            }
        
        # Read current content
        current_content = file_path.read_text(encoding="utf-8")
        
        # Check if old_content exists in file
        if old_content not in current_content:
            return {
                "success": False,
                "error": f"Old content not found in file: {path}"
            }
        
        # Replace content
        updated_content = current_content.replace(old_content, new_content)
        
        # Write updated content
        file_path.write_text(updated_content, encoding="utf-8")
        
        logger.info("file_edit_success", path=path, old_size=len(current_content), new_size=len(updated_content))
        return {
            "success": True,
            "path": str(file_path),
            "old_size": len(current_content),
            "new_size": len(updated_content),
            "message": f"File edited: {path}"
        }
        
    except Exception as e:
        error = f"Failed to edit file {path}: {str(e)}"
        logger.error("file_edit_failed", path=path, error=error)
        return {"success": False, "error": error}


async def file_delete(path: str, **kwargs) -> Dict[str, Any]:
    """Delete a file.
    
    Args:
        path: File path to delete
        
    Returns:
        Dict with success status
    """
    logger.info("file_delete_start", path=path)
    
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File does not exist: {path}"
            }
        
        if not file_path.is_file():
            return {
                "success": False,
                "error": f"Path is not a file: {path}"
            }
        
        file_path.unlink()
        
        logger.info("file_delete_success", path=path)
        return {
            "success": True,
            "path": str(file_path),
            "message": f"File deleted: {path}"
        }
        
    except Exception as e:
        error = f"Failed to delete file {path}: {str(e)}"
        logger.error("file_delete_failed", path=path, error=error)
        return {"success": False, "error": error}


async def file_list_directory(path: str, **kwargs) -> Dict[str, Any]:
    """List directory contents with metadata.
    
    Args:
        path: Directory path to list
        
    Returns:
        Dict with success status and list of tuples (name, type, size)
        - name: file/directory name
        - type: "File" or "Directory"
        - size: file size in bytes or None for directories
    """
    logger.info("file_list_directory_start", path=path)
    
    try:
        dir_path = Path(path)
        
        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory does not exist: {path}"
            }
        
        if not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {path}"
            }
        
        entries: List[Tuple[str, str, Optional[int]]] = []
        
        for item in dir_path.iterdir():
            if item.is_file():
                try:
                    size = item.stat().st_size
                except OSError:
                    size = None
                entries.append((item.name, "File", size))
            elif item.is_dir():
                entries.append((item.name, "Directory", None))
        
        # Sort entries: directories first, then files, alphabetically
        entries.sort(key=lambda x: (x[1] == "File", x[0]))
        
        logger.info("file_list_directory_success", path=path, count=len(entries))
        return {
            "success": True,
            "path": str(dir_path),
            "entries": entries,
            "count": len(entries)
        }
        
    except Exception as e:
        error = f"Failed to list directory {path}: {str(e)}"
        logger.error("file_list_directory_failed", path=path, error=error)
        return {"success": False, "error": error}