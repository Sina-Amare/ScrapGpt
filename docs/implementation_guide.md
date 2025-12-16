# ScrapGPT Implementation Guide

A learning document explaining every component built in this project.

---

## Table of Contents

1. [Project Architecture](#1-project-architecture)
2. [Database & User Model](#2-database--user-model)
3. [Authentication System](#3-authentication-system)
4. [Credit System](#4-credit-system)
5. [Protected Scraping Endpoint](#5-protected-scraping-endpoint)
6. [Key Patterns & Concepts](#6-key-patterns--concepts)

---

## 1. Project Architecture

### What We Built

A FastAPI backend with:

- Async PostgreSQL database
- JWT authentication
- Credit-based rate limiting
- Web scraping endpoint

### Why This Structure

```
app/
├── api/                  # HTTP layer (routes, dependencies)
│   ├── deps.py           # Shared dependencies (auth, db)
│   └── v1/endpoints/     # Versioned endpoints
├── core/                 # Business logic utilities
│   ├── config.py         # Settings from environment
│   └── security.py       # Password hashing, JWT
├── db/                   # Database connection
├── models/               # SQLAlchemy ORM models
└── schemas/              # Pydantic request/response models
```

**Why separate `models/` and `schemas/`?**

- `models/` = Database tables (SQLAlchemy) - how data is **stored**
- `schemas/` = API contracts (Pydantic) - how data is **transferred**

This separation lets you:

- Add database fields without breaking the API
- Change API format without touching the database
- Validate input differently than storage

---

## 2. Database & User Model

### The User Model (`app/models/user.py`)

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Credit system
    credits_remaining = Column(Integer, default=5)
    daily_credit_limit = Column(Integer, default=5)
    credits_reset_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### Why These Fields?

| Field                | Purpose                                     |
| -------------------- | ------------------------------------------- |
| `email`              | Unique identifier + login credential        |
| `hashed_password`    | Never store plain passwords!                |
| `is_active`          | Soft-disable accounts without deleting      |
| `is_verified`        | Future: email verification                  |
| `credits_remaining`  | Current available credits                   |
| `daily_credit_limit` | Per-user limit (allows premium tiers later) |
| `credits_reset_at`   | When credits were last reset                |

### Database Migration (`alembic/versions/001_create_users.py`)

```python
def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, index=True),
        # ... more columns
    )
    op.create_index('ix_users_email', 'users', ['email'])
```

**Why Alembic?**

- Version control for database schema
- Can upgrade/downgrade between versions
- Team members get same schema via `alembic upgrade head`

---

## 3. Authentication System

### How JWT Authentication Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Login Flow                                │
├─────────────────────────────────────────────────────────────┤
│  1. User sends: email + password                            │
│  2. Server verifies password against hash                   │
│  3. Server creates JWT with user_id inside                  │
│  4. User receives: access_token + refresh_token             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Protected Request                         │
├─────────────────────────────────────────────────────────────┤
│  1. User sends: Authorization: Bearer <access_token>        │
│  2. Server decodes JWT, extracts user_id                    │
│  3. Server fetches user from database                       │
│  4. Request proceeds with user context                      │
└─────────────────────────────────────────────────────────────┘
```

### Password Hashing (`app/core/security.py`)

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"])

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)  # "$2b$12$..."

def verify_password(plain_password: str, hashed: str) -> bool:
    return pwd_context.verify(plain_password, hashed)
```

**Why bcrypt?**

- Slow by design (prevents brute force)
- Includes salt automatically (same password → different hashes)
- Industry standard for password storage

### JWT Token Creation

```python
def create_access_token(subject: str | int) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=15)
    payload = {
        "sub": str(subject),  # User ID
        "exp": expire,        # Expiration time
        "type": "access",     # Token type
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
```

**Why two tokens?**

| Token         | Lifetime | Purpose                                   |
| ------------- | -------- | ----------------------------------------- |
| Access Token  | 15 min   | Short-lived, used for API calls           |
| Refresh Token | 7 days   | Long-lived, used to get new access tokens |

If access token is stolen, damage is limited to 15 minutes.

### OAuth2 Login Endpoint

```python
@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),  # Form data
    db: AsyncSession = Depends(get_db),
):
    user = await db.execute(select(User).where(User.email == form_data.username))
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")

    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
    }
```

**Why OAuth2PasswordRequestForm?**

- Standard OAuth2 format (username + password as form data)
- Works with Swagger UI's "Authorize" button
- Industry-standard pattern

---

## 4. Credit System

### The Lazy Reset Pattern

Instead of running a cron job every day to reset credits, we reset **on-demand**:

```python
def ensure_credits_reset(self) -> bool:
    """Reset credits if 24 hours have passed."""
    now = datetime.now(timezone.utc)

    if self.credits_reset_at is None:
        self.credits_reset_at = now
        return False

    hours_since_reset = (now - self.credits_reset_at).total_seconds() / 3600

    if hours_since_reset >= 24:
        self.credits_remaining = self.daily_credit_limit
        self.credits_reset_at = now
        return True  # Reset occurred

    return False
```

**Why lazy reset?**

- No background jobs needed
- No database polling
- Credits reset exactly when needed
- Simpler infrastructure

### Credit Check Dependency

```python
async def require_credits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Trigger lazy reset
    if current_user.ensure_credits_reset():
        await db.commit()

    # Check credits
    if current_user.credits_remaining <= 0:
        raise HTTPException(403, "No credits remaining")

    return current_user
```

**Why a dependency?**

- Reusable across any endpoint
- Separation of concerns (endpoint doesn't handle credit logic)
- Easy to test in isolation

---

## 5. Protected Scraping Endpoint

### The Endpoint (`app/api/v1/endpoints/scrape.py`)

```python
@router.post("")
async def scrape_url(
    request: ScrapeRequest,
    user: User = Depends(require_credits),  # Auth + credit check
    db: AsyncSession = Depends(get_db),
):
    # Fetch URL
    async with httpx.AsyncClient() as client:
        response = await client.get(str(request.url))

    # Parse HTML
    soup = BeautifulSoup(response.text, "lxml")
    title = soup.title.string if soup.title else None
    content = soup.get_text(separator="\n", strip=True)

    # Deduct credit AFTER success
    await deduct_credit(user, db)

    return ScrapeResponse(
        success=True,
        url=str(request.url),
        title=title,
        content=content[:10000],
        credits_remaining=user.credits_remaining,
    )
```

### Why Deduct AFTER Success?

```python
# ❌ BAD: Deduct before scraping
user.credits_remaining -= 1
await db.commit()
response = await client.get(url)  # What if this fails?

# ✅ GOOD: Deduct after success
response = await client.get(url)
if response.ok:
    user.credits_remaining -= 1
    await db.commit()
```

If scraping fails, the user shouldn't lose a credit.

---

## 6. Key Patterns & Concepts

### Dependency Injection

FastAPI's `Depends()` lets you inject shared logic:

```python
# Instead of repeating this in every endpoint:
@router.get("/items")
async def get_items():
    token = extract_token_from_header(request)
    payload = verify_jwt(token)
    user = await db.get(User, payload.sub)
    # ... actual logic

# You write it once as a dependency:
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = verify_token(token)
    user = await db.get(User, payload.sub)
    return user

# And reuse everywhere:
@router.get("/items")
async def get_items(user: User = Depends(get_current_user)):
    # user is automatically available
```

### Pydantic Schemas

Validate input and serialize output:

```python
class ScrapeRequest(BaseModel):
    url: HttpUrl  # Validates it's a real URL
    selector: str | None = None

class ScrapeResponse(BaseModel):
    success: bool
    url: str
    content: str
    credits_remaining: int

@router.post("", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequest):  # Auto-validated
    ...
    return ScrapeResponse(...)  # Auto-serialized
```

### Async Database Sessions

```python
async with AsyncSession(engine) as session:
    result = await session.execute(select(User).where(User.id == 1))
    user = result.scalar_one_or_none()
```

**Why async?**

- Non-blocking I/O
- Handle thousands of concurrent requests
- Database waits don't block other requests

---

## Summary

| Component  | Pattern              | Why                               |
| ---------- | -------------------- | --------------------------------- |
| User Model | SQLAlchemy ORM       | Type-safe database access         |
| Passwords  | bcrypt hashing       | Secure, salted, slow              |
| Auth       | JWT tokens           | Stateless, scalable               |
| Credits    | Lazy reset           | No cron jobs needed               |
| Scraping   | Dependency injection | Clean, reusable, testable         |
| Validation | Pydantic schemas     | Automatic input/output validation |

---

## Next Steps to Learn

1. **Add tests** - `pytest` with `pytest-asyncio`
2. **Error handling** - Custom exception handlers
3. **Rate limiting** - Beyond credits (requests per second)
4. **Background tasks** - Celery or FastAPI BackgroundTasks
5. **Caching** - Redis for scraped content
