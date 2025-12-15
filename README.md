# ScrapGPT

A professional, production-ready FastAPI web scraping platform with AI capabilities.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **🔐 JWT Authentication** - Secure token-based authentication with refresh tokens
- **🌐 Web Scraping** - BeautifulSoup & Playwright for static and dynamic content
- **⚡ Async Everything** - Built with async/await for high performance
- **📊 Job Queue** - Async task processing for long-running scrapes
- **💳 Credit System** - Rate limiting with credit-based usage tracking
- **🗄️ PostgreSQL** - Production-ready database with async SQLAlchemy
- **📖 Auto Documentation** - Interactive Swagger UI and ReDoc

## Quick Start

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14+
- Git

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/scrapegpt.git
cd scrapegpt

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your settings
# IMPORTANT: Change SECRET_KEY for production!
```

### 4. Setup Database

```bash
# Create database
createdb scrapegpt

# Run migrations
alembic upgrade head
```

### 5. Run Development Server

```bash
uvicorn app.main:app --reload
```

Visit: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Project Structure

```
scrapegpt/
├── app/
│   ├── __init__.py          # Package info and version
│   ├── main.py              # FastAPI application entry point
│   ├── api/
│   │   ├── deps.py          # Dependency injection
│   │   └── v1/
│   │       ├── router.py    # v1 API router
│   │       └── endpoints/   # Route handlers
│   ├── core/
│   │   ├── config.py        # Settings management
│   │   └── security.py      # Auth utilities
│   ├── db/
│   │   └── database.py      # Database connection
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic validation schemas
│   └── services/            # Business logic layer
├── alembic/                 # Database migrations
├── docs/                    # Documentation
├── tests/                   # Test suite
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
└── README.md
```

## API Endpoints

| Endpoint               | Method | Description               |
| ---------------------- | ------ | ------------------------- |
| `/`                    | GET    | API info                  |
| `/docs`                | GET    | Swagger UI                |
| `/api/v1/health`       | GET    | Health check              |
| `/api/v1/health/ready` | GET    | Readiness check (with DB) |
| `/api/v1/health/live`  | GET    | Liveness probe            |

## Architecture

### Layers

1. **API Layer** (`app/api/`) - HTTP request/response handling
2. **Service Layer** (`app/services/`) - Business logic
3. **Data Layer** (`app/models/`, `app/db/`) - Database operations

### Key Design Decisions

- **Async-first**: All I/O operations use async/await
- **API Versioning**: `/api/v1/` prefix for future compatibility
- **Dependency Injection**: Clean, testable code with FastAPI's `Depends()`
- **Type Safety**: Full type hints with Pydantic validation

See [docs/architecture.md](docs/architecture.md) for detailed explanations.

## Development

### Code Style

```bash
# Lint with ruff
ruff check .

# Type check with mypy
mypy app/
```

### Running Tests

```bash
pytest tests/ -v
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Production Deployment

### Important Settings

1. Set `ENVIRONMENT=production`
2. Set `DEBUG=false`
3. Generate secure `SECRET_KEY`: `openssl rand -hex 32`
4. Configure proper `CORS_ORIGINS`
5. Use Gunicorn with multiple workers:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## License

MIT License - see [LICENSE](LICENSE) for details.

---

Built with ❤️ using [FastAPI](https://fastapi.tiangolo.com)
