# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FormBot automates form submissions on external websites using AI-powered form detection (Ollama), multi-page flows, CAPTCHA/2FA manual intervention via noVNC, and scheduled execution.

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
pytest tests/test_analyzer.py -v             # Run single test file
pytest tests/ -k "test_name" -v              # Run single test by name
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
    ↓ Pusher broadcast                      Ollama (LLM) :11434
    ↓                                              ↓
WebSocket (Soketi) :6001 ←── Broadcaster ←── AI form analysis
    ↓
Frontend (real-time updates)
```

- **Backend → Scraper**: HTTP calls via `ScraperClient` (600s timeout). All heavy work (Playwright browsing, Ollama AI calls) happens in the scraper.
- **Async processing**: Backend dispatches jobs (`AnalyzeUrlJob`, `ExecuteTaskJob`, etc.) to Redis queue. Queue worker picks them up and calls the scraper.
- **Real-time updates**: Scraper broadcasts events via Pusher SDK → Soketi → Frontend WebSocket. Events include `AiThinking` (streaming tokens), `TaskStatusChanged`, execution step progress.
- **VNC**: Scraper runs Xvfb + x11vnc + websockify for CAPTCHA/2FA manual intervention. Token-based routing on port 6080.

### Key Services

**Scraper** (`packages/scraper/app/services/`):
- `FormAnalyzer` — Cleans HTML (strips scripts/styles/SVG/comments, keeps only relevant attributes), sends to Ollama, applies heuristic override for login detection (no password field = not a login page)
- `OllamaClient` — Ollama API wrapper. Uses `temperature: 0` for deterministic results, default model `llama3.1:8b`
- `TaskExecutor` — Playwright-based form filling with stealth mode, multi-step flows, CAPTCHA/2FA via VNC
- `LoginAnalyzer` — Login flow with optional VNC, then analyzes target page
- `VNCManager` — Manages Xvfb/x11vnc display sessions with token-based websockify routing

**Backend** (`packages/backend/app/`):
- `Services/ScraperClient` — HTTP client to Python scraper
- `Services/CryptoService` — Encrypts sensitive form field values
- `Jobs/` — Async queue jobs for analysis, execution, validation
- `Events/` — Pusher broadcast events for real-time UI updates

### Database (PostgreSQL)

Key models with UUID primary keys:
- `Task` → has many `FormDefinition` (ordered steps: login → intermediate → target)
- `FormDefinition` → has many `FormField` (individual fields with CSS selectors, sensitive fields encrypted)
- `Task` → has many `ExecutionLog` (status, steps_log JSON array, VNC session tracking)

### Frontend Routing

- `/dashboard` — Task overview
- `/tasks/new`, `/tasks/:id/edit` — Multi-step task wizard (URL & Analyze → Review Forms → Fill Fields → Schedule → Options)
- `/tasks/:id` — Task detail with execution history
- `/logs` — Execution logs
- `/settings` — App settings

### WebSocket Channels

- `private-tasks.{userId}` — Task status changes
- `private-execution.{executionId}` — Step-by-step execution progress
- `private-analysis.{analysisId}` — AI thinking tokens, analysis completion, VNC required

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
| Ollama | ollama:11434 | localhost:11434 |
| Test Site | host.docker.internal:3000 | localhost:3000 |

## Test Maintenance Policy

After every impactful change (new feature, bug fix, refactor, API change, model/config change), you MUST:

1. **Run the existing tests** for the affected package(s) to check for breakage.
2. **Update tests** that fail due to the change (e.g. changed defaults, renamed functions, new parameters).
3. **Create new tests** for any new functionality, endpoint, service method, or behavior.
4. **Delete tests** that are no longer relevant (removed features, deprecated code).
5. **Align assertions** with the new behavior (e.g. if a default model changes from `llama3.2:1b` to `llama3.1:8b`, update the corresponding assertion).

Do this **before committing**. A commit with broken tests is not acceptable.

## Important Patterns

- The scraper uses `host.docker.internal` to access the test-site from inside Docker.
- Sensitive form field values are encrypted at rest via `CryptoService` / `ENCRYPTION_KEY`.
- The `FormAnalyzer._clean_html()` method strips noise from HTML before sending to Ollama — always apply cleaning before the 50KB truncation.
- The login heuristic (`_detect_login_heuristic`) checks for password inputs in the live DOM and overrides AI's `page_requires_login` to `false` if none are found.
- Ollama prompts live in `packages/scraper/app/prompts/` — changes here affect AI behavior directly.
