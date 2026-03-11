# Domani

> Domain expiration monitoring and snagging tool — self-hosted, Docker-ready.

Domani watches domain names and alerts you when they're about to expire or become available for registration. Whether you're protecting domains you own or waiting to snag one as it drops, Domani keeps you ahead of the clock.

![Dashboard](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
[![Build and Push Docker Image](https://github.com/maygoo23/Domani/actions/workflows/docker.yml/badge.svg)](https://github.com/maygoo23/Domani/actions/workflows/docker.yml)

---

## Features

- **Domain lifecycle tracking** — monitors all 9 lifecycle states from Active through Pending Delete to Available
- **Smart alerting** — configurable email (SMTP) and webhook notifications per domain, triggered on the transitions that matter to you
- **Snagging mode** — when a target domain enters Pending Delete or becomes available, Domani surfaces direct links to registrar backorder services and notifies you immediately
- **Adaptive polling** — standard 6-hour check intervals automatically switch to 5-minute fast-poll when a domain enters a critical phase
- **Event log** — full audit trail of every WHOIS check, status change, and alert sent
- **Clean web UI** — dark-themed dashboard with live search/filter, no JavaScript framework required
- **Self-hosted** — your data stays on your own machine; runs entirely in a single Docker container

---

## Screenshots

| Dashboard | Domain Detail |
|-----------|--------------|
| Live domain table with status badges, expiry countdowns, and tag filtering | Full WHOIS data, snagging panel with registrar links, event log, and alert config |

---

## Quick Start

### Docker (recommended)

```bash
docker run -d \
  -p 8000:8000 \
  -v domani_data:/data \
  -e SECRET_KEY=your-secret-here \
  --name domani \
  --restart unless-stopped \
  ghcr.io/maygoo23/domani:latest
```

Open **http://localhost:8000** and start adding domains.

### Docker Compose

```bash
git clone https://github.com/maygoo23/Domani.git
cd Domani
cp .env.example .env   # edit as needed
docker compose up -d
```

### Local Development

**Requirements:** Python 3.12+

```bash
git clone https://github.com/maygoo23/Domani.git
cd Domani
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # edit DATABASE_URL to a local path
uvicorn app.main:app --reload
```

---

## Configuration

All configuration is done via environment variables (or a `.env` file). The most important settings can also be managed through the **Settings** page in the web UI.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(random)* | Session signing key — set a fixed value in production |
| `DATABASE_URL` | `sqlite:////data/domani.db` | SQLAlchemy database URL |
| `DEFAULT_CHECK_INTERVAL_HOURS` | `6` | How often to poll WHOIS for each domain |
| `FAST_POLL_INTERVAL_MINUTES` | `5` | Poll interval for domains in Redemption or Pending Delete |
| `EXPIRING_SOON_DAYS` | `30` | Days before expiry to mark a domain as *Expiring Soon* |
| `EXPIRING_CRITICAL_DAYS` | `7` | Days before expiry to mark a domain as *Critical* |
| `SMTP_HOST` | *(empty)* | SMTP server hostname for email alerts |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` | *(empty)* | SMTP username |
| `SMTP_PASSWORD` | *(empty)* | SMTP password |
| `SMTP_FROM` | *(empty)* | Sender address for alert emails |
| `SMTP_TLS` | `true` | Use STARTTLS |

See [`.env.example`](.env.example) for the full list.

---

## Domain Lifecycle

Domani tracks every stage of a domain's lifecycle and fires alerts on configurable transitions:

```
ACTIVE → EXPIRING SOON → EXPIRING CRITICAL → EXPIRED
                                                 ↓
                                           REDEMPTION PERIOD (~30-45 days)
                                                 ↓
                                           PENDING DELETE (~5 days)
                                                 ↓
                                            AVAILABLE ← register here
```

When a domain enters **Redemption** or **Pending Delete**, Domani automatically switches to 5-minute polling and surfaces direct links to registrar backorder services (Namecheap, Porkbun, Cloudflare, GoDaddy, Dynadot, SnapNames).

> **Note:** The exact moment a domain drops varies by registry. A registrar backorder service gives you the best chance of catching a high-demand domain.

---

## Alerts

Alerts are configured per domain and support two delivery methods:

### Email
Uses any standard SMTP server. Configure credentials once in Settings, then add email alert configs to individual domains.

### Webhooks
POST requests with a JSON payload to any URL. Optionally sign requests with HMAC-SHA256 for verification.

**Payload example:**
```json
{
  "domain": "example.com",
  "old_status": "redemption",
  "new_status": "pending_delete",
  "expires_at": "2024-03-15T00:00:00+00:00",
  "days_until_expiry": -35,
  "registrar": "Namecheap Inc.",
  "timestamp": "2024-03-10T12:34:56+00:00"
}
```

**Signature verification** (when a webhook secret is set):
```python
import hmac, hashlib

def verify(secret: str, payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Templates | Jinja2 + [HTMX](https://htmx.org/) |
| Database | SQLite + [SQLAlchemy](https://www.sqlalchemy.org/) |
| Scheduler | [APScheduler](https://apscheduler.readthedocs.io/) |
| WHOIS | [python-whois](https://pypi.org/project/python-whois/) |
| Email | [aiosmtplib](https://aiosmtplib.readthedocs.io/) |
| UI | [Bootstrap 5](https://getbootstrap.com/) dark theme + [Font Awesome](https://fontawesome.com/) |
| Container | Docker (single worker, SQLite volume) |

---

## Development

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check app/

# Run with auto-reload
uvicorn app.main:app --reload
```

### Project Structure

```
app/
├── main.py                  # FastAPI app factory and lifespan
├── config.py                # Settings via pydantic-settings
├── database.py              # SQLAlchemy engine + session
├── models/                  # ORM models (Domain, AlertConfig, DomainEvent, AppSetting)
├── schemas/                 # Pydantic request/response schemas
├── routers/                 # Route handlers (pages, domains, alerts, settings)
├── services/
│   ├── whois_service.py     # WHOIS lookups with retry and rate limiting
│   ├── domain_lifecycle.py  # Status state machine
│   ├── alert_service.py     # Email and webhook dispatch
│   └── scheduler_service.py # APScheduler job management
└── templates/               # Jinja2 HTML templates
```

---

## Deployment Notes

- **Single worker only** — APScheduler runs in-process; do not use multiple uvicorn workers. For horizontal scaling, move the scheduler to a dedicated worker container with a shared job store.
- **Data persistence** — mount a named volume at `/data` to persist the SQLite database across container restarts.
- **Reverse proxy** — place behind nginx or Caddy for TLS termination. The app respects `X-Forwarded-For` headers.
- **No authentication** — Domani v0.1 is designed for single-user, self-hosted use. Place it behind a VPN or add HTTP Basic Auth at the reverse proxy level if exposing to the internet.

---

## Roadmap

- [ ] Built-in authentication (username/password)
- [ ] Bulk domain import (CSV)
- [ ] Pushover / Slack / Telegram notification channels
- [ ] Domain drop time estimation per TLD
- [ ] Public REST API with token authentication
- [ ] Multi-user support

---

## License

MIT — see [LICENSE](LICENSE) for details.
