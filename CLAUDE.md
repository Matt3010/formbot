# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FormBot automates form submissions on external websites using a manual VNC-based field selection editor, multi-step flows, manual intervention via noVNC, and scheduled execution.

## Common Commands

### Docker (primary workflow)
```bash
docker compose up --build                    # Full stack startup
docker compose build scraper queue-worker    # Rebuild after scraper/backend changes
docker compose up -d scraper queue-worker    # Restart specific services
docker compose logs scraper --tail=50        # View service logs
docker compose --profile dev up -d test-site # Start test site (localhost:3000)
```

### Backend (Laravel 11) — `packages/backend/`
```bash
cd packages/backend
composer install
vendor/bin/phpunit                           # Run all tests
vendor/bin/phpunit --filter=TestClassName     # Run single test
php artisan migrate                          # Run migrations
php artisan queue:work redis --tries=3       # Start queue worker locally
```

### Scraper (Python FastAPI) — `packages/scraper/`
```bash
cd packages/scraper
pip install -r requirements.txt
pip install pytest pytest-asyncio
pytest tests/ -v                             # Run all tests
pytest tests/test_editing_api.py -v          # Run single test file
pytest tests/ -k "test_name" -v             # Run single test by name
```

### Frontend (Angular 19) — `packages/frontend/`
```bash
cd packages/frontend
npm install
npm start                                    # Dev server with proxy (localhost:4200)
npm run build                                # Production build
npm test                                     # Run tests
```

## Architecture

### Service Communication

```
Frontend (Angular) :4200
    ↓ HTTP (REST API)
Backend (Laravel) :8000
    ↓ Redis Queue (async jobs)
Queue Worker (Laravel) → ScraperClient HTTP → Scraper (FastAPI) :9000
    ↓                                              ↓
    ↓ Pusher broadcast                      Playwright (headed browser)
    ↓                                              ↓
WebSocket (Soketi) :6001 ←── Broadcaster ←── VNC field highlighting
    ↓
Frontend (real-time updates)
```

- **Backend → Scraper**: HTTP calls via `ScraperClient` (600s timeout). All heavy work (Playwright browsing, VNC sessions) happens in the scraper.
- **Async processing**: Backend dispatches jobs (`ExecuteTaskJob`, etc.) to Redis queue. Queue worker picks them up and calls the scraper.
- **Real-time updates**: Scraper broadcasts events via Pusher SDK → Soketi → Frontend WebSocket. Events include `HighlightingReady`, `FieldSelected`, `FieldAdded`, `TaskStatusChanged`, execution step progress.
- **VNC**: Scraper runs Xvfb + x11vnc + websockify for manual field selection and manual intervention. Token-based routing on port 6080.

### Key Services

**Scraper** (`packages/scraper/app/services/`):
- `TaskExecutor` — Playwright-based form filling with stealth mode, multi-step flows, manual intervention via VNC
- `FieldHighlighter` — Injects highlight.js into VNC browser pages for interactive field selection (view/select/add/remove modes)
- `HighlighterRegistry` — Singleton managing active VNC editing sessions
- `VNCManager` — Manages Xvfb/x11vnc display sessions with token-based websockify routing

**Backend** (`packages/backend/app/`):
- `Services/ScraperClient` — HTTP client to Python scraper
- `Services/CryptoService` — Encrypts sensitive form field values
- `Jobs/` — Async queue jobs for execution, validation
- `Events/` — Pusher broadcast events for real-time UI updates

### Database (PostgreSQL)

Key models with UUID primary keys:
- `Task` → has many `FormDefinition` (ordered steps: login → intermediate → target)
- `FormDefinition` → has many `FormField` (individual fields with CSS selectors, sensitive fields encrypted)
- `Task` → has many `ExecutionLog` (status, steps_log JSON array, VNC session tracking)

### Frontend Routing

- `/dashboard` — Task overview
- `/tasks/new`, `/tasks/:id/edit` — Multi-step task wizard (URL & Open Editor → Configure Forms via VNC → Schedule → Options)
- `/tasks/:id` — Task detail with execution history
- `/logs` — Execution logs
- `/settings` — App settings

### WebSocket Channels

