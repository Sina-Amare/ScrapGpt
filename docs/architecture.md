# ScrapGPT Architecture

This document explains the architectural decisions and design patterns used in ScrapGPT.

## Overview

ScrapGPT follows a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation Layer                      │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│ │   Routes    │  │   Schemas   │  │  Middleware │          │
│ │ (endpoints) │  │  (Pydantic) │  │   (CORS)    │          │
│ └──────┬──────┘  └──────┬──────┘  └─────────────┘          │
│        │                │                                    │
│        └────────────────┴───────────┐                       │
│                                     ▼                       │
├─────────────────────────────────────────────────────────────┤
│                      Business Layer                          │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │                      Services                            │ │
│ │  (scraping logic, auth logic, credit management, etc.)  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                             │                                │
├─────────────────────────────┼───────────────────────────────┤
│                      Data Layer                              │
│ ┌─────────────────┐  ┌─────────────────┐                   │
│ │     Models      │  │   Database      │                   │
│ │  (SQLAlchemy)   │  │   (AsyncPG)     │                   │
│ └─────────────────┘  └─────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure Rationale

### `/app/api/` - API Layer

Contains HTTP-specific code: route handlers, request/response handling.

- **`deps.py`**: Dependency injection functions (database sessions, current user)
- **`v1/endpoints/`**: Versioned endpoint handlers
- **`v1/router.py`**: Route aggregation

**Why versioning?** Allows breaking changes in v2 without affecting v1 clients.

### `/app/core/` - Core Configuration

Application-wide settings and utilities that don't belong elsewhere.

- **`config.py`**: Environment-based configuration with validation
- **`security.py`**: Authentication utilities (JWT, password hashing)

**Why pydantic-settings?** Type-safe configuration with automatic environment variable loading and validation at startup.

### `/app/db/` - Database Layer

Database connection and session management.

- **`database.py`**: Async engine, session factory, dependency

**Why async SQLAlchemy?** Non-blocking database operations align with FastAPI's async architecture, enabling high concurrency.

### `/app/models/` - ORM Models

SQLAlchemy models representing database tables.

- **`base.py`**: Base class and mixins (timestamps, soft delete)

**Why mixins?** Reduce code duplication for common patterns like `created_at`, `updated_at`.

### `/app/schemas/` - Pydantic Schemas

Request/response validation and serialization.

**Why separate from models?**

1. Different purposes (ORM vs API contract)
2. Flexibility to expose different views of the same data
3. Clear input validation rules

### `/app/services/` - Business Logic

Domain-specific logic separated from HTTP concerns.

**Why services?**

1. Testable without HTTP layer
2. Reusable across different endpoints
3. Single responsibility principle

## Key Design Decisions

### 1. Async-First Architecture

**Decision**: Use async/await throughout the stack.

**Rationale**:

- Web scraping involves significant I/O wait time
- Async allows handling many concurrent requests efficiently
- FastAPI is built on Starlette which is async-native

**Trade-off**: Slightly more complex code, must use async database drivers.

### 2. Dependency Injection

**Decision**: Use FastAPI's `Depends()` for all shared resources.

**Rationale**:

- Clean, testable code
- Easy to swap implementations (e.g., mock database for tests)
- Explicit dependencies in function signatures

**Example**:

```python
@router.get("/users")
async def get_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # db and current_user are injected
```

### 3. Configuration Management

**Decision**: Use pydantic-settings with environment variables.

**Rationale**:

- Type-safe configuration
- Validation at startup (fail fast)
- 12-factor app compliance
- Local development with `.env` file

### 4. API Versioning

**Decision**: Use URL path versioning (`/api/v1/`).

**Alternatives considered**:

- Header versioning: Less discoverable
- Query parameter: Not RESTful

**Rationale**: Clear, explicit, works with OpenAPI, easy to maintain.

### 5. JWT Authentication

**Decision**: Use JWT with access/refresh token pattern.

**Rationale**:

- Stateless authentication (scales horizontally)
- Short-lived access tokens (security)
- Refresh tokens for seamless session extension

## Error Handling Strategy

```python
# Global exception handler in main.py
@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )
```

**Approach**: Consistent error response format across all endpoints.

## Security Considerations

1. **Password Hashing**: bcrypt with configurable rounds
2. **JWT Secrets**: Validated at startup, warning for default values
3. **CORS**: Configurable allowed origins
4. **SQL Injection**: Prevented by SQLAlchemy's parameterized queries
5. **Input Validation**: All inputs validated via Pydantic schemas

## Scaling Considerations

### Horizontal Scaling

The application is stateless (JWT auth, no session storage), making it easy to run multiple instances behind a load balancer.

### Database Connection Pooling

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
)
```

Prevents connection exhaustion under load.

### Background Jobs (Future)

For long-running scraping tasks, a job queue (Celery, ARQ) will handle:

- Async task execution
- Retry logic
- Result storage

## Testing Strategy

1. **Unit Tests**: Test services in isolation
2. **Integration Tests**: Test with real database (use Docker)
3. **API Tests**: Test endpoints with `httpx` AsyncClient

```python
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
```

---

_Last updated: December 2024_
