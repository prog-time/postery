# Observability Rules

> **Context:** Read this file before adding new code paths, modifying the worker, or adding new publisher integrations. Every significant operation must be logged.
> **Version:** 1.1

---

## 1. Core Principle

If you cannot observe it, you cannot operate it. Every failure must produce a log entry. Silent failures are forbidden.

---

## 2. Logging Configuration

The application uses Python's standard `logging` module, configured once in `main.py` at startup:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
```

All logs go to stdout. There is no file-based logging or external log aggregation currently configured.

---

## 3. Logger Naming Convention

Use module-scoped loggers named after the module. Never use the root logger.

```python
# ✅ Correct — module-scoped logger
import logging
log = logging.getLogger("worker")           # in app/worker.py
log = logging.getLogger("publisher.vk")    # in app/publisher/vk.py
log = logging.getLogger("publisher.max")   # in app/publisher/max_messenger.py

# ❌ Incorrect — root logger, no context
import logging
logging.info("something happened")
```

---

## 4. Log Level Conventions

| Level | Use |
|-------|-----|
| `DEBUG` | Detailed diagnostics for development only (e.g., raw API response bodies) |
| `INFO` | Normal business events: worker started, channel publishing, upload success |
| `WARNING` | Recoverable non-fatal issues: VK group token falls back to text-only |
| `ERROR` | Failures that affect functionality: channel publish failed |
| `EXCEPTION` | Same as error but includes full traceback — use inside `except` blocks |

---

## 5. Worker Logging Requirements

The worker must log at these exact points:

| Event | Level | Message pattern |
|-------|-------|-----------------|
| Worker starts | INFO | `"Worker started (poll every %ds)"` |
| Worker iteration fails | EXCEPTION | `"Worker iteration failed"` (includes traceback) |
| Channel publish starts | INFO | `"Publishing channel %d → %s / %s"` (id, source_type, source.name) |
| Images to attach | INFO | `"Channel %d: %d image(s) to attach"` |
| Source not found | WARNING | `"Channel %d: source not found"` |
| Publish success | INFO | `"Channel %d published successfully"` |
| Publish failure | ERROR | `"Channel %d failed: %s"` |

```python
# ✅ Correct — exception logged with full traceback via log.exception()
try:
    await _process_due_channels()
except Exception:
    log.exception("Worker iteration failed")

# ❌ Incorrect — silent swallow, no visibility into failures
try:
    await _process_due_channels()
except Exception:
    pass
```

---

## 6. Publisher Logging Requirements

Each publisher module (`telegram.py`, `vk.py`, `max_messenger.py`) must log:

| Event | Level | Content |
|-------|-------|---------|
| Upload step success | INFO | Upload URL obtained or photo/message token |
| API response on success | INFO | Relevant ID (message ID, post ID) |
| Fallback behavior triggered | WARNING | Reason (e.g., VK error 27 → text-only) |

```python
# ✅ Correct — VK fallback logged at WARNING level with context
log.warning(
    "Group token cannot upload photos (error 27). "
    "Use a user access token. Publishing text only."
)

# ❌ Incorrect — silent fallback, no visibility into degraded behavior
pass
```

---

## 7. Error Logging Rules

- Use `log.exception("message")` inside `except` blocks to capture the full traceback
- Use `log.error("message %s", detail)` for expected failure states without an exception object
- Never swallow exceptions silently — always log them at minimum with `log.exception()`
- Truncate error strings stored in `channel.error_message` to 500 characters: `str(e)[:500]`

---

## 8. Error Message Storage

Publisher errors are stored in `post_channels.error_message` (TEXT column). This is the primary mechanism for surfacing publish failures in the admin post list view.

```python
# ✅ Correct — error truncated before storage
channel.error_message = error[:500] if error else None

# ❌ Incorrect — unbounded error string may exceed column capacity
channel.error_message = str(full_traceback)
```

---

## 9. Health Check

The `GET /` endpoint returns `{"status": "ok"}` and serves as a minimal liveness probe. No DB access.

If adding a richer health endpoint in the future:
- Mount it at `GET /health` with no auth requirement
- Return HTTP 200 with `{"status": "ok", "db": "ok"}` after a trivial DB query

---

## 10. Metrics

_Not applicable — no metrics collection system is currently configured. No Prometheus, Datadog, or similar integration exists. If adding metrics, document them in this section._

---

## 11. Tracing

_Not applicable — no distributed tracing is configured. The application is a single process._

---

## Checklist

- [ ] New modules define `log = logging.getLogger("module.name")`
- [ ] Worker events logged at correct levels per the table in Section 5
- [ ] Publisher fallbacks (e.g., VK text-only) logged at WARNING level
- [ ] No silent `except: pass` blocks
- [ ] `log.exception()` used inside except blocks (includes traceback)
- [ ] Publisher errors stored in `channel.error_message`, truncated to 500 chars
- [ ] `logging.basicConfig(...)` in `main.py` not duplicated in other modules
