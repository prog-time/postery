# Domain: Authentication and Access Control

> **Context:** Read this file before modifying authentication logic, adding new admin views, changing role permissions, or touching session handling.
> **Version:** 1.0

---

## 1. Overview

The admin panel uses **session-based authentication** via `starlette-admin`'s `AuthProvider` interface. There is no JWT or API key auth for the admin panel.

Roles control access at the view level using two mixins:

| Mixin | Who can access | Who can delete |
|-------|---------------|----------------|
| `SuperadminOnly` | `superadmin` only | `superadmin` |
| `EditorAccessMixin` | `superadmin` + `editor` | `superadmin` only |

---

## 2. Auth Provider: `RoleAuthProvider`

Implemented in `app/auth.py`. Inherits from `starlette_admin.auth.AuthProvider`.

### Login

1. Validates username and password are non-empty (raises `FormValidationError` otherwise)
2. Queries `admin_users` for active user with matching username
3. Verifies password with `bcrypt.checkpw`
4. On success: stores `user_id` and `role` in `request.session`
5. On failure: raises `LoginFailed`

### Session Validation (`is_authenticated`)

- Reads `user_id` from `request.session`
- Loads the `AdminUser` from DB
- Returns `False` if not found or `is_active=False`
- On success: stores the full `AdminUser` ORM object in `request.state.user`

**Rule:** Always read the user from `request.state.user`, never from `request.session` directly (the session only has the ID and role string, not the full object).

```python
# ✅ Correct — read from request.state
user = getattr(request.state, "user", None)
if user and user.role == Role.SUPERADMIN:
    ...

# ❌ Incorrect — session has only role string, not the ORM object
role = request.session.get("role")
```

---

## 3. Password Hashing

- Algorithm: bcrypt (via `bcrypt` library)
- Function to hash: `app.auth.hash_password(password: str) -> str`
- Function to verify: `app.auth.verify_password(plain: str, hashed: str) -> bool`
- Never store or compare passwords as plain text
- Changing passwords is done via `create_superadmin.py` script — not through the admin UI

---

## 4. Role Definitions

```python
class Role(str, enum.Enum):
    SUPERADMIN = "superadmin"
    EDITOR     = "editor"
```

| Permission | superadmin | editor |
|------------|-----------|--------|
| Create posts | ✅ | ✅ |
| Edit posts | ✅ | ✅ |
| Delete posts/channels | ✅ | ❌ |
| Manage sources (create/edit) | ✅ | ✅ |
| Delete sources | ✅ | ❌ |
| View/manage AI providers | ✅ | ❌ |
| View/manage admin users | ✅ | ❌ |

---

## 5. Access Control Mixins

### `SuperadminOnly`

Apply to views that must be completely hidden from editors (AI providers, admin user management).

```python
# ✅ Correct
class AIProviderView(SuperadminOnly, ModelView):
    ...
```

```python
# ❌ Incorrect — editor can see AI provider settings
class AIProviderView(EditorAccessMixin, ModelView):
    ...
```

`SuperadminOnly` implements:
- `is_accessible(request)` → `True` if `user.role == Role.SUPERADMIN`
- `inaccessible_callback(request)` → redirect to admin index (not 403)

### `EditorAccessMixin`

Apply to views accessible by both roles but with restricted delete.

Implements:
- `is_accessible(request)` → `True` if any authenticated user
- `can_delete(request)` → `True` only for `superadmin`
- `can_create(request)` → `True` for all authenticated users
- `can_edit(request)` → `True` for all authenticated users

---

## 6. Applying Mixins to New Views

When creating a new `ModelView` or `CustomView`:

1. Decide access level: superadmin-only or editor-accessible
2. Apply the appropriate mixin as the **first** base class
3. Never add a view without any mixin — all views must have explicit access control

```python
# ✅ Correct — mixin first
class MyNewView(EditorAccessMixin, CustomView):
    ...

# ❌ Incorrect — no access control
class MyNewView(CustomView):
    ...
```

---

## 7. Default Admin User

On first startup, `init_default_admin()` in `main.py` creates a superadmin user:
- Username: `admin`
- Password: `admin`

**Rule:** Change the default password immediately in any non-development environment using `create_superadmin.py`.

---

## 8. Session Middleware

`SessionMiddleware` (from Starlette) is attached to the Admin instance, not the main FastAPI app:

```python
middlewares=[
    Middleware(SessionMiddleware, secret_key=SECRET_KEY),
]
```

**Rules:**
- `SECRET_KEY` must be changed from the default `"change-me-in-production"` in any deployed environment
- The session cookie is signed but not encrypted — do not store sensitive data in the session
- Session stores only: `user_id` (int) and `role` (str)

---

## 9. Forbidden Behaviors

- ❌ Adding admin views without `SuperadminOnly` or `EditorAccessMixin`
- ❌ Reading `request.session["role"]` for authorization decisions — always read `request.state.user`
- ❌ Storing passwords in plain text
- ❌ Changing passwords through the admin UI (the `password_hash` field is shown in admin but the help text says to use `create_superadmin.py`)
- ❌ Deploying with the default `SECRET_KEY = "change-me-in-production"`

---

## Checklist

- [ ] New view has `SuperadminOnly` or `EditorAccessMixin` as first base class
- [ ] `request.state.user` used for role checks, not `request.session`
- [ ] Passwords hashed with bcrypt via `hash_password()`
- [ ] `SECRET_KEY` changed from default before deployment
- [ ] Default `admin/admin` credentials changed before deployment
- [ ] Session stores only `user_id` and `role` (no sensitive data)
