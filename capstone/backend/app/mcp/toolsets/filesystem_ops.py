"""Filesystem operations toolset for file and directory management."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class FilesystemToolset:
    """MCP toolset for filesystem operations.
    
    Provides tools for:
    - File and directory creation
    - File reading and writing
    - Template file operations
    - Directory structure management
    """
    
    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = Path(work_dir) if work_dir else Path.cwd()
        
    def create_mcp_toolset(self) -> Optional[Any]:
        """Create MCP toolset if ADK is available."""
        if not MCP_AVAILABLE:
            return None
            
        return MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["@modelcontextprotocol/server-filesystem", "--root", str(self.work_dir)]
            )
        )
    
    def create_file(
        self,
        file_path: str,
        content: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """Create a file with specified content.
        
        Args:
            file_path: Path to the file to create
            content: Content to write to the file
            overwrite: Whether to overwrite existing files
            
        Returns:
            Dict with file creation status
        """
        try:
            target_path = Path(file_path)
            if not target_path.is_absolute():
                target_path = self.work_dir / target_path
            
            # Check if file exists
            if target_path.exists() and not overwrite:
                return {
                    "success": False,
                    "error": f"File already exists: {target_path}",
                    "file_path": str(target_path)
                }
            
            # Create parent directories if needed
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content to file
            target_path.write_text(content, encoding='utf-8')
            
            return {
                "success": True,
                "file_path": str(target_path),
                "content_length": len(content),
                "message": f"File created successfully: {target_path.name}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create file: {str(e)}",
                "file_path": file_path
            }
    
    def read_file(self, file_path: str) -> Dict[str, Any]:
        """Read content from a file.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            Dict with file content and metadata
        """
        try:
            target_path = Path(file_path)
            if not target_path.is_absolute():
                target_path = self.work_dir / target_path
            
            if not target_path.exists():
                return {
                    "success": False,
                    "error": f"File does not exist: {target_path}",
                    "file_path": str(target_path)
                }
            
            content = target_path.read_text(encoding='utf-8')
            stats = target_path.stat()
            
            return {
                "success": True,
                "file_path": str(target_path),
                "content": content,
                "size": stats.st_size,
                "modified": stats.st_mtime,
                "message": f"File read successfully: {target_path.name}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read file: {str(e)}",
                "file_path": file_path
            }
    
    def create_directory(
        self,
        dir_path: str,
        parents: bool = True
    ) -> Dict[str, Any]:
        """Create a directory.
        
        Args:
            dir_path: Path to the directory to create
            parents: Whether to create parent directories
            
        Returns:
            Dict with directory creation status
        """
        try:
            target_path = Path(dir_path)
            if not target_path.is_absolute():
                target_path = self.work_dir / target_path
            
            if target_path.exists():
                return {
                    "success": True,
                    "directory_path": str(target_path),
                    "message": f"Directory already exists: {target_path.name}"
                }
            
            target_path.mkdir(parents=parents, exist_ok=True)
            
            return {
                "success": True,
                "directory_path": str(target_path),
                "message": f"Directory created successfully: {target_path.name}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create directory: {str(e)}",
                "directory_path": dir_path
            }
    
    def copy_file(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """Copy a file from source to destination.
        
        Args:
            source_path: Path to the source file
            destination_path: Path to the destination
            overwrite: Whether to overwrite existing files
            
        Returns:
            Dict with copy operation status
        """
        try:
            src_path = Path(source_path)
            if not src_path.is_absolute():
                src_path = self.work_dir / src_path
            
            dest_path = Path(destination_path)
            if not dest_path.is_absolute():
                dest_path = self.work_dir / dest_path
            
            if not src_path.exists():
                return {
                    "success": False,
                    "error": f"Source file does not exist: {src_path}",
                    "source_path": str(src_path)
                }
            
            if dest_path.exists() and not overwrite:
                return {
                    "success": False,
                    "error": f"Destination file already exists: {dest_path}",
                    "destination_path": str(dest_path)
                }
            
            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(src_path, dest_path)
            
            return {
                "success": True,
                "source_path": str(src_path),
                "destination_path": str(dest_path),
                "message": f"File copied successfully: {src_path.name} -> {dest_path.name}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to copy file: {str(e)}",
                "source_path": source_path,
                "destination_path": destination_path
            }
    
    def list_directory(
        self,
        dir_path: str,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """List contents of a directory.
        
        Args:
            dir_path: Path to the directory to list
            recursive: Whether to list recursively
            
        Returns:
            Dict with directory contents
        """
        try:
            target_path = Path(dir_path)
            if not target_path.is_absolute():
                target_path = self.work_dir / target_path
            
            if not target_path.exists():
                return {
                    "success": False,
                    "error": f"Directory does not exist: {target_path}",
                    "directory_path": str(target_path)
                }
            
            if not target_path.is_dir():
                return {
                    "success": False,
                    "error": f"Path is not a directory: {target_path}",
                    "directory_path": str(target_path)
                }
            
            files = []
            directories = []
            
            if recursive:
                for item in target_path.rglob("*"):
                    relative_path = item.relative_to(target_path)
                    if item.is_file():
                        files.append(str(relative_path))
                    elif item.is_dir():
                        directories.append(str(relative_path))
            else:
                for item in target_path.iterdir():
                    if item.is_file():
                        files.append(item.name)
                    elif item.is_dir():
                        directories.append(item.name)
            
            return {
                "success": True,
                "directory_path": str(target_path),
                "files": sorted(files),
                "directories": sorted(directories),
                "total_files": len(files),
                "total_directories": len(directories),
                "recursive": recursive
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list directory: {str(e)}",
                "directory_path": dir_path
            }
    
    def delete_file(self, file_path: str) -> Dict[str, Any]:
        """Delete a file.
        
        Args:
            file_path: Path to the file to delete
            
        Returns:
            Dict with deletion status
        """
        try:
            target_path = Path(file_path)
            if not target_path.is_absolute():
                target_path = self.work_dir / target_path
            
            if not target_path.exists():
                return {
                    "success": False,
                    "error": f"File does not exist: {target_path}",
                    "file_path": str(target_path)
                }
            
            if target_path.is_dir():
                return {
                    "success": False,
                    "error": f"Path is a directory, not a file: {target_path}",
                    "file_path": str(target_path)
                }
            
            target_path.unlink()
            
            return {
                "success": True,
                "file_path": str(target_path),
                "message": f"File deleted successfully: {target_path.name}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete file: {str(e)}",
                "file_path": file_path
            }
    
    def create_directory_structure(
        self,
        base_path: str,
        structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a nested directory structure.
        
        Args:
            base_path: Base path where to create the structure
            structure: Nested dict representing directory structure
                      {"dir1": {"subdir1": {}, "file1.txt": "content"}}
            
        Returns:
            Dict with creation status
        """
        try:
            base = Path(base_path)
            if not base.is_absolute():
                base = self.work_dir / base
            
            created_dirs = []
            created_files = []
            
            def create_recursive(current_path: Path, items: Dict[str, Any]):
                for name, content in items.items():
                    item_path = current_path / name
                    
                    if isinstance(content, dict):
                        # It's a directory
                        item_path.mkdir(parents=True, exist_ok=True)
                        created_dirs.append(str(item_path.relative_to(base)))
                        create_recursive(item_path, content)
                    else:
                        # It's a file
                        item_path.parent.mkdir(parents=True, exist_ok=True)
                        item_path.write_text(str(content), encoding='utf-8')
                        created_files.append(str(item_path.relative_to(base)))
            
            base.mkdir(parents=True, exist_ok=True)
            create_recursive(base, structure)
            
            return {
                "success": True,
                "base_path": str(base),
                "created_directories": created_dirs,
                "created_files": created_files,
                "total_items": len(created_dirs) + len(created_files),
                "message": f"Directory structure created successfully at {base.name}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create directory structure: {str(e)}",
                "base_path": base_path
            }