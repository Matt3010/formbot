![Tests](https://github.com/matt3010/formbot/actions/workflows/tests.yml/badge.svg)

# FormBot

Web application to automate form submissions on external websites, with manual visual form configuration, multi-page flows, CAPTCHA/2FA manual intervention via noVNC, and scheduled execution.

## Stack

| Component | Technology |
|---|---|
| Frontend | Angular 19 (standalone, CSR) |
| Backend | Laravel 11 + Passport OAuth2 |
| Scraper | Python 3.12 + FastAPI + Playwright |
| Database | PostgreSQL 16 |
| Queue | Redis + Laravel Queue |
| WebSocket | Soketi (Pusher protocol) |
| VNC | noVNC + Xvfb |
| Containers | Docker Compose |

## Quick Start

```bash
cp .env.example .env
# Edit .env with your values, then:
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:4200 |
| Backend API | http://localhost:8000/api |
| noVNC | http://localhost:6080 |

## Running Tests

### Laravel (Backend)

```bash
cd packages/backend
composer install
vendor/bin/phpunit
```

### Python (Scraper)

```bash
cd packages/scraper
pip install -r requirements.txt
pip install pytest pytest-asyncio
pytest tests/ -v
```

## License

MIT
