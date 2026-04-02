# Sources Domain Rules

> **Context:** Read this file before adding, modifying, or connecting a publishing source (Telegram, VK, or MAX). Also read before modifying token storage, AI prompts on sources, or the source wizard UI.
> **Version:** 1.1

---

## 1. Core Principle

A source is a configured publishing destination. Every source must store its credentials encrypted and must be tested against the live platform API before being saved. Inactive sources are invisible to the post creation wizard.

---

## 2. What Is This Domain?

A **Source** is a configured publishing destination on a specific platform. There are three source types, each with its own ORM model, database table, admin list view, and wizard:

| Source | Model | Table | Wizard View | List Identity |
|--------|-------|-------|-------------|---------------|
| Telegram | `TelegramSource` | `telegram_sources` | `TelegramSourceWizardView` | `telegram-source` |
| VKontakte | `VKSource` | `vk_sources` | `VKSourceWizardView` | `v-k-source` |
| MAX Messenger | `MAXSource` | `max_sources` | `MAXSourceWizardView` | `m-a-x-source` |

### Key Concepts

| Concept | Description |
|---------|-------------|
| is_active | Controls visibility in post wizard step 2. Inactive = hidden from new posts. |
| EncryptedString | SQLAlchemy type decorator that Fernet-encrypts on write, decrypts on read |
| TokenField | Starlette-admin field: masked in list/detail, password input in form |
| ai_prompt_title | Source-specific system prompt for AI title rewrite |
| ai_prompt_description | Source-specific system prompt for AI description rewrite |
| Connection test | Live API call to validate credentials before saving |

---

## 3. Business Rules

**BR-001** — All credential columns (bot tokens, access tokens, API keys) must use `EncryptedString`. Never use `String` or `Text` for secrets.
_Enforced in:_ `app/models/sources/*.py`

**BR-002** — Credentials must be displayed using `TokenField` in all admin forms and list views. `TokenField` shows a masked value in list/detail and a password input in forms.
_Enforced in:_ `app/admin.py`, `app/fields.py`

**BR-003** — Inactive sources (`is_active=False`) must be excluded from the post wizard step 2 source picker. They remain visible in the admin list view.
_Enforced in:_ `app/views/posts.py @ PostWizardView._get()` step 2 (filters by `is_active=True`)

**BR-004** — Source list views must disable direct creation (`can_create` returns `False`). All new sources are created through the wizard.
_Enforced in:_ `app/admin.py @ TelegramSourceView.can_create()`, etc.

**BR-005** — Source list views must override the edit row action to redirect to the wizard URL, not the default starlette-admin edit form.
_Enforced in:_ `app/admin.py @ row_action_2_edit()`

**BR-006** — When creating a new source, the Save button must remain disabled until the connection test passes. When editing, the Save button is disabled only when a new token value has been entered and not yet tested.
_Enforced in:_ frontend JS in `admin/templates/source/`

**BR-007** — Connection test endpoints must not write anything to the database. They test only.
_Enforced in:_ `app/routers/source.py`

**BR-008** — Connection test endpoints must use a 10-second timeout. On timeout, return `{"ok": false, "error": "Превышено время ожидания"}`.
_Enforced in:_ `app/routers/source.py`

**BR-009** — `ai_prompt_title` and `ai_prompt_description` are source-specific system prompts. They are displayed only in the edit wizard (not the create wizard — the add tab has no AI prompts section).
_Enforced in:_ `app/views/telegram_source.py`, `app/views/vk_source.py`, `app/views/max_source.py`

**BR-010** — When editing a source, if the token input field is left blank, the existing encrypted token must be preserved. Only update the token if a non-empty value is submitted.
_Enforced in:_ `app/views/telegram_source.py @ _post_edit()`, etc.

**BR-011** — The `ai_prompt_title` and `ai_prompt_description` columns were added via `_migrate()` after initial table creation. Never assume they exist without migration running.
_Enforced in:_ `main.py @ _migrate()`

---

## 4. Token Storage

```python
# ✅ Correct — all credential columns use EncryptedString
from app.models.encrypted import EncryptedString

class TelegramSource(Base):
    bot_token: Mapped[str] = mapped_column(EncryptedString, nullable=False)

# ❌ Incorrect — stores credential in plain text
class TelegramSource(Base):
    bot_token: Mapped[str] = mapped_column(String(256), nullable=False)
```

`EncryptedString` transparently encrypts on write and decrypts on read. The application always works with the plain-text value. Legacy plain-text rows are handled gracefully (decryption failure returns the raw value).

---

## 5. Wizard Pattern (Add vs Edit)

