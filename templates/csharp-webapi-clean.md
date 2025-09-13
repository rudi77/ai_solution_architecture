# C# Web API Clean Architecture Template

## Description
ASP.NET Core Web API with Clean Architecture pattern

## Architecture Pattern
- **Clean Architecture (Onion Architecture)**
- **CQRS with MediatR**
- **Entity Framework Core**
- **Dependency Injection**

## Project Structure
```
src/
├── Domain/
│   ├── Entities/
│   │   └── User.cs
│   ├── Enums/
│   │   └── UserStatus.cs
│   └── Interfaces/
│       └── IUserRepository.cs
├── Application/
│   ├── Common/
│   │   ├── Interfaces/
│   │   │   └── IApplicationDbContext.cs
│   │   └── Models/
│   │       └── Result.cs
│   ├── Users/
│   │   ├── Commands/
│   │   │   ├── CreateUser/
│   │   │   │   ├── CreateUserCommand.cs
│   │   │   │   └── CreateUserCommandHandler.cs
│   │   │   └── UpdateUser/
│   │   │       ├── UpdateUserCommand.cs
│   │   │       └── UpdateUserCommandHandler.cs
│   │   └── Queries/
│   │       ├── GetUser/
│   │       │   ├── GetUserQuery.cs
│   │       │   └── GetUserQueryHandler.cs
│   │       └── GetUsers/
│   │           ├── GetUsersQuery.cs
│   │           └── GetUsersQueryHandler.cs
│   └── DependencyInjection.cs
├── Infrastructure/
│   ├── Data/
│   │   ├── ApplicationDbContext.cs
│   │   ├── Configurations/
│   │   │   └── UserConfiguration.cs
│   │   └── Repositories/
│   │       └── UserRepository.cs
│   └── DependencyInjection.cs
└── WebApi/
    ├── Controllers/
    │   └── UsersController.cs
    ├── Middleware/
    │   └── ExceptionHandlingMiddleware.cs
    ├── Models/
    │   ├── CreateUserRequest.cs
    │   ├── UpdateUserRequest.cs
    │   └── UserResponse.cs
    ├── Program.cs
    └── appsettings.json
tests/
├── Domain.Tests/
├── Application.Tests/
├── Infrastructure.Tests/
└── WebApi.Tests/
CleanArchitecture.sln
Directory.Build.props
.gitignore
README.md
```

## Code Examples

### src/Domain/Entities/User.cs
```csharp
using System;

namespace Domain.Entities
{
    public class User
    {
        public int Id { get; set; }
        public string Email { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        public UserStatus Status { get; set; }

        public User()
        {
            CreatedAt = DateTime.UtcNow;
            UpdatedAt = DateTime.UtcNow;
            Status = UserStatus.Active;
        }

        public User(string email, string name) : this()
        {
            Email = email ?? throw new ArgumentNullException(nameof(email));
            Name = name ?? throw new ArgumentNullException(nameof(name));
        }

        public void UpdateName(string name)
        {
            Name = name ?? throw new ArgumentNullException(nameof(name));
            UpdatedAt = DateTime.UtcNow;
        }

        public void UpdateEmail(string email)
        {
            Email = email ?? throw new ArgumentNullException(nameof(email));
            UpdatedAt = DateTime.UtcNow;
        }

        public void Deactivate()
        {
            Status = UserStatus.Inactive;
            UpdatedAt = DateTime.UtcNow;
        }
    }
}
```

### src/Domain/Enums/UserStatus.cs
```csharp
namespace Domain.Enums
{
    public enum UserStatus
    {
        Active = 1,
        Inactive = 2,
        Suspended = 3
    }
}
```

### src/Domain/Interfaces/IUserRepository.cs
```csharp
using Domain.Entities;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace Domain.Interfaces
{
    public interface IUserRepository
    {
        Task<User?> GetByIdAsync(int id, CancellationToken cancellationToken = default);
        Task<User?> GetByEmailAsync(string email, CancellationToken cancellationToken = default);
        Task<List<User>> GetAllAsync(CancellationToken cancellationToken = default);
        Task<User> AddAsync(User user, CancellationToken cancellationToken = default);
        Task<User> UpdateAsync(User user, CancellationToken cancellationToken = default);
        Task DeleteAsync(int id, CancellationToken cancellationToken = default);
    }
}
```

