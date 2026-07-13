# Coding Standards

## General Principles

### Naming Conventions
- Use descriptive names that clearly indicate the purpose
- Follow Python naming conventions (snake_case for variables/functions, PascalCase for classes)
- Avoid abbreviations unless they are widely known and accepted
- Class names should be nouns; method names should be verbs

### Code Style
- Follow PEP 8 style guide
- Use 4 spaces for indentation (no tabs)
- Maximum line length of 120 characters
- Import statements grouped in order: standard library, third-party, local modules
- Each module should have a docstring explaining its purpose

### Documentation
- Every function and class must have a docstring
- Docstrings should follow Google Python Style Guide format
- Module-level documentation for each file
- Inline comments for complex logic sections

## Architecture-Specific Guidelines

### Domain Layer
- Entities should be immutable when possible
- Interfaces defined in domain layer with clear contracts
- No external dependencies allowed (no database, no HTTP clients)

### Application Layer
- Services should contain business logic only
- Use dependency injection for service composition
- Avoid direct database access; use repositories instead

### Infrastructure Layer
- Implement interfaces defined in domain layer
- Handle technical concerns like databases and external APIs
- Follow repository pattern for data access operations

## Testing Requirements

### Unit Tests
- Each class should have corresponding unit tests
- Test all public methods of services, entities, and repositories
- Use mocking to isolate dependencies during testing

### Integration Tests
- Verify that components work together correctly
- Test database interactions through repositories
- Validate end-to-end functionality

## Code Quality Metrics
- Maintain code coverage > 85%
- Keep cyclomatic complexity < 10 per function
- No duplicate code allowed (use refactoring instead)
- All tests must pass before merging to main branch

This document ensures consistency across the entire project and maintains high-quality standards.
