# Python FastAPI Hexagonal Architecture Template

## Description
FastAPI web service with Hexagonal Architecture pattern (Ports & Adapters)

## Architecture Pattern
- **Hexagonal Architecture (Ports & Adapters)**
- **Domain-Driven Design principles**
- **Clean separation of concerns**
- **Dependency Inversion**

## Project Structure
```
src/
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   └── user.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── user_repository.py
│   └── services/
│       ├── __init__.py
│       └── user_service.py
├── infrastructure/
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   └── user_db.py
│   └── web/
│       ├── __init__.py
│       └── api/
│           ├── __init__.py
│           └── user_router.py
├── application/
│   ├── __init__.py
│   ├── use_cases/
│   │   ├── __init__.py
│   │   └── create_user.py
│   └── ports/
│       ├── __init__.py
│       └── user_port.py
└── main.py
tests/
├── __init__.py
├── unit/
│   ├── __init__.py
│   └── test_user_service.py
└── integration/
    ├── __init__.py
    └── test_user_api.py
requirements.txt
Dockerfile
docker-compose.yml
.env.example
.gitignore
README.md
```

## Code Examples

### src/main.py
```python
"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.infrastructure.web.api.user_router import router as user_router

app = FastAPI(
    title="Hexagonal FastAPI Service",
    description="FastAPI service with Hexagonal Architecture",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(user_router, prefix="/api/v1/users", tags=["users"])

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### src/domain/entities/user.py
```python
"""User domain entity."""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class User:
    """User entity representing core business object."""
    
    id: Optional[int] = None
    email: str = ""
    name: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Post-initialization validation."""
        if not self.email:
            raise ValueError("Email is required")
        if not self.name:
            raise ValueError("Name is required")
        
    def update_name(self, new_name: str) -> None:
        """Update user name with validation."""
        if not new_name.strip():
            raise ValueError("Name cannot be empty")
        self.name = new_name.strip()
        self.updated_at = datetime.utcnow()
```

### src/domain/repositories/user_repository.py
```python
"""User repository interface."""

from abc import ABC, abstractmethod
from typing import Optional, List
from src.domain.entities.user import User


class UserRepository(ABC):
    """Abstract user repository defining persistence interface."""
    
    @abstractmethod
    async def create(self, user: User) -> User:
        """Create a new user."""
        pass
    
    @abstractmethod
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        pass
    
    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        pass
    
    @abstractmethod
    async def update(self, user: User) -> User:
        """Update existing user."""
        pass
    
    @abstractmethod
    async def delete(self, user_id: int) -> bool:
        """Delete user by ID."""
        pass
    
    @abstractmethod
    async def list_all(self) -> List[User]:
        """List all users."""
        pass
```

### src/domain/services/user_service.py
```python
"""User domain service."""

from typing import List, Optional
from src.domain.entities.user import User
from src.domain.repositories.user_repository import UserRepository


class UserService:
    """User domain service with business logic."""
    
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository
    
    async def create_user(self, email: str, name: str) -> User:
        """Create a new user with business validation."""
        # Business rule: email must be unique
        existing_user = await self._user_repository.get_by_email(email)
        if existing_user:
            raise ValueError(f"User with email {email} already exists")
        
        user = User(email=email, name=name)
        return await self._user_repository.create(user)
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return await self._user_repository.get_by_id(user_id)
    
    async def update_user(self, user_id: int, name: Optional[str] = None) -> Optional[User]:
        """Update user with business validation."""
        user = await self._user_repository.get_by_id(user_id)
        if not user:
            return None
        
        if name:
            user.update_name(name)
        
        return await self._user_repository.update(user)
    
    async def delete_user(self, user_id: int) -> bool:
        """Delete user."""
        return await self._user_repository.delete(user_id)
    
    async def list_users(self) -> List[User]:
        """List all users."""
        return await self._user_repository.list_all()
```

### src/application/use_cases/create_user.py
```python
"""Create user use case."""

from dataclasses import dataclass
from src.domain.entities.user import User
from src.domain.services.user_service import UserService


@dataclass
class CreateUserRequest:
    """Create user request."""
    email: str
    name: str


@dataclass
class CreateUserResponse:
    """Create user response."""
    user: User
    success: bool
    message: str


class CreateUserUseCase:
    """Create user use case."""
    
    def __init__(self, user_service: UserService):
        self._user_service = user_service
    
    async def execute(self, request: CreateUserRequest) -> CreateUserResponse:
        """Execute create user use case."""
        try:
            user = await self._user_service.create_user(
                email=request.email,
                name=request.name
            )
            return CreateUserResponse(
                user=user,
                success=True,
                message="User created successfully"
            )
        except ValueError as e:
            return CreateUserResponse(
                user=None,
                success=False,
                message=str(e)
            )
```

### src/infrastructure/database/user_db.py
```python
"""User database implementation."""

from typing import Optional, List
from datetime import datetime
from src.domain.entities.user import User
from src.domain.repositories.user_repository import UserRepository


class InMemoryUserRepository(UserRepository):
    """In-memory user repository implementation."""
    
    def __init__(self):
        self._users: dict[int, User] = {}
        self._next_id = 1
    
    async def create(self, user: User) -> User:
        """Create a new user."""
        user.id = self._next_id
        user.created_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        self._users[user.id] = user
        self._next_id += 1
        return user
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        for user in self._users.values():
            if user.email == email:
                return user
        return None
    
    async def update(self, user: User) -> User:
        """Update existing user."""
        if user.id not in self._users:
            raise ValueError(f"User with ID {user.id} not found")
        
        user.updated_at = datetime.utcnow()
        self._users[user.id] = user
        return user
    
    async def delete(self, user_id: int) -> bool:
        """Delete user by ID."""
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False
    
    async def list_all(self) -> List[User]:
        """List all users."""
        return list(self._users.values())
```

### src/infrastructure/web/api/user_router.py
```python
"""User API router."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel

