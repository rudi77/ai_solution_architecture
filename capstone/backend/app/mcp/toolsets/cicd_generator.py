"""CI/CD generator toolset for pipeline configuration."""
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class CICDToolset:
    """MCP toolset for CI/CD pipeline generation.
    
    Provides tools for:
    - GitHub Actions workflow generation
    - GitLab CI configuration
    - Azure Pipelines setup
    - Docker build configurations
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
    
    def get_supported_providers(self) -> List[str]:
        """Get list of supported CI/CD providers."""
        return ["github-actions", "gitlab-ci", "azure-pipelines", "circleci"]
    
    def generate_github_actions_workflow(
        self,
        language: str,
        framework: Optional[str] = None,
        features: Optional[List[str]] = None,
        deployment_target: str = "docker"
    ) -> Dict[str, Any]:
        """Generate GitHub Actions workflow configuration.
        
        Args:
            language: Programming language (go, python, node, etc.)
            framework: Framework used (optional)
            features: List of features to include (testing, linting, security, etc.)
            deployment_target: Deployment target (docker, kubernetes, etc.)
            
        Returns:
            Dict with workflow configuration and files
        """
        if features is None:
            features = ["testing", "linting", "security"]
        
        try:
            workflow_name = f"ci-cd-{language}"
            
            # Base workflow structure
            workflow = {
                "name": f"CI/CD Pipeline - {language.title()}",
                "on": {
                    "push": {
                        "branches": ["main", "develop"]
                    },
                    "pull_request": {
                        "branches": ["main"]
                    }
                },
                "jobs": {}
            }
            
            # Add language-specific jobs
            if language.lower() == "go":
                workflow["jobs"].update(self._generate_go_github_jobs(features, deployment_target))
            elif language.lower() == "python":
                workflow["jobs"].update(self._generate_python_github_jobs(features, deployment_target))
            elif language.lower() in ["node", "typescript"]:
                workflow["jobs"].update(self._generate_node_github_jobs(features, deployment_target))
            
            # Convert to YAML
            workflow_yaml = yaml.dump(workflow, default_flow_style=False, sort_keys=False)
            
            # Additional files
            files = {
                f".github/workflows/{workflow_name}.yml": workflow_yaml
            }
            
            # Add Dockerfile if needed
            if deployment_target == "docker":
                files[".dockerignore"] = self._generate_dockerignore(language)
            
            return {
                "success": True,
                "provider": "github-actions",
                "language": language,
                "framework": framework,
                "features": features,
                "deployment_target": deployment_target,
                "files": files,
                "workflow_name": workflow_name,
                "message": f"GitHub Actions workflow generated for {language}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate GitHub Actions workflow: {str(e)}",
                "language": language
            }
    
    def generate_gitlab_ci_config(
        self,
        language: str,
        framework: Optional[str] = None,
        features: Optional[List[str]] = None,
        deployment_target: str = "docker"
    ) -> Dict[str, Any]:
        """Generate GitLab CI configuration.
        
        Args:
            language: Programming language
            framework: Framework used (optional)
            features: List of features to include
            deployment_target: Deployment target
            
        Returns:
            Dict with GitLab CI configuration
        """
        if features is None:
            features = ["testing", "linting"]
        
        try:
            # Base GitLab CI structure
            gitlab_ci = {
                "stages": ["test", "build", "deploy"],
                "variables": self._get_gitlab_variables(language),
                "before_script": self._get_gitlab_before_script(language)
            }
            
            # Add language-specific jobs
            if language.lower() == "go":
                gitlab_ci.update(self._generate_go_gitlab_jobs(features, deployment_target))
            elif language.lower() == "python":
                gitlab_ci.update(self._generate_python_gitlab_jobs(features, deployment_target))
            elif language.lower() in ["node", "typescript"]:
                gitlab_ci.update(self._generate_node_gitlab_jobs(features, deployment_target))
            
            # Convert to YAML
            config_yaml = yaml.dump(gitlab_ci, default_flow_style=False, sort_keys=False)
            
            files = {
                ".gitlab-ci.yml": config_yaml
            }
            
            return {
                "success": True,
                "provider": "gitlab-ci",
                "language": language,
                "framework": framework,
                "features": features,
                "deployment_target": deployment_target,
                "files": files,
                "message": f"GitLab CI configuration generated for {language}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate GitLab CI config: {str(e)}",
                "language": language
            }
    
    def generate_azure_pipelines_config(
        self,
        language: str,
        framework: Optional[str] = None,
        features: Optional[List[str]] = None,
        deployment_target: str = "docker"
    ) -> Dict[str, Any]:
        """Generate Azure Pipelines configuration.
        
        Args:
            language: Programming language
            framework: Framework used (optional)  
            features: List of features to include
            deployment_target: Deployment target
            
        Returns:
            Dict with Azure Pipelines configuration
        """
        if features is None:
            features = ["testing", "linting"]
        
        try:
            # Base Azure Pipelines structure
            pipeline = {
                "trigger": {
                    "branches": {
                        "include": ["main", "develop"]
                    }
                },
                "pr": {
                    "branches": {
                        "include": ["main"]
                    }
                },
                "pool": {
                    "vmImage": "ubuntu-latest"
                },
                "stages": []
            }
            
            # Add language-specific stages
            if language.lower() == "go":
                pipeline["stages"].extend(self._generate_go_azure_stages(features, deployment_target))
            elif language.lower() == "python":
                pipeline["stages"].extend(self._generate_python_azure_stages(features, deployment_target))
            elif language.lower() in ["node", "typescript"]:
                pipeline["stages"].extend(self._generate_node_azure_stages(features, deployment_target))
            
            # Convert to YAML
            config_yaml = yaml.dump(pipeline, default_flow_style=False, sort_keys=False)
            
            files = {
                "azure-pipelines.yml": config_yaml
            }
            
            return {
                "success": True,
                "provider": "azure-pipelines",
                "language": language,
                "framework": framework,
                "features": features,
                "deployment_target": deployment_target,
                "files": files,
                "message": f"Azure Pipelines configuration generated for {language}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate Azure Pipelines config: {str(e)}",
                "language": language
            }
    
    # GitHub Actions job generators
    def _generate_go_github_jobs(self, features: List[str], deployment_target: str) -> Dict[str, Any]:
        jobs = {
            "test": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Set up Go",
                        "uses": "actions/setup-go@v4",
                        "with": {"go-version": "1.21"}
                    },
                    {
                        "name": "Download dependencies",
                        "run": "go mod download"
                    },
                    {
                        "name": "Run tests",
                        "run": "go test -v ./..."
                    }
                ]
            }
        }
        
        if "linting" in features:
            jobs["lint"] = {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Set up Go",
                        "uses": "actions/setup-go@v4",
                        "with": {"go-version": "1.21"}
                    },
                    {
                        "name": "golangci-lint",
                        "uses": "golangci/golangci-lint-action@v3",
                        "with": {"version": "latest"}
                    }
                ]
            }
        
        if "security" in features:
            jobs["security"] = {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Run Gosec Security Scanner",
                        "uses": "securecodewarrior/github-action-gosec@master"
                    }
                ]
            }
        
        if deployment_target == "docker":
            jobs["build-and-push"] = {
                "needs": ["test"],
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Set up Docker Buildx",
                        "uses": "docker/setup-buildx-action@v3"
                    },
                    {
                        "name": "Build Docker image",
                        "run": "docker build -t ${{ github.repository }}:${{ github.sha }} ."
                    }
                ]
            }
        
        return jobs
    
    def _generate_python_github_jobs(self, features: List[str], deployment_target: str) -> Dict[str, Any]:
        jobs = {
            "test": {
                "runs-on": "ubuntu-latest",
                "strategy": {
                    "matrix": {
                        "python-version": ["3.10", "3.11", "3.12"]
                    }
                },
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Set up Python ${{ matrix.python-version }}",
                        "uses": "actions/setup-python@v4",
                        "with": {"python-version": "${{ matrix.python-version }}"}
                    },
                    {
                        "name": "Install dependencies",
                        "run": "pip install -r requirements.txt"
                    },
                    {
                        "name": "Run tests",
                        "run": "pytest"
                    }
                ]
            }
        }
        
        if "linting" in features:
            jobs["lint"] = {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Set up Python",
                        "uses": "actions/setup-python@v4",
                        "with": {"python-version": "3.11"}
                    },
                    {
                        "name": "Install linting tools",
                        "run": "pip install ruff black mypy"
                    },
                    {
                        "name": "Run ruff",
                        "run": "ruff check ."
                    },
                    {
                        "name": "Run black",
                        "run": "black --check ."
                    },
                    {
                        "name": "Run mypy",
                        "run": "mypy ."
                    }
                ]
            }
        
        if "security" in features:
            jobs["security"] = {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Run bandit security linter",
                        "uses": "jpetrucciani/bandit-check@main"
                    }
                ]
            }
        
        if deployment_target == "docker":
            jobs["build-and-push"] = {
                "needs": ["test"],
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Set up Docker Buildx",
                        "uses": "docker/setup-buildx-action@v3"
                    },
                    {
                        "name": "Build Docker image",
                        "run": "docker build -t ${{ github.repository }}:${{ github.sha }} ."
                    }
                ]
            }
        
        return jobs
    
    def _generate_node_github_jobs(self, features: List[str], deployment_target: str) -> Dict[str, Any]:
        jobs = {
            "test": {
                "runs-on": "ubuntu-latest",
                "strategy": {
                    "matrix": {
                        "node-version": ["18", "20", "21"]
                    }
                },
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Use Node.js ${{ matrix.node-version }}",
                        "uses": "actions/setup-node@v4",
                        "with": {"node-version": "${{ matrix.node-version }}"}
                    },
                    {
                        "name": "Install dependencies",
                        "run": "npm ci"
                    },
                    {
                        "name": "Run tests",
                        "run": "npm test"
                    }
                ]
            }
        }
        
        if "linting" in features:
            jobs["lint"] = {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Use Node.js",
                        "uses": "actions/setup-node@v4",
                        "with": {"node-version": "20"}
                    },
                    {
                        "name": "Install dependencies",
                        "run": "npm ci"
                    },
                    {
                        "name": "Run ESLint",
                        "run": "npm run lint"
                    }
                ]
            }
        
        if deployment_target == "docker":
            jobs["build-and-push"] = {
                "needs": ["test"],
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Set up Docker Buildx",
                        "uses": "docker/setup-buildx-action@v3"
                    },
                    {
                        "name": "Build Docker image",
                        "run": "docker build -t ${{ github.repository }}:${{ github.sha }} ."
                    }
                ]
            }
        
        return jobs
    
    # GitLab CI generators
    def _get_gitlab_variables(self, language: str) -> Dict[str, str]:
        base_vars = {
            "DOCKER_DRIVER": "overlay2",
            "DOCKER_TLS_CERTDIR": "/certs"
        }
        
        if language.lower() == "go":
            base_vars.update({
                "GO_VERSION": "1.21",
                "CGO_ENABLED": "0",
                "GOOS": "linux"
            })
        elif language.lower() == "python":
            base_vars.update({
                "PYTHON_VERSION": "3.11"
            })
        elif language.lower() in ["node", "typescript"]:
            base_vars.update({
                "NODE_VERSION": "20"
            })
        
        return base_vars
    
    def _get_gitlab_before_script(self, language: str) -> List[str]:
        if language.lower() == "go":
            return [
                "apt-get update -qq && apt-get install -y -qq git ca-certificates",
                "wget -O- -nv https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s v1.54.2"
            ]
        elif language.lower() == "python":
            return [
                "python -m pip install --upgrade pip"
            ]
        elif language.lower() in ["node", "typescript"]:
            return [
                "npm ci --cache .npm --prefer-offline"
            ]
        return []
    
    def _generate_go_gitlab_jobs(self, features: List[str], deployment_target: str) -> Dict[str, Any]:
        jobs = {
            "test": {
                "image": "golang:1.21",
                "stage": "test",
                "script": [
                    "go mod download",
                    "go test -v ./..."
                ]
            }
        }
        
        if "linting" in features:
            jobs["lint"] = {
                "image": "golang:1.21",
                "stage": "test",
                "script": [
                    "./bin/golangci-lint run"
                ]
            }
        
        if deployment_target == "docker":
            jobs["build"] = {
                "image": "docker:latest",
                "services": ["docker:dind"],
                "stage": "build",
                "script": [
                    "docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA ."
                ]
            }
        
        return jobs
    
    def _generate_python_gitlab_jobs(self, features: List[str], deployment_target: str) -> Dict[str, Any]:
        jobs = {
            "test": {
                "image": "python:3.11",
                "stage": "test",
                "script": [
                    "pip install -r requirements.txt",
                    "pytest"
                ]
            }
        }
        
        if "linting" in features:
            jobs["lint"] = {
                "image": "python:3.11",
                "stage": "test",
                "script": [
                    "pip install ruff black mypy",
                    "ruff check .",
                    "black --check .",
                    "mypy ."
                ]
            }
        
        if deployment_target == "docker":
            jobs["build"] = {
                "image": "docker:latest",
                "services": ["docker:dind"],
                "stage": "build",
                "script": [
                    "docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA ."
                ]
            }
        
        return jobs
    
    def _generate_node_gitlab_jobs(self, features: List[str], deployment_target: str) -> Dict[str, Any]:
        jobs = {
            "test": {
                "image": "node:20",
                "stage": "test",
                "cache": {
                    "paths": [".npm/"]
                },
                "script": [
                    "npm ci --cache .npm --prefer-offline",
                    "npm test"
                ]
            }
        }
        
        if "linting" in features:
            jobs["lint"] = {
                "image": "node:20",
                "stage": "test",
                "cache": {
                    "paths": [".npm/"]
                },
                "script": [
                    "npm ci --cache .npm --prefer-offline",
                    "npm run lint"
                ]
            }
        
        if deployment_target == "docker":
            jobs["build"] = {
                "image": "docker:latest",
                "services": ["docker:dind"],
                "stage": "build",
                "script": [
                    "docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA ."
                ]
            }
        
        return jobs
    
    # Azure Pipelines generators
    def _generate_go_azure_stages(self, features: List[str], deployment_target: str) -> List[Dict[str, Any]]:
        stages = [
            {
                "stage": "Test",
                "jobs": [
                    {
                        "job": "TestJob",
                        "steps": [
                            {
                                "task": "GoTool@0",
                                "inputs": {"version": "1.21"}
                            },
                            {
                                "script": "go mod download",
                                "displayName": "Download dependencies"
                            },
                            {
                                "script": "go test -v ./...",
                                "displayName": "Run tests"
                            }
                        ]
                    }
                ]
            }
        ]
        
        if "linting" in features:
            stages[0]["jobs"][0]["steps"].append({
                "script": "golangci-lint run",
                "displayName": "Run linter"
            })
        
        if deployment_target == "docker":
            stages.append({
                "stage": "Build",
                "dependsOn": "Test",
                "jobs": [
                    {
                        "job": "BuildJob",
                        "steps": [
                            {
                                "task": "Docker@2",
                                "inputs": {
                                    "command": "build",
                                    "Dockerfile": "Dockerfile",
                                    "tags": "$(Build.BuildId)"
                                }
                            }
                        ]
                    }
                ]
            })
        
        return stages
    
    def _generate_python_azure_stages(self, features: List[str], deployment_target: str) -> List[Dict[str, Any]]:
        stages = [
            {
                "stage": "Test",
                "jobs": [
                    {
                        "job": "TestJob",
                        "steps": [
                            {
                                "task": "UsePythonVersion@0",
                                "inputs": {"versionSpec": "3.11"}
                            },
                            {
                                "script": "pip install -r requirements.txt",
                                "displayName": "Install dependencies"
                            },
                            {
                                "script": "pytest",
                                "displayName": "Run tests"
                            }
                        ]
                    }
                ]
            }
        ]
        
        if "linting" in features:
            stages[0]["jobs"][0]["steps"].extend([
                {
                    "script": "pip install ruff black mypy",
                    "displayName": "Install linting tools"
                },
                {
                    "script": "ruff check .",
                    "displayName": "Run ruff"
                },
                {
                    "script": "black --check .",
                    "displayName": "Run black"
                }
            ])
        
        if deployment_target == "docker":
            stages.append({
                "stage": "Build",
                "dependsOn": "Test",
                "jobs": [
                    {
                        "job": "BuildJob",
                        "steps": [
                            {
                                "task": "Docker@2",
                                "inputs": {
                                    "command": "build",
                                    "Dockerfile": "Dockerfile",
                                    "tags": "$(Build.BuildId)"
                                }
                            }
                        ]
                    }
                ]
            })
        
        return stages
    
    def _generate_node_azure_stages(self, features: List[str], deployment_target: str) -> List[Dict[str, Any]]:
        stages = [
            {
                "stage": "Test",
                "jobs": [
                    {
                        "job": "TestJob",
                        "steps": [
                            {
                                "task": "NodeTool@0",
                                "inputs": {"versionSpec": "20.x"}
                            },
                            {
                                "script": "npm ci",
                                "displayName": "Install dependencies"
                            },
                            {
                                "script": "npm test",
                                "displayName": "Run tests"
                            }
                        ]
                    }
                ]
            }
        ]
        
        if "linting" in features:
            stages[0]["jobs"][0]["steps"].append({
                "script": "npm run lint",
                "displayName": "Run ESLint"
            })
        
        if deployment_target == "docker":
            stages.append({
                "stage": "Build",
                "dependsOn": "Test",
                "jobs": [
                    {
                        "job": "BuildJob",
                        "steps": [
                            {
                                "task": "Docker@2",
                                "inputs": {
                                    "command": "build",
                                    "Dockerfile": "Dockerfile",
                                    "tags": "$(Build.BuildId)"
                                }
                            }
                        ]
                    }
                ]
            })
        
        return stages
    
    def _generate_dockerignore(self, language: str) -> str:
        """Generate .dockerignore file for the specified language."""
        base_ignore = [
            ".git",
            ".gitignore",
            "README.md",
            "LICENSE",
            ".dockerignore",
            "Dockerfile",
            ".DS_Store",
            "Thumbs.db"
        ]
        
        if language.lower() == "go":
            base_ignore.extend([
                "*.exe",
                "*.exe~",
                "*.dll",
                "*.so",
                "*.dylib",
                "*.test",
                "*.out"
            ])
        elif language.lower() == "python":
            base_ignore.extend([
                "__pycache__",
                "*.py[cod]",
                "*$py.class",
                "*.so",
                ".Python",
                "env",
                "venv",
                ".venv",
                ".env",
                ".pytest_cache",
                "htmlcov"
            ])
        elif language.lower() in ["node", "typescript"]:
            base_ignore.extend([
                "node_modules",
                "npm-debug.log*",
                "yarn-debug.log*",
                "yarn-error.log*",
                ".env",
                ".env.local",
                ".env.development.local",
                ".env.test.local",
                ".env.production.local",
                "dist",
                "build"
            ])
        
        return "\n".join(base_ignore)