- `private-tasks.{userId}` — Task status changes
- `private-execution.{executionId}` — Step-by-step execution progress
- `private-analysis.{taskId}` — VNC highlighting ready, field selection during form editing

## Service URLs (Development)

| Service | Internal (Docker) | External (Host) |
|---------|-------------------|-----------------|
| Frontend | — | localhost:4200 |
| Backend API | backend:8000 | localhost:8000/api |
| Scraper | scraper:9000 | localhost:9001 |
| WebSocket | websocket:6001 | localhost:6001 |
| noVNC | scraper:6080 | localhost:6080 |
| PostgreSQL | db:5432 | localhost:5432 |
| Redis | redis:6379 | localhost:6379 |
| Test Site | host.docker.internal:3000 | localhost:3000 |

## Deployment

### Production Deployment

For production deployment with public accessibility, SSL/TLS, and proper security configuration, see **[DEPLOYMENT.md](DEPLOYMENT.md)** for comprehensive setup instructions.

### Public URL Configuration

FormBot uses environment variables to configure public-facing URLs for external access:

**MinIO Public URLs** (for screenshot access):
- `MINIO_ENDPOINT` — Internal Docker endpoint (e.g., `http://minio:9000`)
- `MINIO_PUBLIC_URL` — Public URL for presigned screenshot URLs (e.g., `https://minio.yourdomain.com` or `http://your-ip:9002`)
- Defaults to `MINIO_ENDPOINT` if not set (backward compatible)

**VNC Public URLs** (for VNC session access):
- `NOVNC_PUBLIC_HOST` — Public hostname (e.g., `vnc.yourdomain.com` or `your-ip`)
- `NOVNC_PUBLIC_PORT` — Public port (e.g., `6080` or empty for default https port)
- `NOVNC_PUBLIC_SCHEME` — Protocol scheme (`http` or `https`)
- Defaults to `localhost:6080` with `http` if not set (backward compatible)

**Configuration Examples:**

Development (default):
```bash
MINIO_PUBLIC_URL=http://localhost:9002
NOVNC_PUBLIC_HOST=localhost
NOVNC_PUBLIC_PORT=6080
NOVNC_PUBLIC_SCHEME=http
```

Production with domain:
```bash
MINIO_PUBLIC_URL=https://minio.yourdomain.com
NOVNC_PUBLIC_HOST=vnc.yourdomain.com
NOVNC_PUBLIC_PORT=  # Empty for default https port 443
NOVNC_PUBLIC_SCHEME=https
```

Production with IP:
```bash
MINIO_PUBLIC_URL=http://203.0.113.10:9002
NOVNC_PUBLIC_HOST=203.0.113.10
NOVNC_PUBLIC_PORT=6080
NOVNC_PUBLIC_SCHEME=http
```

## Test Maintenance Policy

After every impactful change (new feature, bug fix, refactor, API change, model/config change), you MUST:

1. **Run the existing tests** for the affected package(s) to check for breakage.
2. **Update tests** that fail due to the change (e.g. changed defaults, renamed functions, new parameters).
3. **Create new tests** for any new functionality, endpoint, service method, or behavior.
4. **Delete tests** that are no longer relevant (removed features, deprecated code).
5. **Align assertions** with the new behavior.

Do this **before committing**. A commit with broken tests is not acceptable.

## Important Patterns

- **WebSocket over polling**: Always prefer WebSocket (Pusher/Soketi) for real-time UI updates instead of HTTP polling. The infrastructure is already in place (`WebSocketService`, Soketi, private channels). Use polling only as a last resort when WebSocket would be overkill (e.g. a one-off data fetch with no live updates needed).
- The scraper uses `host.docker.internal` to access the test-site from inside Docker.
- Sensitive form field values are encrypted at rest via `CryptoService` / `ENCRYPTION_KEY`.
- Field selection is fully manual via the VNC editor — no AI detection. Users click on fields in the live browser to add them.
- Manual intervention (CAPTCHA/2FA/human verification) is handled via the `human_breakpoint` flag. When set, the executor pauses and opens VNC for manual user action before continuing.

## E2E Verification

After rebuilding (`docker compose up --build -d`) and completing an implementation, use the `/playwriter` skill to test the changes end-to-end in the browser. This ensures the full stack works correctly before committing.
