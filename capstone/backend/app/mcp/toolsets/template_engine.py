"""Template engine toolset for language-specific scaffolding."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class TemplateEngineToolset:
    """MCP toolset for template-based code generation.
    
    Provides tools for:
    - Language-specific project scaffolding
    - Template file generation
    - Configuration file creation
    - Best practices application
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        self.templates_dir = Path(templates_dir) if templates_dir else Path(__file__).parent / "templates"
        
    def create_mcp_toolset(self) -> Optional[Any]:
        """Create MCP toolset if ADK is available."""
        if not MCP_AVAILABLE:
            return None
            
        # For templates, we'd need a custom MCP server
        # For now, return filesystem access to templates directory
        return MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["@modelcontextprotocol/server-filesystem", "--root", str(self.templates_dir)]
            )
        )
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported programming languages."""
        return ["go", "python", "node", "typescript", "java", "rust", "csharp"]
    
    def get_supported_frameworks(self, language: str) -> List[str]:
        """Get supported frameworks for a language."""
        frameworks = {
            "go": ["gin", "echo", "fiber", "chi", "standard"],
            "python": ["fastapi", "flask", "django", "starlette"],
            "node": ["express", "koa", "nestjs", "fastify"],
            "typescript": ["express", "nestjs", "koa", "fastify"],
            "java": ["spring", "micronaut", "quarkus", "vertx"],
            "rust": ["axum", "actix", "warp", "rocket"],
            "csharp": ["aspnet", "minimal", "webapi"]
        }
        return frameworks.get(language.lower(), [])
    
    def generate_go_service(
        self,
        service_name: str,
        framework: str = "gin",
        features: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate a Go service template.
        
        Args:
            service_name: Name of the service
            framework: Web framework to use (gin, echo, fiber, etc.)
            features: Optional list of features (database, metrics, logging, etc.)
            
        Returns:
            Dict with generated files and structure
        """
        if features is None:
            features = ["logging", "metrics", "health"]
        
        try:
            # Basic Go service structure
            structure = {
                "cmd": {
                    service_name: {
                        "main.go": self._generate_go_main(service_name, framework)
                    }
                },
                "internal": {
                    "handlers": {
                        "health.go": self._generate_go_health_handler(framework),
                        "api.go": self._generate_go_api_handler(framework)
                    },
                    "config": {
                        "config.go": self._generate_go_config()
                    },
                    "models": {
                        "response.go": self._generate_go_response_models()
                    }
                },
                "pkg": {},
                "go.mod": self._generate_go_mod(service_name),
                "go.sum": "",
                "Dockerfile": self._generate_go_dockerfile(service_name),
                ".gitignore": self._generate_go_gitignore(),
                "README.md": f"# {service_name}\n\nA Go service built with {framework}.\n"
            }
            
            # Add feature-specific files
            if "database" in features:
                structure["internal"]["database"] = {
                    "connection.go": self._generate_go_database_connection()
                }
            
            if "metrics" in features:
                structure["internal"]["metrics"] = {
                    "metrics.go": self._generate_go_metrics()
                }
            
            return {
                "success": True,
                "service_name": service_name,
                "language": "go",
                "framework": framework,
                "features": features,
                "structure": structure,
                "message": f"Go service '{service_name}' template generated with {framework}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate Go service: {str(e)}",
                "service_name": service_name
            }
    
    def generate_python_service(
        self,
        service_name: str,
        framework: str = "fastapi",
        features: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate a Python service template.
        
        Args:
            service_name: Name of the service
            framework: Web framework to use (fastapi, flask, django, etc.)
            features: Optional list of features
            
        Returns:
            Dict with generated files and structure
        """
        if features is None:
            features = ["logging", "metrics", "testing"]
        
        try:
            structure = {
                "app": {
                    "__init__.py": "",
                    "main.py": self._generate_python_main(service_name, framework),
                    "api": {
                        "__init__.py": "",
                        "health.py": self._generate_python_health_api(framework),
                        "routes.py": self._generate_python_routes(framework)
                    },
                    "config": {
                        "__init__.py": "",
                        "settings.py": self._generate_python_settings()
                    },
                    "models": {
                        "__init__.py": "",
                        "schemas.py": self._generate_python_schemas(framework)
                    }
                },
                "tests": {
                    "__init__.py": "",
                    "test_api.py": self._generate_python_tests(framework)
                },
                "requirements.txt": self._generate_python_requirements(framework, features),
                "pyproject.toml": self._generate_python_pyproject(service_name),
                "Dockerfile": self._generate_python_dockerfile(),
                ".gitignore": self._generate_python_gitignore(),
                "README.md": f"# {service_name}\n\nA Python service built with {framework}.\n"
            }
            
            return {
                "success": True,
                "service_name": service_name,
                "language": "python",
                "framework": framework,
                "features": features,
                "structure": structure,
                "message": f"Python service '{service_name}' template generated with {framework}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate Python service: {str(e)}",
                "service_name": service_name
            }
    
    def generate_node_service(
        self,
        service_name: str,
        framework: str = "express",
        language: str = "typescript",
        features: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate a Node.js service template.
        
        Args:
            service_name: Name of the service
            framework: Web framework to use (express, koa, nestjs, etc.)
            language: Language variant (javascript, typescript)
            features: Optional list of features
            
        Returns:
            Dict with generated files and structure
        """
        if features is None:
            features = ["logging", "testing", "eslint"]
        
        try:
            is_typescript = language.lower() == "typescript"
            ext = "ts" if is_typescript else "js"
            
            structure = {
                "src": {
                    f"index.{ext}": self._generate_node_main(service_name, framework, is_typescript),
                    "routes": {
                        f"health.{ext}": self._generate_node_health_routes(framework, is_typescript),
                        f"api.{ext}": self._generate_node_api_routes(framework, is_typescript)
                    },
                    "config": {
                        f"config.{ext}": self._generate_node_config(is_typescript)
                    },
                    "middleware": {
                        f"logging.{ext}": self._generate_node_logging_middleware(is_typescript)
                    }
                },
                "tests": {
                    f"api.test.{ext}": self._generate_node_tests(framework, is_typescript)
                },
                "package.json": self._generate_node_package_json(service_name, framework, is_typescript, features),
                "Dockerfile": self._generate_node_dockerfile(is_typescript),
                ".gitignore": self._generate_node_gitignore(),
                "README.md": f"# {service_name}\n\nA Node.js service built with {framework}.\n"
            }
            
            if is_typescript:
                structure["tsconfig.json"] = self._generate_typescript_config()
                structure[".eslintrc.js"] = self._generate_eslint_config_ts()
            else:
                structure[".eslintrc.js"] = self._generate_eslint_config_js()
            
            return {
                "success": True,
                "service_name": service_name,
                "language": language,
                "framework": framework,
                "features": features,
                "structure": structure,
                "message": f"Node.js service '{service_name}' template generated with {framework} ({language})"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate Node.js service: {str(e)}",
                "service_name": service_name
            }
    
    # Template generation methods (simplified versions)
    def _generate_go_main(self, service_name: str, framework: str) -> str:
        return f'''package main

import (
    "log"
    "net/http"
    
    "github.com/gin-gonic/gin"
    "{service_name}/internal/handlers"
    "{service_name}/internal/config"
)

func main() {{
    cfg := config.Load()
    
    r := gin.Default()
    
    // Health endpoint
    r.GET("/health", handlers.HealthHandler)
    
    // API routes
    api := r.Group("/api/v1")
    handlers.SetupAPIRoutes(api)
    
    log.Printf("Server starting on :%s", cfg.Port)
    log.Fatal(http.ListenAndServe(":"+cfg.Port, r))
}}'''

    def _generate_go_health_handler(self, framework: str) -> str:
        return '''package handlers

import (
    "net/http"
    
    "github.com/gin-gonic/gin"
)

func HealthHandler(c *gin.Context) {
    c.JSON(http.StatusOK, gin.H{
        "status": "healthy",
        "service": "idp-service",
    })
}'''

    def _generate_go_api_handler(self, framework: str) -> str:
        return '''package handlers

import (
    "net/http"
    
    "github.com/gin-gonic/gin"
)

func SetupAPIRoutes(router *gin.RouterGroup) {
    router.GET("/status", StatusHandler)
}

func StatusHandler(c *gin.Context) {
    c.JSON(http.StatusOK, gin.H{
        "message": "API is running",
    })
}'''

    def _generate_go_config(self) -> str:
        return '''package config

import (
    "os"
)

type Config struct {
    Port string
    Environment string
}

func Load() *Config {
    return &Config{
        Port: getEnv("PORT", "8080"),
        Environment: getEnv("ENVIRONMENT", "development"),
    }
}

func getEnv(key, defaultValue string) string {
    if value := os.Getenv(key); value != "" {
        return value
    }
    return defaultValue
}'''

    def _generate_go_response_models(self) -> str:
        return '''package models

type APIResponse struct {
    Success bool        `json:"success"`
    Message string      `json:"message"`
    Data    interface{} `json:"data,omitempty"`
    Error   string      `json:"error,omitempty"`
}'''

    def _generate_go_mod(self, service_name: str) -> str:
        return f'''module {service_name}

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
)'''

    def _generate_go_dockerfile(self, service_name: str) -> str:
        return f'''FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go build -o main cmd/{service_name}/main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/

COPY --from=builder /app/main .

CMD ["./main"]'''

    def _generate_go_gitignore(self) -> str:
        return '''# Binaries
*.exe
*.exe~
*.dll
*.so
*.dylib

# Test binary
*.test

# Coverage
*.out

# Go workspace file
go.work'''

    # Python template methods
    def _generate_python_main(self, service_name: str, framework: str) -> str:
        if framework == "fastapi":
            return '''from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.routes import router as api_router

app = FastAPI(title="IDP Service", version="1.0.0")

app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)'''
        return ""

    def _generate_python_health_api(self, framework: str) -> str:
        if framework == "fastapi":
            return '''from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "healthy", "service": "idp-service"}'''
        return ""

    def _generate_python_routes(self, framework: str) -> str:
        if framework == "fastapi":
            return '''from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
async def status():
    return {"message": "API is running"}'''
        return ""

    def _generate_python_settings(self) -> str:
        return '''import os
from typing import Optional

class Settings:
    port: int = int(os.getenv("PORT", "8000"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

settings = Settings()'''

    def _generate_python_schemas(self, framework: str) -> str:
        if framework == "fastapi":
            return '''from pydantic import BaseModel
from typing import Any, Optional

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None'''
        return ""

    def _generate_python_tests(self, framework: str) -> str:
        if framework == "fastapi":
            return '''import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_api_status():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert "message" in response.json()'''
        return ""

    def _generate_python_requirements(self, framework: str, features: List[str]) -> str:
        base_deps = []
        if framework == "fastapi":
            base_deps = ["fastapi>=0.104.0", "uvicorn[standard]>=0.24.0"]
        
        if "testing" in features:
            base_deps.append("pytest>=7.0.0")
            base_deps.append("httpx>=0.25.0")
        
        return "\n".join(base_deps)

    def _generate_python_pyproject(self, service_name: str) -> str:
        return f'''[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "{service_name}"
version = "0.1.0"
description = "IDP Generated Service"
dependencies = []

[tool.pytest.ini_options]
testpaths = ["tests"]'''

    def _generate_python_dockerfile(self) -> str:
        return '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]'''

    def _generate_python_gitignore(self) -> str:
        return '''__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
.env
.pytest_cache/
.coverage
htmlcov/'''

    # Node.js template methods
    def _generate_node_main(self, service_name: str, framework: str, is_typescript: bool) -> str:
        if framework == "express":
            imports = "import express from 'express';" if is_typescript else "const express = require('express');"
            return f'''{imports}
import healthRoutes from './routes/health';
import apiRoutes from './routes/api';

const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());
app.use('/health', healthRoutes);
app.use('/api/v1', apiRoutes);

app.listen(port, () => {{
    console.log(`Server running on port ${{port}}`);
}});'''
        return ""

    def _generate_node_health_routes(self, framework: str, is_typescript: bool) -> str:
        if framework == "express":
            imports = "import { Router } from 'express';" if is_typescript else "const { Router } = require('express');"
            export_stmt = "export default router;" if is_typescript else "module.exports = router;"
            return f'''{imports}

const router = Router();

router.get('/', (req, res) => {{
    res.json({{ status: 'healthy', service: 'idp-service' }});
}});

{export_stmt}'''
        return ""

    def _generate_node_api_routes(self, framework: str, is_typescript: bool) -> str:
        if framework == "express":
            imports = "import { Router } from 'express';" if is_typescript else "const { Router } = require('express');"
            export_stmt = "export default router;" if is_typescript else "module.exports = router;"
            return f'''{imports}

const router = Router();

router.get('/status', (req, res) => {{
    res.json({{ message: 'API is running' }});
}});

{export_stmt}'''
        return ""

    def _generate_node_config(self, is_typescript: bool) -> str:
        config_type = ": { port: number; environment: string }" if is_typescript else ""
        export_stmt = "export default config;" if is_typescript else "module.exports = config;"
        return f'''const config{config_type} = {{
    port: parseInt(process.env.PORT || '3000'),
    environment: process.env.NODE_ENV || 'development'
}};

{export_stmt}'''

    def _generate_node_logging_middleware(self, is_typescript: bool) -> str:
        return "// Logging middleware placeholder"

    def _generate_node_tests(self, framework: str, is_typescript: bool) -> str:
        return "// Test placeholder"

    def _generate_node_package_json(self, service_name: str, framework: str, is_typescript: bool, features: List[str]) -> str:
        dependencies = {}
        dev_dependencies = {}
        
        if framework == "express":
            dependencies["express"] = "^4.18.0"
            dev_dependencies["@types/express"] = "^4.17.0" if is_typescript else None
        
        if is_typescript:
            dev_dependencies["typescript"] = "^5.0.0"
            dev_dependencies["@types/node"] = "^20.0.0"
            dev_dependencies["ts-node"] = "^10.0.0"
        
        if "testing" in features:
            dev_dependencies["jest"] = "^29.0.0"
        
        # Filter out None values
        dev_dependencies = {k: v for k, v in dev_dependencies.items() if v is not None}
        
        scripts = {
            "start": "ts-node src/index.ts" if is_typescript else "node src/index.js",
            "dev": "ts-node --watch src/index.ts" if is_typescript else "nodemon src/index.js",
            "build": "tsc" if is_typescript else None,
            "test": "jest" if "testing" in features else None
        }
        
        # Filter out None values
        scripts = {k: v for k, v in scripts.items() if v is not None}
        
        import json
        return json.dumps({
            "name": service_name,
            "version": "1.0.0",
            "description": "IDP Generated Service",
            "main": "src/index.js",
            "scripts": scripts,
            "dependencies": dependencies,
            "devDependencies": dev_dependencies
        }, indent=2)

    def _generate_node_dockerfile(self, is_typescript: bool) -> str:
        if is_typescript:
            return '''FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

CMD ["npm", "start"]'''
        else:
            return '''FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

CMD ["npm", "start"]'''

    def _generate_node_gitignore(self) -> str:
        return '''node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.env
.env.local
.env.development.local
.env.test.local
.env.production.local
dist/
build/'''

    def _generate_typescript_config(self) -> str:
        import json
        return json.dumps({
            "compilerOptions": {
                "target": "ES2020",
                "module": "commonjs",
                "outDir": "./dist",
                "rootDir": "./src",
                "strict": True,
                "esModuleInterop": True,
                "skipLibCheck": True,
                "forceConsistentCasingInFileNames": True
            },
            "include": ["src/**/*"],
            "exclude": ["node_modules", "dist"]
        }, indent=2)

    def _generate_eslint_config_ts(self) -> str:
        return '''module.exports = {
    parser: '@typescript-eslint/parser',
    extends: [
        'eslint:recommended',
        '@typescript-eslint/recommended'
    ],
    env: {
        node: true,
        es2020: true
    }
};'''

    def _generate_eslint_config_js(self) -> str:
        return '''module.exports = {
    extends: ['eslint:recommended'],
    env: {
        node: true,
        es2020: true
    }
};'''

    def _generate_database_connection(self) -> str:
        return "// Database connection placeholder"

    def _generate_go_database_connection(self) -> str:
        return '''package database

import (
    "database/sql"
    "log"
    
    _ "github.com/lib/pq"
)

func Connect(connectionString string) (*sql.DB, error) {
    db, err := sql.Open("postgres", connectionString)
    if err != nil {
        return nil, err
    }
    
    if err := db.Ping(); err != nil {
        return nil, err
    }
    
    log.Println("Database connected successfully")
    return db, nil
}'''

    def _generate_go_metrics(self) -> str:
        return '''package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    RequestsTotal = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "http_requests_total",
            Help: "Total number of HTTP requests",
        },
        []string{"method", "endpoint", "status"},
    )
    
    RequestDuration = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name: "http_request_duration_seconds",
            Help: "Duration of HTTP requests",
        },
        []string{"method", "endpoint"},
    )
)'''