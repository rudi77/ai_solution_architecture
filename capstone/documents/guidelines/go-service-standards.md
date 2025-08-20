# Go Service Development Standards

## Project Structure

All Go services should follow this standard structure:

```
service-name/
├── cmd/
│   └── service-name/
│       └── main.go
├── internal/
│   ├── handlers/
│   ├── services/
│   ├── models/
│   └── config/
├── pkg/
├── api/
├── deployments/
├── scripts/
├── go.mod
├── go.sum
├── Dockerfile
└── README.md
```

## Framework Requirements

- **Web Framework**: Use Gin for HTTP services
- **Database**: GORM for ORM, PostgreSQL preferred
- **Logging**: Use structured logging with logrus
- **Configuration**: Use Viper for configuration management
- **Testing**: Use testify for assertions

## Code Standards

### Naming Conventions
- Use descriptive names for variables and functions
- Package names should be lowercase, single words
- Use camelCase for unexported identifiers
- Use PascalCase for exported identifiers

### Error Handling
- Always handle errors explicitly
- Wrap errors with context using fmt.Errorf or pkg/errors
- Return errors as the last value in multiple return statements

### Dependency Management
- Use Go modules for dependency management
- Pin dependency versions in go.mod
- Regular dependency updates via security scanning

## API Standards

### REST API Guidelines
- Use standard HTTP status codes
- Implement proper CORS handling
- Use JSON for request/response bodies
- Include request ID in logs and responses

### Response Format
```json
{
  "success": true,
  "data": {},
  "message": "Optional message",
  "request_id": "uuid"
}
```

## Security Requirements

- Always validate input data
- Implement rate limiting
- Use HTTPS in production
- Sanitize user inputs
- Never log sensitive information

## Performance Guidelines

- Use connection pooling for databases
- Implement graceful shutdown
- Add health check endpoints
- Use proper timeouts for external calls
- Implement circuit breakers for external dependencies

## Testing Requirements

- Minimum 80% code coverage
- Unit tests for all business logic
- Integration tests for API endpoints
- Use test containers for database tests
- Mock external dependencies

## Deployment Standards

- Use multi-stage Docker builds
- Run as non-root user in containers
- Include health check endpoints
- Use environment variables for configuration
- Implement proper logging and monitoring