### src/Application/Common/Models/Result.cs
```csharp
using System.Collections.Generic;

namespace Application.Common.Models
{
    public class Result<T>
    {
        public bool IsSuccess { get; }
        public T? Value { get; }
        public List<string> Errors { get; }

        private Result(bool isSuccess, T? value, List<string> errors)
        {
            IsSuccess = isSuccess;
            Value = value;
            Errors = errors;
        }

        public static Result<T> Success(T value) => new(true, value, new List<string>());
        public static Result<T> Failure(List<string> errors) => new(false, default, errors);
        public static Result<T> Failure(string error) => new(false, default, new List<string> { error });
    }

    public class Result
    {
        public bool IsSuccess { get; }
        public List<string> Errors { get; }

        private Result(bool isSuccess, List<string> errors)
        {
            IsSuccess = isSuccess;
            Errors = errors;
        }

        public static Result Success() => new(true, new List<string>());
        public static Result Failure(List<string> errors) => new(false, errors);
        public static Result Failure(string error) => new(false, new List<string> { error });
    }
}
```

### src/Application/Users/Commands/CreateUser/CreateUserCommand.cs
```csharp
using MediatR;
using Application.Common.Models;
using Domain.Entities;

namespace Application.Users.Commands.CreateUser
{
    public record CreateUserCommand(string Email, string Name) : IRequest<Result<User>>;
}
```

### src/Application/Users/Commands/CreateUser/CreateUserCommandHandler.cs
```csharp
using MediatR;
using Domain.Entities;
using Domain.Interfaces;
using Application.Common.Models;
using System.Threading;
using System.Threading.Tasks;

namespace Application.Users.Commands.CreateUser
{
    public class CreateUserCommandHandler : IRequestHandler<CreateUserCommand, Result<User>>
    {
        private readonly IUserRepository _userRepository;

        public CreateUserCommandHandler(IUserRepository userRepository)
        {
            _userRepository = userRepository;
        }

        public async Task<Result<User>> Handle(CreateUserCommand request, CancellationToken cancellationToken)
        {
            // Validate input
            if (string.IsNullOrWhiteSpace(request.Email))
                return Result<User>.Failure("Email is required");

            if (string.IsNullOrWhiteSpace(request.Name))
                return Result<User>.Failure("Name is required");

            // Check if user already exists
            var existingUser = await _userRepository.GetByEmailAsync(request.Email, cancellationToken);
            if (existingUser != null)
                return Result<User>.Failure($"User with email {request.Email} already exists");

            // Create user
            var user = new User(request.Email, request.Name);
            var createdUser = await _userRepository.AddAsync(user, cancellationToken);

            return Result<User>.Success(createdUser);
        }
    }
}
```

### src/Application/Users/Queries/GetUser/GetUserQuery.cs
```csharp
using MediatR;
using Application.Common.Models;
using Domain.Entities;

namespace Application.Users.Queries.GetUser
{
    public record GetUserQuery(int Id) : IRequest<Result<User>>;
}
```

### src/Application/Users/Queries/GetUser/GetUserQueryHandler.cs
```csharp
using MediatR;
using Domain.Entities;
using Domain.Interfaces;
using Application.Common.Models;
using System.Threading;
using System.Threading.Tasks;

namespace Application.Users.Queries.GetUser
{
    public class GetUserQueryHandler : IRequestHandler<GetUserQuery, Result<User>>
    {
        private readonly IUserRepository _userRepository;

        public GetUserQueryHandler(IUserRepository userRepository)
        {
            _userRepository = userRepository;
        }

        public async Task<Result<User>> Handle(GetUserQuery request, CancellationToken cancellationToken)
        {
            var user = await _userRepository.GetByIdAsync(request.Id, cancellationToken);
            
            if (user == null)
                return Result<User>.Failure($"User with ID {request.Id} not found");

            return Result<User>.Success(user);
        }
    }
}
```

### src/Infrastructure/Data/ApplicationDbContext.cs
```csharp
using Microsoft.EntityFrameworkCore;
using Domain.Entities;
using Infrastructure.Data.Configurations;

namespace Infrastructure.Data
{
    public class ApplicationDbContext : DbContext
    {
        public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options) : base(options)
        {
        }

        public DbSet<User> Users { get; set; } = null!;

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            modelBuilder.ApplyConfiguration(new UserConfiguration());
            base.OnModelCreating(modelBuilder);
        }
    }
}
```

### src/Infrastructure/Data/Configurations/UserConfiguration.cs
```csharp
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Domain.Entities;

namespace Infrastructure.Data.Configurations
{
    public class UserConfiguration : IEntityTypeConfiguration<User>
    {
        public void Configure(EntityTypeBuilder<User> builder)
        {
            builder.HasKey(u => u.Id);

            builder.Property(u => u.Email)
                .IsRequired()
                .HasMaxLength(255);

            builder.Property(u => u.Name)
                .IsRequired()
                .HasMaxLength(100);

            builder.Property(u => u.CreatedAt)
                .IsRequired();

            builder.Property(u => u.UpdatedAt)
                .IsRequired();

            builder.Property(u => u.Status)
                .IsRequired()
                .HasConversion<int>();

            builder.HasIndex(u => u.Email)
                .IsUnique();
        }
    }
}
```