### Add (create) wizard
- No `pk` query param
- Single tab: connection parameters (name, token, chat_id / group_id, is_active)
- No AI prompts tab — prompts are only configurable after the source exists

### Edit wizard
- `pk={id}` query param present
- Two sections: parameters tab + AI prompts fields
- Token field: if left blank, existing token is kept; if filled, token is updated and test required

```python
# ✅ Correct — only update token when a new value is submitted
if bot_token:
    source.bot_token = bot_token

# ❌ Incorrect — overwrites with empty string, breaking the encrypted value
source.bot_token = bot_token
```

---

## 6. Connection Test Endpoints

| Platform | Endpoint | Required Fields | Optional Fields |
|----------|----------|-----------------|-----------------|
| Telegram | `POST /api/source/telegram/test` | `bot_token` | `chat_id` |
| VKontakte | `POST /api/source/vk/test` | `access_token`, `group_id` | — |
| MAX | `POST /api/source/max/test` | `bot_token` | `chat_id` |

All return:
```json
{"ok": true, "message": "Подключение успешно (@botname)"}
// or
{"ok": false, "error": "human-readable reason"}
```

---

## 7. Platform-Specific Rules

### Telegram
- `chat_id` accepts `@channel_username` or numeric `-1001234567890`
- `thread_id` is optional — only required for supergroup forum topics
- The bot must be an admin with "Post Messages" permission in the target channel

### VKontakte
- `group_id` is the positive numeric ID (without minus sign)
- Community tokens work for text-only posts but fail photo uploads (VK error 27)
- User access token with `wall`, `photos`, `offline` permissions required for photo uploads
- This limitation is documented in the wizard UI help text

### MAX Messenger
- `chat_id` is the numeric channel/chat ID (stored as string)
- Auth uses `Authorization: Bearer {bot_token}` header
- Validated via `GET https://botapi.max.ru/me`

---

## 8. Starlette-Admin Identity Naming

Starlette-admin slugifies the `name` attribute to generate URL identities. Understand the pattern:

| Class-level `name` | Resulting URL identity |
|--------------------|----------------------|
| `telegram_source` | `telegram-source` |
| `vk_source` | `v-k-source` |
| `max_source` | `m-a-x-source` |
| `ai_provider` | `ai-provider` |

The wizard list redirect URLs must use these exact slugified identities:

```python
# ✅ Correct
_LIST_URL = "/admin/v-k-source/list"   # in app/views/vk_source.py

# ❌ Incorrect — wrong slug, results in 404
_LIST_URL = "/admin/vk-source/list"
```

---

## 9. Adding a New Source Type

Follow these steps in order:

1. Create `app/models/sources/{platform}.py` — ORM model with `EncryptedString` for tokens
2. Create `app/publisher/{platform}.py` — publisher implementing the `publish()` contract
3. Create `app/views/{platform}_source.py` — `CustomView` + `EditorAccessMixin` wizard
4. Create the list `ModelView` in `app/admin.py` with `EditorAccessMixin`; disable `can_create`; redirect edit to wizard
5. Add source to the `DropDown` in `create_admin()`
6. Register `ai_prompt_title` and `ai_prompt_description` in `_migrate()`
7. Add the new `source_type` string to the post wizard step 2 picker and the worker dispatch
8. Add the connection test endpoint to `app/routers/source.py`
9. Update `rules/database/schema.md` and this file

---

## Forbidden Behaviors

- ❌ Using `String` or `Text` for credential columns — always use `EncryptedString`
- ❌ Using `StringField` for credential admin fields — always use `TokenField`
- ❌ Allowing direct creation via list view `can_create` — creation must go through wizard
- ❌ Saving a source without a successful connection test (for new tokens)
- ❌ Storing the raw decrypted token in templates or logs
- ❌ Including inactive sources in the post wizard step 2 picker

---

## Checklist

- [ ] New source model uses `EncryptedString` for all credential columns
- [ ] Admin view uses `TokenField`, not `StringField`, for credential columns
- [ ] `can_create` disabled on list view; creation redirected to wizard
- [ ] Edit wizard preserves existing token when input is blank
- [ ] Source excluded from wizard picker when `is_active=False`
- [ ] `ai_prompt_title` and `ai_prompt_description` added via `_migrate()`
- [ ] Connection test endpoint timeout is 10 seconds
- [ ] Connection test endpoint returns `{"ok": bool, "message" | "error": str}`
- [ ] Connection test endpoint makes no DB writes
- [ ] List URL in wizard uses correct slugified identity (verify starlette-admin's slugify output)
