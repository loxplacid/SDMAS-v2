# Module Guidelines

## Module Organization

### Domain Modules
Modules in the domain layer should contain:
- Core entities (models, value objects)
- Interfaces for services and repositories
- Domain exceptions
- Constants and enums specific to business logic

### Application Modules
Application modules should include:
- Use cases (service classes that implement business logic)
- Service interfaces and implementations
- Event handling components
- Data transfer objects (DTOs)

### Infrastructure Modules
Infrastructure modules contain:
- Database repository implementations
- External API clients
- File system operations
- Configuration management
- Logging implementations

## Module Naming Conventions

### Domain Layer
