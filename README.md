# TaskHub API

Task management backend built with FastAPI, SQLAlchemy 2.x (async), Alembic, PostgreSQL 16, and Redis 7.

## Project Structure

```text
app/
├── api/
│   ├── deps.py           # JWT auth dependencies
│   └── v1/endpoints/     # Route handlers
├── core/                 # Config, security, RBAC, cache, middleware, exception handlers
├── db/                   # Async engine, session, Base metadata
├── models/               # SQLAlchemy ORM models
├── repositories/         # BaseRepository + entity repositories
├── schemas/              # Pydantic v2 schemas
└── services/             # Business logic & background notifications
alembic/                  # Database migrations
tests/                    # Pytest async integration tests
```

## Features

- Auth with JWT access/refresh tokens, refresh token rotation, and logout revocation
- User profile (`GET/PATCH /users/me`) and change password
- Workspaces with member management and RBAC (`ADMIN`, `OWNER`, `EDITOR`, `VIEWER`)
- Projects CRUD and archive (`ACTIVE` / `ARCHIVED`)
- Tasks CRUD, assignees, status/priority/due_date, filtering, and pagination
- Project labels (attach/detach on tasks) and task comments
- Redis caching for `GET /api/v1/projects/{id}/tasks` with automatic invalidation on updates
- Background task email notification when assigning a task
- Swagger UI (`/docs`) and ReDoc (`/redoc`) with Bearer auth

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

- API: `http://localhost:8000/api/v1`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Run Locally

Requirements: Python 3.12+, PostgreSQL 16, Redis 7 (if Redis is not running, cache falls back to in-memory TTL store).

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -e ".[dev]"
cp .env.example .env

alembic upgrade head
uvicorn app.main:app --reload
```

## Environment Variables

See `.env.example` for the full list. Main variables:

- `ENVIRONMENT`: `development` | `staging` | `production` | `test`
- `DEBUG`: `true` / `false` (must be `false` in staging/production)
- `DATABASE_URL`: async SQLAlchemy URL (e.g. `postgresql+asyncpg://taskhub:taskhub@localhost:5432/taskhub`)
- `REDIS_URL`: Redis connection string (e.g. `redis://localhost:6379/0`)
- `CACHE_TTL_SECONDS`: cache expiry in seconds (default `60`)
- `SECRET_KEY`: JWT signing key (must be >= 32 chars in staging/production)
- `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS`: token lifetimes
- `SMTP_ENABLED`: set `true` to send real SMTP emails, otherwise notifications are logged

## Tests & Lint

```bash
pytest -v
ruff check app tests
ruff format --check app tests
mypy app
```
