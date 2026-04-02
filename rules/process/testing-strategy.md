# Testing Strategy Rules

> **Context:** Read this file before writing any code that affects behavior, APIs, database, or business logic. Understand what is expected before marking a task done.
> **Version:** 1.0

---

## 1. Current State

_Not applicable — no test suite currently exists. There is no `tests/` directory and no test runner configured in the project._

This file documents the full recommended testing strategy so that when tests are introduced, they follow the correct principles from the start.

---

## 2. Core Principle

Test everything that can fail, and fail fast.

- Do not mock the database — use a real SQLite test database (a separate `data/test.db` file)
- Integration tests over unit tests for this codebase (most logic is I/O and ORM interaction)
- Publisher tests should use `httpx.MockTransport` or `respx` to mock HTTP, not mock the database
- Every new business rule added to a domain file must have a corresponding test

---

## 3. Recommended Test Structure

```
tests/
├─ conftest.py              <- shared fixtures: test DB engine, SessionLocal, client
├─ test_worker.py           <- worker poll logic, channel selection, status transitions
├─ test_publishers.py       <- per-platform publish formatting and error handling
├─ test_wizard_posts.py     <- step 1/2/3 POST handlers, validation rules
├─ test_wizard_sources.py   <- source create/edit wizard, token preservation
├─ test_ai_generate.py      <- /api/ai/generate endpoint, provider selection, prompt injection
├─ test_api_source.py       <- /api/source/*/test endpoints, timeout handling
└─ test_auth.py             <- login, session, role access, is_active guard
```

---

## 4. Test Database Rules

- Use a separate SQLite file for tests (e.g., `data/test.db` or in-memory `:memory:`)
- Reset the database between test sessions (drop and recreate all tables)
- Use factories to create test records — never rely on the default seeded `admin` user
- Do not run `_migrate()` in tests — create tables directly from `Base.metadata.create_all()`

```python
# ✅ Correct — real SQLite, reset per session
@pytest.fixture(scope="session")
def engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=e)
    return e

# ❌ Incorrect — mocking the ORM bypasses real SQLAlchemy behavior
db = MagicMock()
db.query.return_value.filter_by.return_value.first.return_value = fake_provider
```

---

## 5. Worker Tests

The worker contains the most critical business logic. Test these scenarios:

- A `pending` channel with `scheduled_at = None` is published immediately
- A `pending` channel with `scheduled_at` in the past is published
- A `pending` channel with `scheduled_at` in the future is NOT published
- A `draft` post channel is skipped (not published)
- When the last channel of a post is published, `post.status` becomes `published`
- A failed channel sets `status = failed` and stores `error_message`
- A failed channel does not affect other channels of the same post

```python
# ✅ Correct test name — describes the invariant
async def test_worker_skips_future_scheduled_channel():
    ...

# ❌ Incorrect test name — meaningless
async def test_worker_1():
    ...
```

---

## 6. Publisher Tests

Publisher functions receive pre-loaded data. Test with mocked HTTP:

- Correct message body structure per platform
- Correct `parse_mode=HTML` for Telegram, plain text for VK/MAX
- Image count capped at 10
- `sendMessage` / `sendPhoto` / `sendMediaGroup` selection logic for Telegram
- VK error 27 triggers text-only fallback and returns `(True, None)` not `(False, ...)`
- `publish()` returns `(False, "error")` on HTTP error — never raises

---

## 7. Wizard Tests

Test the HTTP POST handlers directly using FastAPI's `TestClient`:

- Step 1: blank title returns form with error
- Step 1: valid title creates post and redirects to step 2
- Step 2: no sources selected returns form with error
- Step 2: sources selected creates PostChannel records and redirects to step 3
- Step 3: saves channel overrides and advances to next channel
- Step 3: final channel sets `post.status = ready`
- Source wizard edit: blank token preserves existing encrypted token

---

## 8. AI Generation Tests

- No active provider → `{"ok": false, "error": "Нет активного AI провайдера"}`
- Empty text → `{"ok": false, "error": "Поле пустое — нечего обрабатывать"}`
- Missing source → generation proceeds without system message
- `field = "title"` → reads `ai_prompt_title` from source
- `field = "description"` → reads `ai_prompt_description` from source
- Provider API timeout → `{"ok": false, "error": "Превышено время ожидания"}`

---

## 9. Forbidden Test Patterns

- ❌ Mocking `SessionLocal` or SQLAlchemy ORM calls — use a real test DB
- ❌ Tests that depend on timing (`time.sleep()`) unless strictly necessary
- ❌ Hardcoded IDs that assume a specific insert order
- ❌ Skipping tests with `pytest.skip()` without a documented reason
- ❌ Tests without assertions (no-op tests that always pass)

---

## 10. CI Integration

When tests are added, they must:
- Run automatically on every push (once a CI pipeline is added — see `ci-cd.md`)
- Use the `pytest` framework
- Pass completely before any merge to the main branch

---

## Checklist

- [ ] New business rule in domain file → test case added for that rule
- [ ] Worker logic changes → worker test cases updated
- [ ] Publisher changes → publisher test cases updated
- [ ] Wizard POST handler changes → wizard test cases updated
- [ ] API endpoint changes → API test cases updated
- [ ] Tests use real SQLite, not mocked ORM
- [ ] Test names describe the behavior being tested
- [ ] No silent assertions or no-op tests
