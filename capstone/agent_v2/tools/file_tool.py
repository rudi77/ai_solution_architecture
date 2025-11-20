# ============================================
# FILE SYSTEM TOOLS
# ============================================
from pathlib import Path
from typing import Any, Dict
from capstone.agent_v2.tool import Tool, ApprovalRiskLevel


class FileReadTool(Tool):
    """Safe file reading with size limits"""
    
    @property
    def name(self) -> str:
        return "file_read"
    
    @property
    def description(self) -> str:
        return "Read file contents safely with size limits and encoding detection"
    
    async def execute(self, path: str, encoding: str = "utf-8", max_size_mb: int = 10, **kwargs) -> Dict[str, Any]:
        """
        Read file contents safely with size limits and encoding detection

        Args:
            path: The path to the file to read
            encoding: The encoding of the file
            max_size_mb: The maximum size of the file in MB

        Returns:
            A dictionary with the following keys:
            - success: True if the file was read successfully, False otherwise
            - content: The contents of the file
            - size: The size of the file in bytes
            - path: The path to the file
        """
        try:
            file_path = Path(path)
            
            if not file_path.exists():
                return {"success": False, "error": f"File not found: {path}"}
            
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > max_size_mb:
                return {"success": False, "error": f"File too large: {file_size_mb:.2f}MB > {max_size_mb}MB"}
            
            content = file_path.read_text(encoding=encoding)
            return {
                "success": True,
                "content": content,
                "size": len(content),
                "path": str(file_path.absolute())
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

class FileWriteTool(Tool):
    """Safe file writing with backup option"""
    
    @property
    def name(self) -> str:
        return "file_write"
    
    @property
    def description(self) -> str:
        return "Write content to file with backup and safety checks"
    
    @property
    def requires_approval(self) -> bool:
        return True

    @property
    def approval_risk_level(self) -> ApprovalRiskLevel:
        return ApprovalRiskLevel.MEDIUM

    async def execute(self, path: str, content: str, backup: bool = True, **kwargs) -> Dict[str, Any]:
        """
        Write content to file with backup and safety checks

        Args:
            path: The path to the file to write
            content: The content to write to the file
            backup: Whether to backup the existing file

        Returns:
            A dictionary with the following keys:
            - success: True if the file was written successfully, False otherwise
            - path: The path to the file
            - size: The size of the file in bytes
            - backed_up: Whether the existing file was backed up
            - error: The error message if the file was not written successfully
        """
        try:
            file_path = Path(path)
            
            # Backup existing file
            if backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                backup_path.write_text(file_path.read_text(), encoding='utf-8')
            
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            file_path.write_text(content, encoding='utf-8')
            
            return {
                "success": True,
                "path": str(file_path.absolute()),
                "size": len(content),
                "backed_up": backup and file_path.exists()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
