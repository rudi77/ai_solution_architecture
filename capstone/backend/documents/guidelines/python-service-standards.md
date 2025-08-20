# Python Service Development Standards

## Project Structure

All Python services should follow this standard structure:

```
service-name/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── services/
│   └── utils/
├── tests/
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── .gitignore
└── README.md
```

## Framework Requirements

- **Web Framework**: FastAPI for REST APIs
- **Database**: SQLAlchemy 2.0+ with async support
- **Validation**: Pydantic v2 for data validation
- **Testing**: pytest with async support
- **Logging**: Use Python's built-in logging with structured format

## Code Standards

### Naming Conventions
- Use snake_case for variables and functions
- Use PascalCase for classes
- Use UPPER_CASE for constants
- Use descriptive names

### Type Hints
- Always use type hints for function parameters and returns
- Use generic types where appropriate
- Import types from typing module

### Error Handling
- Use custom exceptions for business logic errors
- Always catch and handle specific exceptions
- Use proper HTTP status codes for API errors

### Code Quality
- Use black for code formatting
- Use ruff for linting
- Use mypy for type checking
- Maximum line length: 100 characters

## API Standards

### FastAPI Guidelines
- Use dependency injection for common operations
- Implement proper request/response models with Pydantic
- Add OpenAPI documentation
- Use async/await for I/O operations

### Response Format
```python
class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    errors: Optional[List[str]] = None
```

## Database Standards

- Use async SQLAlchemy for database operations
- Implement proper connection pooling
- Use Alembic for database migrations
- Follow naming conventions for tables and columns

## Security Requirements

- Validate all input data with Pydantic
- Implement proper authentication and authorization
- Use HTTPS in production
- Sanitize user inputs
- Implement rate limiting with slowapi

## Performance Guidelines

- Use async/await for I/O bound operations
- Implement proper caching strategies
- Use connection pooling
- Implement health check endpoints
- Monitor performance with middleware

## Testing Requirements

- Minimum 85% code coverage
- Use pytest with async support
- Use pytest fixtures for test data
- Use httpx for testing async endpoints
- Mock external dependencies

## Deployment Standards

- Use multi-stage Docker builds
- Use Python 3.11+ in production
- Run with uvicorn in production
- Use environment variables for configuration
- Implement proper logging and monitoring
- Use gunicorn with uvicorn workers for production