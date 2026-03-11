# Domani Project Memory

## Project Overview
Domani is a domain expiration monitoring and snagging tool — a FastAPI web app intended to be Docker-containerized and hosted on GitHub.

## Tech Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 + SQLite (WAL mode)
- **Templates**: Jinja2 SSR with Bootstrap 5.3 dark theme (GitHub dark palette)
- **Scheduler**: APScheduler (AsyncIOScheduler, single worker required)
- **WHOIS**: python-whois with retry/backoff via asyncio
- **Notifications**: aiosmtplib (email), httpx (webhooks with HMAC signing)
- **Tests**: pytest + pytest-asyncio, 33 tests, all passing

## Key Architecture Decisions
- Single uvicorn worker (APScheduler runs in-process — no multi-worker)
- Shared `app/templates_config.py` for Jinja2 instance with all custom filters
- DB tables created on lifespan startup (not at import time — important for tests)
- `DATABASE_URL` must be set before importing app in tests

## Running locally
```bash
DATABASE_URL=sqlite:///./local.db uvicorn app.main:app --reload
```

## Running tests
```bash
DATABASE_URL=sqlite:///./test_domani.db .venv/bin/python -m pytest tests/ -v
```

## File Layout (key files)
- `app/main.py` — FastAPI app factory, lifespan, middleware, error handlers
- `app/templates_config.py` — Shared Jinja2 instance (all routers import from here)
- `app/services/scheduler_service.py` — APScheduler init, job reconciliation
- `app/services/whois_service.py` — WHOIS lookups with retry/backoff
- `app/services/domain_lifecycle.py` — State machine (DomainStatus enum + transitions)
- `app/services/alert_service.py` — Email + webhook dispatch
- `app/models/domain.py` — Domain ORM + DomainStatus enum
- `static/css/custom.css` — Dark GitHub-style theme
- `Dockerfile`, `docker-compose.yml` — Docker setup
- `.github/workflows/docker.yml` — CI: lint → test → build+push to GHCR

## Domain Lifecycle States
UNKNOWN → ACTIVE → EXPIRING_SOON → EXPIRING_CRITICAL → EXPIRED → REDEMPTION → PENDING_DELETE → AVAILABLE

Fast-poll (5min) activates for REDEMPTION and PENDING_DELETE states.
