# Project Architecture

## Overview
This project follows a Clean Architecture pattern, separating business logic from infrastructure concerns. The architecture is divided into distinct layers that maintain clear boundaries and dependencies flowing inward toward the core domain.

## Layered Structure

### 1. Presentation Layer (UI)
- Handles user interaction and display
- Contains controllers, views, and UI components
- Depends on application services for business operations

### 2. Application Layer
- Contains use cases and application logic
- Coordinates between presentation and domain layers
- Uses dependency injection for service composition

### 3. Domain Layer (Core)
- Contains core business logic and entities
- Defines interfaces that other layers implement
- Independent of external frameworks or databases

### 4. Infrastructure Layer
- Handles technical details like database access, file systems, etc.
- Implements domain interfaces
- Provides concrete implementations for repositories and services

## Configuration System

### Enterprise Configuration Manager
The project now includes a comprehensive enterprise configuration system with the following features:

1. **YAML Support** - Configuration files in YAML format
2. **.env Support** - Environment variable file support
3. **Environment Overrides** - Runtime environment-specific configurations
4. **Development/Production Configurations** - Separate configs for different environments
5. **Secret Management** - Secure handling of sensitive information
6. **Validation** - Input validation and error checking
7. **Strong Typing** - Type-safe configuration objects
8. **Configuration Caching** - Performance optimization through caching

### Configuration Structure