from src.domain.services.user_service import UserService
from src.application.use_cases.create_user import CreateUserUseCase, CreateUserRequest
from src.infrastructure.database.user_db import InMemoryUserRepository

router = APIRouter()

# Dependency injection setup
def get_user_repository():
    """Get user repository instance."""
    return InMemoryUserRepository()

def get_user_service(repo=Depends(get_user_repository)):
    """Get user service instance."""
    return UserService(repo)

def get_create_user_use_case(service=Depends(get_user_service)):
    """Get create user use case instance."""
    return CreateUserUseCase(service)


class CreateUserDTO(BaseModel):
    """Create user data transfer object."""
    email: str
    name: str


class UserDTO(BaseModel):
    """User data transfer object."""
    id: int
    email: str
    name: str
    created_at: str
    updated_at: str


@router.post("/", response_model=UserDTO)
async def create_user(
    user_data: CreateUserDTO,
    use_case: CreateUserUseCase = Depends(get_create_user_use_case)
):
    """Create a new user."""
    request = CreateUserRequest(email=user_data.email, name=user_data.name)
    response = await use_case.execute(request)
    
    if not response.success:
        raise HTTPException(status_code=400, detail=response.message)
    
    return UserDTO(
        id=response.user.id,
        email=response.user.email,
        name=response.user.name,
        created_at=response.user.created_at.isoformat(),
        updated_at=response.user.updated_at.isoformat()
    )


@router.get("/{user_id}", response_model=UserDTO)
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    """Get user by ID."""
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserDTO(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat()
    )


@router.get("/", response_model=List[UserDTO])
async def list_users(service: UserService = Depends(get_user_service)):
    """List all users."""
    users = await service.list_users()
    return [
        UserDTO(
            id=user.id,
            email=user.email,
            name=user.name,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat()
        )
        for user in users
    ]
```

### requirements.txt
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
python-multipart==0.0.6
```

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENV=development
    volumes:
      - .:/app
```

### .env.example
```
ENV=development
LOG_LEVEL=info
```

### .gitignore
```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

.pytest_cache/
.coverage
htmlcov/

.vscode/
.idea/
*.swp
*.swo
```

### README.md
```markdown
# Hexagonal FastAPI Service

A FastAPI web service implementing Hexagonal Architecture (Ports & Adapters) pattern.

## Architecture

This project follows Hexagonal Architecture principles:

- **Domain Layer**: Contains business entities, services, and repository interfaces
- **Application Layer**: Contains use cases and application-specific logic
- **Infrastructure Layer**: Contains external adapters (database, web API)

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
uvicorn src.main:app --reload
```

3. Access the API:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## API Endpoints

- `POST /api/v1/users/` - Create a new user
- `GET /api/v1/users/{user_id}` - Get user by ID
- `GET /api/v1/users/` - List all users
- `GET /health` - Health check

## Testing

Run tests with:
```bash
pytest tests/
```

## Docker

Build and run with Docker:
```bash
docker-compose up --build
```
```

## Template Usage Notes

This template creates a complete FastAPI service with:

1. **Clean Architecture** - Proper separation of concerns
2. **Domain-Driven Design** - Rich domain entities and services
3. **Dependency Injection** - Proper DI setup with FastAPI
4. **RESTful API** - Complete CRUD operations
5. **Docker Support** - Ready for containerization
6. **Testing Structure** - Organized test directory
7. **Development Tools** - Requirements, gitignore, environment setup

The template follows best practices for:
- Error handling
- Validation
- API documentation
- Code organization
- Dependency management