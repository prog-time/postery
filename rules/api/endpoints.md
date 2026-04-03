# API Contract Rules

> **Context:** Read this file before adding, modifying, or removing any REST API endpoint. Do not implement endpoints not documented here. Document a new endpoint here before implementing it.
> **Version:** 1.1

---

## 1. Core Principle

The REST API under `/api/` serves the admin UI exclusively. All endpoints are internal. There is no public API, no API key authentication, and no versioning prefix. All JSON endpoints return `{"ok": bool, ...}` — never raise `HTTPException` from endpoints consumed by the admin JavaScript.

---

## 2. Endpoint Inventory

### 2.1 Health Check

```
GET /
```

Response:
```json
{"status": "ok"}
```

Purpose: Minimal liveness check. No auth required. No DB access.

---

### 2.2 AI Text Generation

```
POST /api/ai/generate
```

Router: `app/routers/ai_generate.py` (prefix `/api/ai`)

**Request body (JSON):**
```json
{
  "text": "string",          // text to rewrite (required, non-empty after strip)
  "source_type": "string",   // "telegram" | "vk" | "max"
  "source_id": 0,            // integer PK of the source record
  "field": "string",         // "title" | "description"
  "prompt": "string|null"    // optional custom system prompt; null → use source's ai_prompt_*
}
```

**Success response:**
```json
{"ok": true, "result": "rewritten text"}
```

**Error responses (all HTTP 200):**

| Condition | Response |
|-----------|----------|
| No active provider | `{"ok": false, "error": "Нет активного AI провайдера"}` |
| Empty `text` field | `{"ok": false, "error": "Поле пустое — нечего обрабатывать"}` |
| Timeout | `{"ok": false, "error": "Превышено время ожидания"}` |
| Unknown provider type | `{"ok": false, "error": "Неизвестный тип провайдера"}` |

**Timeouts:** 60 s for generation call.

**Side effects:** None — does not write to the database.

---

### 2.3 AI Provider Connection Test

```
POST /api/ai-provider/test
```

Router: `app/routers/ai_provider.py` (prefix `/api/ai-provider`)

**Request body (JSON):**
```json
{
  "provider_type": "string",  // "openai" | "gigachat"
  "api_key": "string",        // plain-text key (not yet saved to DB)
  "base_url": "string|null",  // optional, OpenAI custom endpoint
  "scope": "string|null"      // optional, GigaChat scope
}
```

**Success response:**
```json
{"ok": true}
```

**Error response:**
```json
{"ok": false, "error": "..."}
```

**Timeouts:** 10 s.

**Side effects:** None — no DB writes.

**Notes:**
- For OpenAI: `GET {base_url}/v1/models` with Bearer auth, expect HTTP 200
- For GigaChat: `POST` OAuth endpoint, expect HTTP 200; `verify=False` required

---

### 2.4 Telegram Source Connection Test

```
POST /api/source/telegram/test
```

Router: `app/routers/source.py` (prefix `/api/source`)

**Request body (JSON):**
```json
{
  "bot_token": "string",
  "chat_id": "string|null"   // optional
}
```

**Success response:**
```json
{"ok": true, "message": "Подключение успешно (@botname)"}
```

**Error response:**
```json
{"ok": false, "error": "..."}
```

**Timeouts:** 10 s.

**Side effects:** None.

**Notes:**
- Step 1: `GET https://api.telegram.org/bot{token}/getMe` — validates token
- Step 2 (if `chat_id` provided): `GET getChat?chat_id={chat_id}` — validates channel access

---

### 2.5 VKontakte Source Connection Test

```
POST /api/source/vk/test
```

Router: `app/routers/source.py` (prefix `/api/source`)

**Request body (JSON):**
```json
{
  "access_token": "string",
  "group_id": 123456789
}
```

**Success response:**
```json
{"ok": true, "message": "Подключение успешно (Group Name)"}
```

**Error response:**
```json
{"ok": false, "error": "..."}
```

**Timeouts:** 10 s.

**Side effects:** None.

**Notes:**
- Calls `groups.getById` with VK API v5.199
- Does NOT verify photo upload capability (community vs user token)

---

### 2.6 MAX Source Connection Test

```
POST /api/source/max/test
```

Router: `app/routers/source.py` (prefix `/api/source`)

**Request body (JSON):**
```json
{
  "bot_token": "string",
  "chat_id": "string|null"   // optional
}
```

**Success response:**
```json
{"ok": true, "message": "Подключение успешно (@botname)"}
```

**Error response:**
```json
{"ok": false, "error": "..."}
```

**Timeouts:** 10 s.

**Side effects:** None.

