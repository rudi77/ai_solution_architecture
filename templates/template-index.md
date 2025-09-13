# Template Index

## Available Project Templates

This directory contains project templates for the IDP Copilot template-based project generation system.

### Python Templates

#### python-fastapi-hexagonal.md
- **Language**: Python
- **Framework**: FastAPI
- **Architecture**: Hexagonal Architecture (Ports & Adapters)
- **Features**: Domain-Driven Design, Dependency Injection, Clean Architecture
- **Use Cases**: Microservices, API Services, Domain-Rich Applications

#### python-flask-mvc.md
- **Language**: Python
- **Framework**: Flask
- **Architecture**: Model-View-Controller (MVC)
- **Features**: SQLAlchemy ORM, Flask Blueprints, Database Migrations
- **Use Cases**: Web Applications, RESTful APIs, Traditional Web Services

### C# Templates

#### csharp-webapi-clean.md
- **Language**: C#
- **Framework**: ASP.NET Core Web API
- **Architecture**: Clean Architecture with CQRS
- **Features**: MediatR, Entity Framework Core, Dependency Injection
- **Use Cases**: Enterprise APIs, Microservices, CQRS Applications

## Template Matching Keywords

### Python FastAPI
- Keywords: `python`, `fastapi`, `hexagonal`, `clean`, `microservice`, `api`
- Architecture: Hexagonal Architecture
- Template: `python-fastapi-hexagonal.md`

### Python Flask
- Keywords: `python`, `flask`, `mvc`, `web`, `orm`, `sqlalchemy`
- Architecture: MVC Pattern
- Template: `python-flask-mvc.md`

### C# Web API
- Keywords: `csharp`, `c#`, `dotnet`, `.net`, `webapi`, `clean`, `cqrs`
- Architecture: Clean Architecture with CQRS
- Template: `csharp-webapi-clean.md`

## Template Selection Logic

The template selection system works as follows:

1. **Parse User Input**: Extract language, framework, and architecture preferences
2. **Keyword Matching**: Match input against template keywords
3. **Disambiguation**: If multiple templates match, ask clarifying questions
4. **Single Selection**: Ensure exactly one template is selected before proceeding

### Example Disambiguation Scenarios

**Input**: "Create Python Web Service"
- Matches: `python-fastapi-hexagonal.md` and `python-flask-mvc.md`
- Clarification: "I found Python FastAPI and Flask templates. Which framework do you prefer?"

**Input**: "Create C# API"
- Matches: `csharp-webapi-clean.md`
- Action: Proceed with Clean Architecture template

**Input**: "Create FastAPI service with hexagonal architecture"
- Matches: `python-fastapi-hexagonal.md`
- Action: Proceed with Hexagonal Architecture template

## Template Structure

Each template file contains:

1. **Description**: Brief overview of the template
2. **Architecture Pattern**: Architectural approach and principles
3. **Project Structure**: Complete directory and file layout
4. **Code Examples**: Detailed implementation examples for key files
5. **Configuration Files**: Requirements, Docker, environment setup
6. **Documentation**: README and usage instructions

## Adding New Templates

To add a new template:

1. Create a new `.md` file following the naming convention: `{language}-{framework}-{pattern}.md`
2. Include all required sections (Description, Architecture, Project Structure, Code Examples)
3. Update this index file with the new template information
4. Add appropriate keywords for template matching

## Template Quality Standards

All templates must:

- Follow industry best practices for the chosen architecture
- Include complete, runnable code examples
- Provide proper error handling and validation
- Include testing structure and examples
- Follow consistent naming conventions
- Include necessary configuration files (Docker, requirements, etc.)
- Provide clear documentation and usage instructions