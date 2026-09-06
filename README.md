# deckpilotAI backend

FastAPI, SQLAlchemy, Turso/libSQL, Cloudflare R2, and a bounded multi-agent PowerPoint generation pipeline.

## Prerequisites

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/) 0.12+
- Turso and R2 credentials for production; development can use local SQLite and local object storage

## Local setup

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
# Put two independently generated values into JWT_SECRET and KEY_ENCRYPTION_SECRET.
uv sync --extra dev --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Liveness is `GET /api/v1/health`; database readiness is `GET /api/v1/health/ready`. API docs are available at `/docs` outside production.

## Configuration

Production requires `APP_ENV=production`, independent 32+ character `JWT_SECRET` and `KEY_ENCRYPTION_SECRET` values, a paired `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN`, all three R2 connection values, one or more HTTPS `FRONTEND_ORIGIN` values, and explicit `ALLOWED_HOSTS`. Keep `DB_ECHO=false`. Development can override `SQLITE_DATABASE_URL` and `LOCAL_STORAGE_DIR` for isolated runs. AI provider keys are optional; deterministic generation remains available without them.

`FRONTEND_ORIGIN` and `ALLOWED_HOSTS` accept comma-separated values. Outbound AI calls are limited to `AI_PROVIDER_ALLOWED_HOSTS`. Uploads default to 25 MiB and may be bounded with `MAX_UPLOAD_BYTES`.

Never commit `.env`. Changing `KEY_ENCRYPTION_SECRET` requires a planned provider-key re-encryption migration; old ciphertext cannot be recovered with a new key.

## Verification

```powershell
uv run ruff check app tests alembic scripts
uv run mypy app
uv run pytest -q
uv run pip-audit
$env:RUN_LIVE_TESTS='1'; uv run pytest -q tests/test_turso_conn.py tests/test_r2_live.py
```

Live tests use configured development services, write one uniquely named R2 test object, verify it, and remove it.

## Production deployment

Run migrations as a separate release step before starting application replicas:

```powershell
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or build the included image and inject environment variables at runtime:

```powershell
docker build -t deckpilotai-backend .
docker run --rm -p 8000:8000 --env-file .env deckpilotai-backend
```

Terminate with SIGTERM and allow graceful draining. Put the service behind a TLS-terminating reverse proxy, configure trusted forwarded-proxy addresses at the platform layer, and route liveness/readiness separately. Generation tasks currently execute in the API process; use one backend replica or introduce a durable external queue before horizontal scaling or zero-downtime restarts.
