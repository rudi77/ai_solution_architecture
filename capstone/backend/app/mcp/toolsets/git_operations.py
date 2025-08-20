"""Git operations toolset for repository management."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class GitOperationsToolset:
    """MCP toolset for Git repository operations.
    
    Provides tools for:
    - Repository creation and initialization
    - Cloning repositories
    - Committing changes
    - Branch management
    - Remote operations
    """
    
    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = Path(work_dir) if work_dir else Path.cwd()
        
    def create_mcp_toolset(self) -> Optional[Any]:
        """Create MCP toolset if ADK is available."""
        if not MCP_AVAILABLE:
            return None
            
        # For now, return a basic filesystem MCP server
        # In a full implementation, this would be a custom Git MCP server
        return MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["@modelcontextprotocol/server-filesystem", "--root", str(self.work_dir)]
            )
        )
    
    def init_repository(
        self, 
        repo_name: str, 
        description: Optional[str] = None,
        private: bool = False
    ) -> Dict[str, Any]:
        """Initialize a new Git repository.
        
        Args:
            repo_name: Name of the repository
            description: Optional repository description
            private: Whether the repository should be private
            
        Returns:
            Dict with repository information and status
        """
        try:
            repo_path = self.work_dir / repo_name
            
            # Create directory if it doesn't exist
            repo_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize git repository
            result = subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Create initial README if description provided
            if description:
                readme_path = repo_path / "README.md"
                readme_content = f"# {repo_name}\n\n{description}\n"
                readme_path.write_text(readme_content)
                
                # Add and commit README
                subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
                subprocess.run(
                    ["git", "commit", "-m", "Initial commit with README"],
                    cwd=repo_path,
                    check=True
                )
            
            return {
                "success": True,
                "repository_name": repo_name,
                "repository_path": str(repo_path),
                "description": description,
                "private": private,
                "message": f"Repository '{repo_name}' initialized successfully"
            }
            
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Git command failed: {e.stderr}",
                "repository_name": repo_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to initialize repository: {str(e)}",
                "repository_name": repo_name
            }
    
    def clone_repository(
        self, 
        repo_url: str, 
        destination: Optional[str] = None
    ) -> Dict[str, Any]:
        """Clone an existing repository.
        
        Args:
            repo_url: URL of the repository to clone
            destination: Optional destination directory name
            
        Returns:
            Dict with clone operation status
        """
        try:
            clone_args = ["git", "clone", repo_url]
            if destination:
                clone_args.append(destination)
                target_path = self.work_dir / destination
            else:
                # Extract repo name from URL
                repo_name = repo_url.split("/")[-1].replace(".git", "")
                target_path = self.work_dir / repo_name
            
            result = subprocess.run(
                clone_args,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            return {
                "success": True,
                "repository_url": repo_url,
                "repository_path": str(target_path),
                "message": f"Repository cloned successfully to {target_path}"
            }
            
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Git clone failed: {e.stderr}",
                "repository_url": repo_url
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to clone repository: {str(e)}",
                "repository_url": repo_url
            }
    
    def commit_changes(
        self,
        repo_path: str,
        message: str,
        files: Optional[list] = None
    ) -> Dict[str, Any]:
        """Commit changes to repository.
        
        Args:
            repo_path: Path to the repository
            message: Commit message
            files: Optional list of specific files to commit (defaults to all changes)
            
        Returns:
            Dict with commit operation status
        """
        try:
            repo_dir = Path(repo_path)
            if not repo_dir.exists():
                return {
                    "success": False,
                    "error": f"Repository path does not exist: {repo_path}"
                }
            
            # Add files
            if files:
                for file in files:
                    subprocess.run(["git", "add", file], cwd=repo_dir, check=True)
            else:
                subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
            
            # Check if there are changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            if not status_result.stdout.strip():
                return {
                    "success": True,
                    "message": "No changes to commit",
                    "repository_path": repo_path
                }
            
            # Commit changes
            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            return {
                "success": True,
                "commit_hash": hash_result.stdout.strip(),
                "commit_message": message,
                "repository_path": repo_path,
                "message": f"Changes committed successfully with hash {hash_result.stdout.strip()[:8]}"
            }
            
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Git commit failed: {e.stderr}",
                "repository_path": repo_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to commit changes: {str(e)}",
                "repository_path": repo_path
            }
    
    def create_branch(
        self,
        repo_path: str,
        branch_name: str,
        checkout: bool = True
    ) -> Dict[str, Any]:
        """Create a new branch.
        
        Args:
            repo_path: Path to the repository
            branch_name: Name of the new branch
            checkout: Whether to checkout the new branch immediately
            
        Returns:
            Dict with branch creation status
        """
        try:
            repo_dir = Path(repo_path)
            if not repo_dir.exists():
                return {
                    "success": False,
                    "error": f"Repository path does not exist: {repo_path}"
                }
            
            # Create branch
            if checkout:
                subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    cwd=repo_dir,
                    check=True
                )
                action = "created and checked out"
            else:
                subprocess.run(
                    ["git", "branch", branch_name],
                    cwd=repo_dir,
                    check=True
                )
                action = "created"
            
            return {
                "success": True,
                "branch_name": branch_name,
                "repository_path": repo_path,
                "checked_out": checkout,
                "message": f"Branch '{branch_name}' {action} successfully"
            }
            
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Git branch creation failed: {e.stderr}",
                "branch_name": branch_name,
                "repository_path": repo_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create branch: {str(e)}",
                "branch_name": branch_name,
                "repository_path": repo_path
            }
    
    def get_repository_status(self, repo_path: str) -> Dict[str, Any]:
        """Get repository status information.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Dict with repository status information
        """
        try:
            repo_dir = Path(repo_path)
            if not repo_dir.exists():
                return {
                    "success": False,
                    "error": f"Repository path does not exist: {repo_path}"
                }
            
            # Get current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get status
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse status
            modified_files = []
            untracked_files = []
            
            for line in status_result.stdout.splitlines():
                if line.startswith(" M"):
                    modified_files.append(line[3:])
                elif line.startswith("??"):
                    untracked_files.append(line[3:])
            
            return {
                "success": True,
                "repository_path": repo_path,
                "current_branch": branch_result.stdout.strip(),
                "modified_files": modified_files,
                "untracked_files": untracked_files,
                "has_changes": len(modified_files) > 0 or len(untracked_files) > 0
            }
            
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Git status failed: {e.stderr}",
                "repository_path": repo_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get repository status: {str(e)}",
                "repository_path": repo_path
            }