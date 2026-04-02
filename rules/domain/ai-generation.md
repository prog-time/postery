# Domain: AI Text Generation

> **Context:** Read this file before modifying AI provider management, AI text generation endpoints, or adding a new AI provider type.
> **Version:** 1.0

---

## 1. Overview

Postery supports AI-powered rewriting of post titles and descriptions before publication. The AI layer consists of:

- **`ai_providers` table** — stores provider credentials and which one is active
- **`/api/ai/generate` endpoint** — accepts text + source context, calls the active provider, returns the rewritten text
- **`/api/ai-provider/test` endpoint** — validates provider credentials without saving
- **Admin wizard** — `AIProviderWizardView` for creating/editing providers

---

## 2. Provider Model Rules

- Only **one** `AIProvider` record may have `is_active=True` at any time
- Enforcement: `AIProviderView.after_create` and `after_edit` deactivate all other providers when a provider is activated
- Only **one** record per `provider_type` (openai / gigachat) may exist: enforced in `before_create`
- Credentials are stored with `EncryptedString`

```python
# ✅ Correct — deactivate others after activation
async def after_edit(self, request, obj):
    if obj.is_active:
        await anyio.to_thread.run_sync(lambda: _do_deactivate_others(obj.id))
```

---

## 3. Supported Providers

### 3.1 OpenAI

- **Auth:** `Authorization: Bearer {api_key}` header
- **Default endpoint:** `https://api.openai.com`
- **Custom endpoint (`base_url`):** supports Azure and proxy endpoints. Strip trailing slashes.
- **Model:** `gpt-4o-mini` (hardcoded; update here and in `ai_generate.py` if changing)
- **Completions URL:** `{base_url}/v1/chat/completions`
- **Validation URL:** `{base_url}/v1/models` (GET, expect 200)
- **Timeout:** 60 s for generation, 10 s for connection test

### 3.2 GigaChat (Sber)

- **Auth:** OAuth 2.0 via `https://ngw.devices.sberbank.ru:9443/api/v2/oauth`
  - Header: `Authorization: Basic {api_key}` (Base64 key from GigaChat cabinet)
  - Header: `RqUID: {uuid4()}`
  - Body: `scope={scope}` (form-encoded)
  - Response: `{"access_token": "..."}` (short-lived)
- **Completions URL:** `https://gigachat.devices.sberbank.ru/api/v1/chat/completions`
- **SSL verification:** disabled (`verify=False`) due to Sber's internal CA — suppress `InsecureRequestWarning` with `warnings.catch_warnings()`
- **Scope values:** `GIGACHAT_API_PERS` (personal) or `GIGACHAT_API_CORP` (corporate)
- **Model:** `GigaChat` (hardcoded)
- **Timeout:** 60 s for generation, 10 s for OAuth test

---

## 4. Generation Request Flow

```
POST /api/ai/generate
  ↓
Load active AIProvider from DB
  ↓
Load source (telegram/vk/max) by source_type + source_id
  ↓
Read ai_prompt_title or ai_prompt_description (as system message)
  ↓
Call provider API with {system_msg?, user_msg=text}
  ↓
Return {"ok": true, "result": "..."}
    or {"ok": false, "error": "..."}
```

**Rules:**
- If no active provider exists, return `{"ok": false, "error": "..."}` immediately — do not raise an HTTP error
- If the source does not exist, proceed without a system message (use provider default behavior)
- If the prompt field is empty/NULL, make the API call without a system message
- The `field` parameter must be `"title"` or `"description"` — determines which prompt column to read
- Strip whitespace from both the prompt and the user text before sending

---

## 5. API Response Contract

```python
# ✅ Correct success response
{"ok": True, "result": "rewritten text here"}

# ✅ Correct failure response
{"ok": False, "error": "human-readable error message"}

# ❌ Incorrect — raising HTTP exceptions from AI endpoints
raise HTTPException(status_code=500, detail="AI error")
```

All error conditions (no provider, timeout, API error, unknown provider type) return `{"ok": False, "error": "..."}` with HTTP 200.

---

## 6. Adding a New AI Provider

1. Add a new value to `ProviderType` enum in `app/models/providers/ai_provider.py`
2. Implement `_generate_{provider}()` async function in `app/routers/ai_generate.py`
3. Implement `_test_{provider}()` async function in `app/routers/ai_provider.py`
4. Add the dispatch branch in `generate_text()` and `test_connection()`
5. Update `AIProviderView.fields` in `app/admin.py` with any new fields
6. Update `AIProviderWizardView` template if provider-specific fields are needed
7. Update this file and `rules/database/schema.md`

---

## 7. Forbidden Behaviors

- ❌ Storing OAuth access tokens (GigaChat `access_token`) in the database — they are short-lived, fetch on each request
- ❌ Sharing one `httpx.AsyncClient` instance across requests — create a new client per request with `async with httpx.AsyncClient(...) as client:`
- ❌ Enabling SSL verification for GigaChat endpoints — Sber uses an internal CA not trusted by default
- ❌ Raising HTTP exceptions from generation or test endpoints — always return `{"ok": false, ...}`
- ❌ Calling AI provider APIs from within a SQLAlchemy session context — close the DB session first

---

## Checklist

- [ ] Only one `AIProvider` with `is_active=True` at any time
- [ ] `after_create` and `after_edit` hooks deactivate other providers on activation
- [ ] New provider type added to `ProviderType` enum AND `AIProviderView.fields`
- [ ] Generation endpoint returns `{"ok": bool, ...}` for all cases
- [ ] GigaChat SSL verification disabled, warnings suppressed
- [ ] GigaChat OAuth token fetched per-request, not stored
- [ ] `httpx.AsyncClient` created per-request with appropriate timeout
- [ ] AI endpoint called only after DB session is closed