### src/Infrastructure/Data/Repositories/UserRepository.cs
```csharp
using Microsoft.EntityFrameworkCore;
using Domain.Entities;
using Domain.Interfaces;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace Infrastructure.Data.Repositories
{
    public class UserRepository : IUserRepository
    {
        private readonly ApplicationDbContext _context;

        public UserRepository(ApplicationDbContext context)
        {
            _context = context;
        }

        public async Task<User?> GetByIdAsync(int id, CancellationToken cancellationToken = default)
        {
            return await _context.Users.FindAsync(new object[] { id }, cancellationToken);
        }

        public async Task<User?> GetByEmailAsync(string email, CancellationToken cancellationToken = default)
        {
            return await _context.Users
                .FirstOrDefaultAsync(u => u.Email == email, cancellationToken);
        }

        public async Task<List<User>> GetAllAsync(CancellationToken cancellationToken = default)
        {
            return await _context.Users.ToListAsync(cancellationToken);
        }

        public async Task<User> AddAsync(User user, CancellationToken cancellationToken = default)
        {
            _context.Users.Add(user);
            await _context.SaveChangesAsync(cancellationToken);
            return user;
        }

        public async Task<User> UpdateAsync(User user, CancellationToken cancellationToken = default)
        {
            _context.Users.Update(user);
            await _context.SaveChangesAsync(cancellationToken);
            return user;
        }

        public async Task DeleteAsync(int id, CancellationToken cancellationToken = default)
        {
            var user = await GetByIdAsync(id, cancellationToken);
            if (user != null)
            {
                _context.Users.Remove(user);
                await _context.SaveChangesAsync(cancellationToken);
            }
        }
    }
}
```

### src/WebApi/Controllers/UsersController.cs
```csharp
using Microsoft.AspNetCore.Mvc;
using MediatR;
using WebApi.Models;
using Application.Users.Commands.CreateUser;
using Application.Users.Queries.GetUser;
using Application.Users.Queries.GetUsers;
using System.Threading.Tasks;

namespace WebApi.Controllers
{
    [ApiController]
    [Route("api/v1/[controller]")]
    public class UsersController : ControllerBase
    {
        private readonly IMediator _mediator;

        public UsersController(IMediator mediator)
        {
            _mediator = mediator;
        }

        [HttpPost]
        public async Task<ActionResult<UserResponse>> Create([FromBody] CreateUserRequest request)
        {
            var command = new CreateUserCommand(request.Email, request.Name);
            var result = await _mediator.Send(command);

            if (!result.IsSuccess)
                return BadRequest(new { Errors = result.Errors });

            var response = new UserResponse
            {
                Id = result.Value!.Id,
                Email = result.Value.Email,
                Name = result.Value.Name,
                Status = result.Value.Status.ToString(),
                CreatedAt = result.Value.CreatedAt,
                UpdatedAt = result.Value.UpdatedAt
            };

            return CreatedAtAction(nameof(GetById), new { id = response.Id }, response);
        }

        [HttpGet("{id}")]
        public async Task<ActionResult<UserResponse>> GetById(int id)
        {
            var query = new GetUserQuery(id);
            var result = await _mediator.Send(query);

            if (!result.IsSuccess)
                return NotFound(new { Errors = result.Errors });

            var response = new UserResponse
            {
                Id = result.Value!.Id,
                Email = result.Value.Email,
                Name = result.Value.Name,
                Status = result.Value.Status.ToString(),
                CreatedAt = result.Value.CreatedAt,
                UpdatedAt = result.Value.UpdatedAt
            };

            return Ok(response);
        }

        [HttpGet]
        public async Task<ActionResult<List<UserResponse>>> GetAll()
        {
            var query = new GetUsersQuery();
            var result = await _mediator.Send(query);

            if (!result.IsSuccess)
                return BadRequest(new { Errors = result.Errors });

            var responses = result.Value!.Select(user => new UserResponse
            {
                Id = user.Id,
                Email = user.Email,
                Name = user.Name,
                Status = user.Status.ToString(),
                CreatedAt = user.CreatedAt,
                UpdatedAt = user.UpdatedAt
            }).ToList();

            return Ok(responses);
        }
    }
}
```

### src/WebApi/Models/CreateUserRequest.cs
```csharp
using System.ComponentModel.DataAnnotations;

namespace WebApi.Models
{
    public class CreateUserRequest
    {
        [Required]
        [EmailAddress]
        public string Email { get; set; } = string.Empty;

        [Required]
        [StringLength(100, MinimumLength = 2)]
        public string Name { get; set; } = string.Empty;
    }
}
```

