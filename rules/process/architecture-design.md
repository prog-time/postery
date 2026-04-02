# Architecture Design

> **Context:** Read this file before designing any new feature, refactoring an existing layer, or introducing a new dependency. Always design before implementing.
> **Version:** 1.1

---

## 1. Core Principle

Design first. Code second. Every change must start with identifying affected layers, data flow, and access control implications. Never write code before the design is confirmed.

If design is missing — stop and design.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                      │
│                                                                  │
│  ┌──────────────┐   ┌──────────────────────────────────────┐   │
│  │  REST API    │   │        Starlette-Admin Panel          │   │
│  │  /api/*      │   │        /admin/*                       │   │
│  │              │   │  ┌─────────────┐ ┌─────────────────┐ │   │
│  │ ai_generate  │   │  │  ModelViews │ │  CustomViews    │ │   │
│  │ ai_provider  │   │  │  (list/edit)│ │  (wizards)      │ │   │
│  │ source tests │   │  └─────────────┘ └─────────────────┘ │   │
│  └──────────────┘   └──────────────────────────────────────┘   │
│           │                        │                             │
│           └────────────────────────┘                            │
│                        │                                         │
│              SQLAlchemy ORM (synchronous)                        │
│                        │                                         │
│              SQLite (data/admin.db)                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Background Worker (asyncio task)            │   │
│  │  Polls every 30s → publishes due PostChannel records    │   │
│  │  Calls publisher modules → Telegram / VK / MAX APIs     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Layer Responsibilities

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Entrypoint** | `main.py` | App factory, schema init, migrations, default admin seed, worker startup |
| **Config** | `app/config.py` | `BASE_DIR`, `SECRET_KEY`, template/static paths — no imports from app |
| **Database** | `app/database.py` | Engine, `SessionLocal`, `Base` |
| **Models** | `app/models/` | ORM table definitions, enums, computed properties |
| **REST Routers** | `app/routers/` | FastAPI route handlers; thin wrappers, no business logic |
| **Admin Views** | `app/admin.py` + `app/views/` | Starlette-admin `ModelView` and `CustomView` classes |
| **Auth** | `app/auth.py` | `RoleAuthProvider`, access control mixins, password utilities |
| **Crypto** | `app/crypto.py` | Fernet encrypt/decrypt, mask helper |
| **Custom Fields** | `app/fields.py` | `TokenField` — masked display and password input |
| **Publishers** | `app/publisher/` | Platform-specific async publish functions |
| **Worker** | `app/worker.py` | Background polling loop, orchestrates publishers |
| **Templates** | `admin/templates/` | Jinja2 HTML templates |
| **Statics** | `admin/statics/` | CSS, JS, favicons |

---

## 4. Dependency Rules

- **Models** must not import from routers, views, or publishers
- **Routers** may import from models and database only — no circular imports
- **Admin views** may import from models, database, auth, and views
- **Publishers** must not open DB sessions — all data is passed as arguments
- **Worker** imports publishers and models — it is the only layer that does DB writes after async calls
- **Config** has no imports from the rest of the application

```python
# ✅ Correct — publisher receives pre-loaded data
async def publish(text: str, source, image_paths: list[str]):
    token = source.bot_token  # already loaded, no lazy fetch

# ❌ Incorrect — publisher opens its own DB session
async def publish(source_id: int, ...):
    with SessionLocal() as db:
        source = db.get(TelegramSource, source_id)
```

---

## 5. Pre-Implementation Design Steps

Before writing any code for a new feature:

1. **Read context** — read this file and the relevant domain + database files
2. **Define the problem** — state the goal in 1–3 sentences; list non-goals
3. **Identify affected layers** — which files in which layers will change
4. **Check DB impact** — any new tables or columns? Plan `_migrate()` entry.
5. **Confirm access control** — `SuperadminOnly` or `EditorAccessMixin`?
6. **Assess worker impact** — does the feature produce new `PostChannel` states or `source_type` values?
7. **Check circular imports** — no new import cycles allowed
8. **Propose design** — component diagram or data flow description; do not write code yet

Only after all steps complete → implementation is allowed.

---

## 6. Admin Panel Architecture

**ModelView** — auto-generated CRUD pages for ORM models. Use for list/detail pages.

**CustomView** — fully custom request/response with Jinja2 templates. Use for:
- Multi-step wizards (post wizard, source wizard, AI provider wizard)
- Pages that require test-before-save logic
- Pages that require complex form validation beyond starlette-admin defaults

**Wizard pattern:**
- A `CustomView` handles multi-step forms via URL query params (`?step=N&post_id=N`)
- State is passed via redirect URLs, not server-side session
- The wizard is always separate from the `ModelView` list; creation goes via wizard

**DropDown** — menu grouping; holds a list of views. Used for "Источники" and "Управление".

**Icon rule:** Pass `icon=` to the `ModelView` constructor, not as a class attribute:

```python
# ✅ Correct — icon passed to constructor
admin.add_view(AIProviderView(AIProvider, icon="fa-solid fa-robot"))

# ❌ Incorrect — class-level icon attribute is ignored by starlette-admin
class AIProviderView(SuperadminOnly, ModelView):
    icon = "fa-solid fa-robot"  # has no effect
```

---

## 7. Starlette-Admin Identity Naming

Starlette-admin derives URL slugs from the `name` attribute using a specific slugify function. Do not guess — verify the actual slug by inspecting the generated URLs:

| `name` attribute | Resulting identity slug |
|-----------------|------------------------|
| `telegram_source` | `telegram-source` |
| `vk_source` | `v-k-source` |
| `max_source` | `m-a-x-source` |
| `ai_provider` | `ai-provider` |
| `admin_user` | `admin-user` |

Wizard list redirect URLs (`_LIST_URL` constants) must use the correct slug:

```python
# ✅ Correct
_LIST_URL = "/admin/v-k-source/list"

# ❌ Incorrect — wrong slug, results in 404
_LIST_URL = "/admin/vk_source/list"
```

---

## 8. Async / Sync Boundary

- The FastAPI app and all route handlers are **async**
- SQLAlchemy ORM is **synchronous** (`create_engine`, `SessionLocal`)
- The worker uses asyncio but calls synchronous DB operations in blocking fashion (acceptable for SQLite)
- Do not use `aiosqlite` or async SQLAlchemy — the codebase is intentionally synchronous on the DB layer
- When synchronous blocking work is needed from an async starlette-admin hook, use `anyio.to_thread.run_sync()`

```python
# ✅ Correct — async hook delegates sync DB work to thread
async def after_edit(self, request, obj):
    if obj.is_active:
        await anyio.to_thread.run_sync(lambda: _do_deactivate_others(obj.id))

# ❌ Incorrect — direct synchronous DB call in async hook blocks the event loop
async def after_edit(self, request, obj):
    _do_deactivate_others(obj.id)
```

---

## 9. Migration Architecture

No Alembic. Schema changes follow this exact process:

1. Update `rules/database/schema.md` with the new column
2. Add an entry to `_migrate()` in `main.py`
3. Add the `Mapped` declaration to the SQLAlchemy model
4. Only additive changes: `ADD COLUMN` only

```python
# ✅ Correct — additive migration registered in _migrate()
migrations = [
    ("post_channels", "retry_count", "INTEGER DEFAULT 0"),
]

# ❌ Incorrect — Alembic, DROP, or RENAME
alembic.op.drop_column("posts", "legacy_field")
```

---

## 10. File Upload Architecture

- Uploaded files stored on disk under `BASE_DIR/data/uploads/{post_id}/`
- File paths stored in DB as relative paths from `BASE_DIR`
- Absolute path reconstructed at publish time: `str(BASE_DIR / img.file_path)`
- No CDN, no object storage — local disk only
- Upload directory created on demand with `mkdir(parents=True, exist_ok=True)`

---

## Checklist

- [ ] Affected layers identified and documented before coding
- [ ] No new circular imports introduced
- [ ] DB changes planned: `_migrate()` entry + `schema.md` update
- [ ] Access control level determined (`SuperadminOnly` or `EditorAccessMixin`)
- [ ] Worker impact assessed (new `source_type` or `PostChannel` states)
- [ ] Async/sync boundary respected (no async SQLAlchemy)
- [ ] File upload paths stored relative to `BASE_DIR`
- [ ] `icon=` passed to `ModelView` constructor, not as class attribute
- [ ] Starlette-admin identity slug verified against actual generated URL
