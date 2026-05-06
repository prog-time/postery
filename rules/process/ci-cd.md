# CI/CD Rules

> **Context:** Read this file before shipping any change to a production or staging server, or before modifying the deployment process.
> **Version:** 1.0

---

## 1. Core Principle

_Not applicable — no automated CI/CD pipeline is currently configured. There is no GitHub Actions, GitLab CI, Jenkins, or equivalent pipeline. All deployments are performed manually._

This file documents the current manual deployment process and the standards that any future CI/CD pipeline must meet.

---

## 2. Deployment Processes

### 2.1 Docker (recommended for self-host, production)

Three-command deployment on any machine with Docker and Docker Compose:

```bash
git clone https://github.com/prog-time/postery.git
cp .env.example .env
# Set SECRET_KEY and optionally INITIAL_ADMIN_* in .env
docker compose up -d
```

Update to a new version:

```bash
git pull
docker compose up -d --build
```

**Rules for Docker deployment:**
- `./data/` is bind-mounted into the container — all persistent data lives there on the host
- The worker runs in the same process as FastAPI (via `lifespan asyncio.create_task`) — do not split into a separate `worker` service (SQLite single-writer constraint; on PostgreSQL the constraint relaxes but the deployment shape stays the same)
- Both SQLite and PostgreSQL drivers (`aiosqlite`, `psycopg2-binary`) ship in the default image; switch via `DATABASE_URL` in `.env`. Postgres server itself is not bundled — point at an external instance.
- Heroku-style `postgres://` URLs are auto-normalized to `postgresql://` in `app/database.py` (SQLAlchemy 2.x rejects the legacy scheme).
- `restart: unless-stopped` handles process crashes and server reboots automatically
- Healthcheck: `curl -fsS http://localhost:8000/health` — container reaches `healthy` status ~30 s after start
- `SECRET_KEY` must be set before first start; changing it later makes all DB-encrypted tokens unreadable
- `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` set the first admin's credentials on first start with empty DB; if unset, `admin/admin` is created (change immediately via `/admin` or `python create_superadmin.py`)

### 2.2 Local development (start.sh)

`start.sh` is for local development only and is not included in the Docker image (excluded via `.dockerignore`).

```bash
pip install -r requirements.txt
./start.sh
```

**Rules for local deployment:**
- Always run `pip install -r requirements.txt` after pulling new changes
- Never restart the app without verifying the new code starts without import errors
- The background worker starts automatically via the `lifespan` context in `main.py` — no separate process needed

---

## 3. Pre-Deployment Checklist

Before deploying to any non-development environment, verify:

**Docker:**
- [ ] `SECRET_KEY` in `.env` is set to a strong random value (never the default placeholder)
- [ ] `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD` are set, or admin password changed after first start
- [ ] `./data/` volume is bind-mounted correctly in `docker-compose.yml`
- [ ] Healthcheck passes (`docker compose ps` shows `healthy` status)
- [ ] `docker compose logs` shows no startup errors

**Local (start.sh):**
- [ ] `SECRET_KEY` in `.env` is changed from the default
- [ ] Default `admin` / `admin` credentials have been changed via `create_superadmin.py`
- [ ] `data/` directory exists and is writable (for `admin.db` and uploaded images)
- [ ] `requirements.txt` is up to date with all new dependencies
- [ ] No debug code or print statements are present in application code
- [ ] Migrations in `_migrate()` are compatible with the production database schema

---

## 4. Database Migration Safety

Because there is no Alembic and no rollback mechanism, migrations are irreversible once applied:

- Only additive `ADD COLUMN` migrations are safe to apply in production
- Never `DROP COLUMN`, `RENAME COLUMN`, or `RENAME TABLE` via `_migrate()`
- If a destructive change is needed, it must be done manually with a backup first
- Back up `data/admin.db` before any deployment that includes schema changes

---

## 5. Future CI/CD Standards

When a CI/CD pipeline is added, it must include these stages:

**Stage 1 — Lint and type-check**
- Run `ruff` or `flake8` for linting
- Run `mypy` for type checking (if type stubs are added)
- Fail the pipeline on any error

**Stage 2 — Tests**
- Run the full test suite (once one exists — see `testing-strategy.md`)
- Fail the pipeline if any test fails

**Stage 3 — Deploy to staging**
- Only run after tests pass
- Deploy to a staging environment
- Run smoke tests

**Stage 4 — Deploy to production**
- Require manual approval
- Never deploy automatically to production

```yaml
# ✅ Correct future pipeline structure
jobs:
  test:
    steps:
      - run: pip install -r requirements.txt
      - run: pytest

  deploy-staging:
    needs: test
    steps:
      - run: ./deploy-staging.sh

  deploy-production:
    needs: deploy-staging
    environment: production   # requires manual approval
    steps:
      - run: ./deploy-production.sh
```

```yaml
# ❌ Incorrect — deploy without tests
jobs:
  deploy:
    steps:
      - run: ./deploy-production.sh
```

---

## 6. AI-Specific CI/CD Rules

When an AI agent proposes pipeline changes:
- Never commit pipeline changes that skip tests
- Never hardcode secrets in pipeline YAML — use environment variables or secrets management
- Never push directly to `main` or `master` branches
- Always validate YAML syntax before committing

---

## Checklist

- [ ] `SECRET_KEY` changed from default before deployment
- [ ] Default admin credentials changed
- [ ] `data/` directory exists and is writable
- [ ] `pip install -r requirements.txt` run after pull
- [ ] Database backed up before schema-changing deployment
- [ ] No debug code committed
- [ ] Future CI/CD pipeline must pass tests before deploying
