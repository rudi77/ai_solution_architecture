# ============================================
# SHELL TOOL
# ============================================

from ast import Dict
import asyncio
import shutil
from typing import Any
from capstone.agent_v2.tool import Tool


class ShellTool(Tool):
    """Execute shell commands with safety limits"""
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return "Execute shell commands with timeout and safety limits"
    
    async def execute(self, command: str, timeout: int = 30, cwd: str = None, **kwargs) -> Dict[str, Any]:
        try:
            # Safety check - block dangerous commands
            dangerous_patterns = [
                "rm -rf /", "rm -rf /*", 
                "dd if=/dev/zero", "dd if=/dev/random",
                "format c:", "del /f /s /q",
                ":(){ :|:& };:",  # Fork bomb
                "> /dev/sda",
                "mkfs.",
            ]
            
            if any(pattern in command.lower() for pattern in dangerous_patterns):
                return {"success": False, "error": "Command blocked for safety reasons"}
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                return {
                    "success": process.returncode == 0,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "returncode": process.returncode,
                    "command": command
                }
            except asyncio.TimeoutError:
                process.kill()
                return {"success": False, "error": f"Command timed out after {timeout}s"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# Power Shell Tool
# ============================================

class PowerShellTool(Tool):
    """Execute PowerShell commands with safety limits"""
    
    @property
    def name(self) -> str:
        return "powershell"
    
    @property
    def description(self) -> str:
        return "Execute PowerShell commands with timeout and safety limits"

    async def execute(self, command: str, timeout: int = 30, cwd: str = None, **kwargs) -> Dict[str, Any]:

        # Safety check - block dangerous powershell commands (case-insensitive)
        dangerous_patterns = [
            "Remove-Item -Path * -Force",
            "Remove-Item -Path * -Recurse",
            "Remove-Item -Path * -Recurse -Force",
            "Remove-Item -Path * -Recurse -Force",
        ]
        lower_cmd = command.lower()
        lower_patterns = [p.lower() for p in dangerous_patterns]
        if any(pattern in lower_cmd for pattern in lower_patterns):
            return {"success": False, "error": "Command blocked for safety reasons"}

        # Resolve PowerShell executable
        shell_exe = shutil.which("pwsh") or shutil.which("powershell")
        if not shell_exe:
            return {"success": False, "error": "No PowerShell executable found (pwsh/powershell)"}

        try:
            # Execute command explicitly via PowerShell
            process = await asyncio.create_subprocess_exec(
                shell_exe,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
            
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
            
        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode() if stdout else "",
            "stderr": stderr.decode() if stderr else "",
            "returncode": process.returncode,
            "command": command
        }