**Notes:**
- `GET https://botapi.max.ru/me` with `Authorization: Bearer {token}` — validates token
- If `chat_id` provided: `GET /chats/{chat_id}` — validates channel access

---

### 2.7 Delete Post Image

```
DELETE /api/posts/image/{image_id}
```

Router: `app/routers/posts.py` (prefix `/api/posts`)

**Path parameter:** `image_id` — integer PK of a `post_images` row.

**Success response:**
```json
{"ok": true}
```

**Error response:**
```json
{"ok": false, "error": "Изображение не найдено"}
```

**Side effects:**
- Deletes the `post_images` row from the database (committed before file removal).
- Removes the physical file from disk (`BASE_DIR / image.file_path`). File removal errors are logged as warnings but do not fail the response.

**Notes:**
- No auth check beyond the admin session that owns the UI page.
- Does not re-order remaining `PostImage.order` values — ordering is preserved implicitly.

---

## 3. Routing Structure

```
app/routers/main.py        <- root router, aggregates all sub-routers + GET /
app/routers/ai_generate.py <- POST /api/ai/generate        (prefix /api/ai)
app/routers/ai_provider.py <- POST /api/ai-provider/test   (prefix /api/ai-provider)
app/routers/source.py      <- POST /api/source/*/test      (prefix /api/source)
```

All sub-routers are included in `router` from `app/routers/main.py`, which is included in `main.py`:

```python
# ✅ Correct — all routers aggregated in main.py router
from app.routers.ai_generate import router as ai_generate_router
router.include_router(ai_generate_router)

# ❌ Incorrect — registering routes directly on the FastAPI app
@app.post("/api/my/endpoint")
async def my_endpoint():
    ...
```

---

## 4. Admin Panel Routes

The admin panel is server-side rendered by starlette-admin at `/admin`. These are NOT REST endpoints — they are Jinja2-rendered HTML pages.

Do not add REST logic to admin view `render()` methods. Keep admin views as rendering-only controllers.

| View | URL Pattern | Type |
|------|-------------|------|
| Dashboard | `GET /admin/` | CustomView |
| Post list | `GET/POST /admin/posts` | CustomView |
| Post wizard | `GET/POST /admin/posts/wizard` | CustomView |
| Calendar | `GET /admin/calendar` | CustomView |
| Telegram source list | `GET /admin/telegram-source/list` | ModelView |
| Telegram wizard | `GET/POST /admin/telegram-source/wizard` | CustomView |
| VK source list | `GET /admin/v-k-source/list` | ModelView |
| VK wizard | `GET/POST /admin/vk-source/wizard` | CustomView |
| MAX source list | `GET /admin/m-a-x-source/list` | ModelView |
| MAX wizard | `GET/POST /admin/max-source/wizard` | CustomView |
| AI provider list | `GET /admin/ai-provider/list` | ModelView |
| AI provider wizard | `GET/POST /admin/ai-provider/wizard` | CustomView |
| Admin users | `GET /admin/admin-user/list` | ModelView |

---

## 5. Rules for Adding New Endpoints

- Define the endpoint in the appropriate router module (or create a new one for a new domain)
- Include the new router in `app/routers/main.py`
- Document the endpoint in this file before or immediately after implementation
- Return `{"ok": bool, ...}` for all JSON endpoints consumed by the admin JavaScript
- Use `fastapi.APIRouter` with a meaningful `prefix` and `tags`
- Never write to the database in test/validation endpoints
- Set appropriate timeouts: 10 s for connection tests, 60 s for generation

```python
# ✅ Correct — uses APIRouter with prefix and tags
router = APIRouter(prefix="/api/source", tags=["source"])

@router.post("/newplatform/test")
async def test_newplatform(body: NewPlatformTestRequest):
    return await _test_newplatform(body.token)

# ❌ Incorrect — endpoint defined directly on the FastAPI app
@app.post("/api/source/newplatform/test")
async def test_newplatform(...):
    ...
```

---

## Forbidden Behaviors

- ❌ Implementing an endpoint not documented in this file
- ❌ Raising `HTTPException` from endpoints consumed by the admin JS
- ❌ Writing to the database in test/validation endpoints
- ❌ Defining endpoints directly on `app` instead of via `APIRouter`
- ❌ Forgetting to include a new router in `app/routers/main.py`

---

## Checklist

- [ ] New endpoint documented in this file before or immediately after implementation
- [ ] Endpoint placed in the correct router module
- [ ] Router module included in `app/routers/main.py`
- [ ] Response uses `{"ok": bool, ...}` pattern for admin UI endpoints
- [ ] Test/validation endpoints make no DB writes
- [ ] Timeout set appropriately (10 s for tests, 60 s for generation)
- [ ] No `HTTPException` raised from endpoints used by the admin JavaScript
