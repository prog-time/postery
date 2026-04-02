# Domain: Post

> **Context:** Read this file before touching post creation, the wizard flow, PostStatus transitions, PostChannel logic, or image uploads.
> **Version:** 1.0

---

## 1. Overview

A **Post** is the master content record. It contains a title, optional description, tags, and images. It is published to one or more **PostChannels**, each targeting a specific platform source (Telegram, VK, MAX).

A Post is created through a **3-step wizard** in the admin panel (`PostWizardView`).

---

## 2. Post Status Machine

```
DRAFT  ──(wizard step 3 complete)──► READY  ──(all channels published)──► PUBLISHED
```

| Status | Meaning | Who sets it |
|--------|---------|-------------|
| `draft` | Wizard steps 1–2 not complete | Default on creation |
| `ready` | All channels configured; worker may publish | Wizard step 3 POST handler |
| `published` | Every `PostChannel.status == published` | Worker after last channel publishes |

**Rules:**
- The worker only processes channels whose parent post has status `ready` or `published`
- Do not set `status = ready` unless at least one `PostChannel` exists
- Do not set `status = published` directly — the worker computes this from channel states

---

## 3. Wizard Flow (3 Steps)

### Step 1 — Content

**Route:** `GET /admin/posts/wizard?step=1[&post_id=N]`

**Form fields:**
- `title` (required, VARCHAR 256)
- `description` (optional, TEXT)
- `tags` (optional, comma-separated, VARCHAR 512)
- `images` (optional, multiple file uploads, stored under `data/uploads/{post_id}/`)

**Rules:**
- Title is required; return step 1 with error if blank
- Images are appended, not replaced, on re-submit
- File path stored relative to `BASE_DIR` (e.g., `data/uploads/1/photo.jpg`)
- After save, redirect to `?post_id={id}&step=2`

### Step 2 — Select Sources

**Route:** `GET /admin/posts/wizard?step=2&post_id=N`

**Form fields:**
- `telegram_sources[]` — multi-select of active TelegramSource IDs
- `vk_sources[]` — multi-select of active VKSource IDs
- `max_sources[]` — multi-select of active MAXSource IDs

**Rules:**
- At least one source must be selected; show error otherwise
- On submit: delete all existing `PostChannel` records for this post, then recreate from form selection
- After save, redirect to `?post_id={id}&step=3&channel_id={first_channel_id}`

### Step 3 — Customize Per Channel

**Route:** `GET /admin/posts/wizard?step=3&post_id=N&channel_id=M`

**Form fields:**
- `title` (optional override)
- `description` (optional override)
- `scheduled_at` (optional ISO datetime string from `datetime-local` input, naive local time)

**Rules:**
- After saving a channel, advance to the next channel in `post.channels` list
- When all channels are processed, set `post.status = ready` and redirect to `/admin/posts`
- If `from_list=1` query param is present, redirect back to `/admin/posts` immediately (editing from list, not wizard)
- `scheduled_at = None` means "publish immediately when worker next runs"
- Do not set `channel.status` to anything other than `pending` in the wizard — the worker owns status

---

## 4. PostChannel Rules

- `source_type` must be exactly `"telegram"`, `"vk"`, or `"max"`
- `source_id` is the integer PK of the corresponding source table — resolved in Python, not via DB FK
- `effective_title` and `effective_description` properties handle fallback to parent post values
- Never bypass `effective_title` / `effective_description` when building the published text — use `build_text()` from `app.publisher.utils`

```python
# ✅ Correct — use the utility
from app.publisher.utils import build_text
text = build_text(channel, post, bold_title=True)

# ❌ Incorrect — bypasses per-channel overrides
text = post.title + "\n" + post.description
```

---

## 5. Image Upload Rules

- Upload directory: `data/uploads/{post_id}/`
- Created automatically on first upload (`mkdir parents=True, exist_ok=True`)
- File path stored as relative path from `BASE_DIR`
- Maximum 10 images per media group (Telegram and VK limit)
- Images are sent in `PostImage.order` ascending order
- Do not delete images when re-submitting step 1 — they accumulate

---

## 6. Tag Formatting

Tags are stored as a raw comma-separated string in `posts.tags`. The `format_tags()` utility in `app.publisher.utils` converts them to hashtag format for publishing:

```python
# Input:  "тег один, тег два"
# Output: "#тег_один #тег_два"
```

- Spaces within a tag are replaced with underscores
- Leading `#` is added automatically
- If `tags` is NULL or empty, no tag line is appended

---

## 7. Forbidden Behaviors

- ❌ Setting `post.status = published` directly in wizard or API handlers — only the worker does this
- ❌ Storing absolute file paths — always use paths relative to `BASE_DIR`
- ❌ Lazy-loading ORM relations inside async publisher functions — load all data before the first `await`
- ❌ Deleting images when the wizard step 1 is re-submitted
- ❌ Creating `PostChannel` with a `status` other than `pending`

---

## Checklist

- [ ] Wizard step 1 validates title is non-empty
- [ ] Wizard step 2 validates at least one source selected
- [ ] Step 2 deletes and recreates channels on each submit
- [ ] Step 3 sets `post.status = ready` only after all channels are processed
- [ ] `effective_title` / `effective_description` used via `build_text()`
- [ ] Image paths stored relative to `BASE_DIR`
- [ ] `scheduled_at` parsed as `datetime.fromisoformat()`, never assumed UTC
- [ ] Worker not bypassed for status transitions