### src/WebApi/Models/UserResponse.cs
```csharp
using System;

namespace WebApi.Models
{
    public class UserResponse
    {
        public int Id { get; set; }
        public string Email { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string Status { get; set; } = string.Empty;
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }
}
```

### src/WebApi/Program.cs
```csharp
using Microsoft.EntityFrameworkCore;
using Infrastructure.Data;
using Application;
using Infrastructure;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Add application services
builder.Services.AddApplication();
builder.Services.AddInfrastructure(builder.Configuration);

// Add database
builder.Services.AddDbContext<ApplicationDbContext>(options =>
    options.UseSqlite(builder.Configuration.GetConnectionString("DefaultConnection")));

var app = builder.Build();

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();
app.UseAuthorization();
app.MapControllers();

// Health check
app.MapGet("/health", () => new { Status = "Healthy" });

app.Run();
```

### src/Application/DependencyInjection.cs
```csharp
using Microsoft.Extensions.DependencyInjection;
using MediatR;
using System.Reflection;

namespace Application
{
    public static class DependencyInjection
    {
        public static IServiceCollection AddApplication(this IServiceCollection services)
        {
            services.AddMediatR(cfg => cfg.RegisterServicesFromAssembly(Assembly.GetExecutingAssembly()));
            return services;
        }
    }
}
```

### src/Infrastructure/DependencyInjection.cs
```csharp
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Domain.Interfaces;
using Infrastructure.Data.Repositories;

namespace Infrastructure
{
    public static class DependencyInjection
    {
        public static IServiceCollection AddInfrastructure(this IServiceCollection services, IConfiguration configuration)
        {
            services.AddScoped<IUserRepository, UserRepository>();
            return services;
        }
    }
}
```

### CleanArchitecture.sln
```
Microsoft Visual Studio Solution File, Format Version 12.00
Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "Domain", "src\Domain\Domain.csproj", "{GUID1}"
EndProject
Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "Application", "src\Application\Application.csproj", "{GUID2}"
EndProject
Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "Infrastructure", "src\Infrastructure\Infrastructure.csproj", "{GUID3}"
EndProject
Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "WebApi", "src\WebApi\WebApi.csproj", "{GUID4}"
EndProject
Global
	GlobalSection(SolutionConfigurationPlatforms) = preSolution
		Debug|Any CPU = Debug|Any CPU
		Release|Any CPU = Release|Any CPU
	EndGlobalSection
EndGlobal
```

### README.md
```markdown
# Clean Architecture Web API

An ASP.NET Core Web API implementing Clean Architecture principles with CQRS pattern.

## Architecture

This project follows Clean Architecture (Onion Architecture) principles:

- **Domain Layer**: Core business entities and interfaces
- **Application Layer**: Use cases, commands, queries (CQRS with MediatR)
- **Infrastructure Layer**: Data access, external services
- **WebApi Layer**: Controllers, middleware, configuration

## Technologies

- .NET 8
- ASP.NET Core Web API
- Entity Framework Core
- MediatR (CQRS)
- SQLite (development)
- Swagger/OpenAPI

## Quick Start

1. Restore packages:
```bash
dotnet restore
```

2. Run migrations:
```bash
dotnet ef database update --project src/Infrastructure --startup-project src/WebApi
```

3. Run the application:
```bash
dotnet run --project src/WebApi
```

4. Access the API:
- API: https://localhost:7000
- Swagger: https://localhost:7000/swagger
- Health check: https://localhost:7000/health

## API Endpoints

- `POST /api/v1/users` - Create a new user
- `GET /api/v1/users/{id}` - Get user by ID
- `GET /api/v1/users` - List all users
- `GET /health` - Health check

## Testing

Run tests with:
```bash
dotnet test
```

## Project Structure

The solution is organized into four main projects following Clean Architecture:

1. **Domain** - Core business logic and entities
2. **Application** - Use cases and application logic
3. **Infrastructure** - Data access and external concerns
4. **WebApi** - API controllers and configuration
```

## Template Usage Notes

This template creates a complete .NET Web API with:

1. **Clean Architecture** - Proper dependency flow and separation
2. **CQRS Pattern** - Command Query Responsibility Segregation
3. **MediatR** - Mediator pattern implementation
4. **Entity Framework Core** - ORM with code-first approach
5. **Dependency Injection** - Built-in DI container
6. **Swagger/OpenAPI** - API documentation
7. **Result Pattern** - Consistent error handling
8. **Repository Pattern** - Data access abstraction

The template follows .NET best practices for:
- Project organization
- Dependency management
- Error handling
- API design
- Testing structure