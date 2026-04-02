# CI/CD Rules

> **Context:** Read this file before shipping any change to a production or staging server, or before modifying the deployment process.
> **Version:** 1.0

---

## 1. Core Principle

_Not applicable — no automated CI/CD pipeline is currently configured. There is no GitHub Actions, GitLab CI, Jenkins, or equivalent pipeline. All deployments are performed manually._

This file documents the current manual deployment process and the standards that any future CI/CD pipeline must meet.

---

## 2. Current Deployment Process

Deployment is manual via `start.sh`:

```bash
# ✅ Current deployment steps
git pull
pip install -r requirements.txt
# restart uvicorn (kill existing process, then:)
uvicorn main:app --host 0.0.0.0 --port 8000
```

The `start.sh` file at the project root wraps the uvicorn start command.

**Rules for manual deployment:**
- Always run `pip install -r requirements.txt` after pulling, in case new dependencies were added
- Never restart the app without verifying the new code starts without import errors
- The background worker starts automatically via the `lifespan` context in `main.py` — no separate process needed

---

## 3. Pre-Deployment Checklist

Before deploying to any non-development environment, verify:

- [ ] `SECRET_KEY` in `app/config.py` is changed from the default `"change-me-in-production"` to a strong random value
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
