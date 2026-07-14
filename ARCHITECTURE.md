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

## Key Principles

### SOLID Principles
1. **Single Responsibility Principle**: Each class has one reason to change
2. **Open/Closed Principle**: Open for extension, closed for modification
3. **Liskov Substitution Principle**: Subtypes must be substitutable for their base types
4. **Interface Segregation Principle**: Clients should not be forced to depend on interfaces they don't use
5. **Dependency Inversion Principle**: Depend on abstractions, not concretions

### Repository Pattern
- Abstracts data access operations
- Provides a clean interface between domain and infrastructure layers
- Enables testability through mocking

### Event Bus
- Facilitates loose coupling between components
- Supports publish/subscribe communication patterns
- Enables asynchronous processing of business events

## File Structure
