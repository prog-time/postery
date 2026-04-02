# Security Rules

> **Context:** Read this file before modifying authentication logic, token storage, session handling, role-based access, password handling, or any feature that touches user input or external API credentials.
> **Version:** 1.0

---

## 1. Core Principle

Security is not optional or deferred. Every credential must be encrypted at rest. Every route must have explicit access control. Never trust generated code blindly on security-sensitive paths.

---

## 2. Credential Encryption

All sensitive string values (bot tokens, API keys, access tokens) must be stored using `EncryptedString`:

```python
# ✅ Correct — Fernet-encrypted at rest
from app.models.encrypted import EncryptedString

class TelegramSource(Base):
    bot_token: Mapped[str] = mapped_column(EncryptedString, nullable=False)

# ❌ Incorrect — token stored in plain text in the database
class TelegramSource(Base):
    bot_token: Mapped[str] = mapped_column(String(256), nullable=False)
```

`EncryptedString` uses Fernet (AES-128-CBC + HMAC). The encryption key is derived from `SECRET_KEY` via SHA-256.

**Rules:**
- Every new credential column must use `EncryptedString`
- Never use `String`, `Text`, or `VARCHAR` for tokens, keys, or passwords
- Legacy plain-text values in old rows are returned as-is (graceful fallback) — this is the only acceptable exception

---

## 3. SECRET_KEY

The `SECRET_KEY` in `app/config.py` is the root of the encryption key derivation:

```python
# app/config.py (development default — MUST change for production)
SECRET_KEY = "change-me-in-production"
```

**Rules:**
- Change `SECRET_KEY` before deploying to any non-development environment
- Use a minimum 32-character random string (e.g., `secrets.token_hex(32)`)
- If `SECRET_KEY` changes in production, all existing encrypted values in the database become unreadable — never rotate without a migration plan
- Never commit `SECRET_KEY` to version control as a real value

---

## 4. Password Hashing

```python
# ✅ Correct — bcrypt via the project helper functions
from app.auth import hash_password, verify_password

hashed = hash_password("user_password")
is_valid = verify_password("user_password", hashed)

# ❌ Incorrect — plain text storage or weak hashing
password_hash = user_password          # plain text
password_hash = hashlib.md5(...)       # weak algorithm
```

**Rules:**
- Always hash passwords with bcrypt via `hash_password()` in `app/auth.py`
- Never store or compare passwords as plain text
- Password changes must use `create_superadmin.py` — not the admin UI

---

## 5. Session Authentication

The admin panel uses session-based auth via `starlette-admin`'s `AuthProvider`:

- Sessions are managed by `SessionMiddleware` with `secret_key=SECRET_KEY`
- Session stores only: `user_id` (int) and `role` (str) — no sensitive data
- Session is signed (itsdangerous) but not encrypted
- `httpOnly` and `Secure` cookie flags are controlled by Starlette — verify they are set in production

```python
# ✅ Correct — read authenticated user from request.state
user = getattr(request.state, "user", None)
if user and user.role == Role.SUPERADMIN:
    ...

# ❌ Incorrect — reading role from session bypasses is_active check
role = request.session.get("role")
if role == "superadmin":
    ...
```

---

## 6. Role-Based Access Control

Every admin view must declare explicit access control using one of two mixins:

| Mixin | Who can access | Who can delete |
|-------|---------------|----------------|
| `SuperadminOnly` | `superadmin` only | `superadmin` |
| `EditorAccessMixin` | `superadmin` + `editor` | `superadmin` only |

```python
# ✅ Correct — mixin as first base class
class AIProviderView(SuperadminOnly, ModelView):
    ...

class TelegramSourceView(EditorAccessMixin, ModelView):
    ...

# ❌ Incorrect — no access control; any authenticated user can access
class AIProviderView(ModelView):
    ...
```

**Rules:**
- Never add an admin view without `SuperadminOnly` or `EditorAccessMixin`
- Never check `request.session["role"]` — always use `request.state.user`
- `inaccessible_callback` redirects to admin index, not a 403 page

---

## 7. Token Display in the Admin UI

Never display raw decrypted tokens in HTML templates or list views:

```python
# ✅ Correct — TokenField masks value in list/detail; password input in form
from app.fields import TokenField

fields = [
    TokenField("bot_token", label="Bot Token"),
]

# ❌ Incorrect — StringField displays the raw decrypted token in the list table
fields = [
    StringField("bot_token", label="Bot Token"),
]
```

`TokenField` shows `***xxxx` (last 4 chars visible) in list/detail views and uses `<input type="password">` in forms.

---

## 8. API Endpoint Security

The REST API endpoints under `/api/` are served from the same FastAPI app as the admin panel. They are not protected by session auth individually — the admin session covers the HTML page, and the JavaScript fetch calls originate from authenticated sessions.

**Rules:**
- Do not expose sensitive data (tokens, keys, password hashes) in API responses
- Test/validation endpoints must never write to the database
- Do not add unauthenticated endpoints that return internal state or secrets

---

## 9. GigaChat SSL Exception

GigaChat endpoints require `verify=False` because Sber uses an internal CA not trusted by default:

```python
# ✅ Correct — required for GigaChat; warnings suppressed explicitly
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        ...

# ❌ Incorrect — applying verify=False to non-GigaChat endpoints
async with httpx.AsyncClient(verify=False) as client:
    await client.get("https://api.telegram.org/...")
```

Only apply `verify=False` to Sber endpoints (`ngw.devices.sberbank.ru` and `gigachat.devices.sberbank.ru`). Never disable SSL verification for Telegram, VK, or MAX.

---

## 10. Forbidden Behaviors

- ❌ Using `String`/`Text` columns for credentials — always use `EncryptedString`
- ❌ Using `StringField` in admin views for credentials — always use `TokenField`
- ❌ Deploying with the default `SECRET_KEY = "change-me-in-production"`
- ❌ Deploying with the default `admin`/`admin` credentials
- ❌ Logging decrypted tokens, API keys, or password hashes
- ❌ Adding admin views without access control mixins
- ❌ Checking `request.session["role"]` instead of `request.state.user.role`
- ❌ Applying `verify=False` to non-GigaChat HTTPS calls
- ❌ Storing sensitive data in the session (beyond `user_id` and `role`)

---

## Checklist

- [ ] New credential columns use `EncryptedString`
- [ ] New credential admin fields use `TokenField`
- [ ] New admin views have `SuperadminOnly` or `EditorAccessMixin`
- [ ] `request.state.user` used for all role checks
- [ ] Passwords hashed via `hash_password()` — never stored plain
- [ ] `SECRET_KEY` changed from default before production deployment
- [ ] Default `admin`/`admin` credentials changed before production deployment
- [ ] GigaChat `verify=False` applied only to Sber endpoints
- [ ] No tokens, keys, or hashes logged or returned in API responses
