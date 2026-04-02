# How to Write Rules

> **Purpose:** This file defines the standard every rules file in this project must meet. It is self-referential — it must itself comply with the rules it defines.
> **Context:** Read this file before creating or updating any rules in the `rules/` directory.
> **Version:** 1.1

---

## 1. Purpose

- Explain why this documentation system exists
- Describe what problem it solves
- Ensure consistency across all rules files
- Make onboarding for AI agents and developers deterministic

---

## 2. Mandatory Structure of Every Rules File

Every `.md` file in `rules/` must contain:

1. A `# Title` matching the file's subject
2. A `> Context:` blockquote explaining when an AI agent should read this file
3. A `> Version:` blockquote
4. Numbered sections with clear, imperative headings
5. At least one ✅ Correct and one ❌ Incorrect example per major rule
6. A `## Checklist` section at the end

---

## 3. Writing Style Rules

### Language

- Write all rules in English
- Write in short, imperative sentences: "Use X", "Never do Y", "Always Z"
- Avoid vague qualifiers: "try to", "consider", "might want to" — state rules definitively
- Use second person: "the agent must", "you must"

### Code Example Formatting

```python
# ✅ Correct
class MySourceView(EditorAccessMixin, ModelView):
    fields = [
        TokenField("api_key", label="API Key"),
    ]

# ❌ Incorrect — uses StringField for a secret, exposes credential in plain text
class MySourceView(ModelView):
    fields = [
        StringField("api_key", label="API Key"),
    ]
```

### Decomposition Rules

- One rule per bullet point — never combine two rules in one sentence
- If a section grows beyond 10 bullets, split into subsections
- If a topic covers more than 3 distinct concerns, create a separate file

---

## 4. Versioning and Changelog Rules

```markdown
# ✅ Correct
> Version: 1.1
## Changelog
- Rule BR-005 updated to include edge case validation for empty prompts
```

```markdown
# ❌ Incorrect — no version, no changelog entry when updating an existing rule
```

---

## 5. Forbidden Content

- ❌ Opinions without justification — every rule must have a reason
- ❌ Duplicate rules that already exist in another file — link instead
- ❌ Broken or hypothetical code examples
- ❌ Vague rules that cannot be verified (e.g., "write clean code")
- ❌ Rules that contradict another file without explicitly noting the override

---

## 6. Project-Specific Conventions for Code Examples

Use Python unless the rule is language-agnostic. Use actual project types:

| Topic | Type to reference |
|-------|------------------|
| Encrypted credential field | `EncryptedString` from `app.models.encrypted` |
| Custom admin field | `TokenField` from `app.fields` |
| Access control | `SuperadminOnly` or `EditorAccessMixin` from `app.auth` |
| Publisher signature | `async def publish(text, source, image_paths) -> tuple[bool, str | None]` |
| Session database | `SessionLocal()` context manager |
| Config values | `from app.config import SECRET_KEY, BASE_DIR` |

---

## 7. Not Applicable Sections

When a concern genuinely does not apply to this project, write the section header and mark it:

```markdown
## 7. Metrics

_Not applicable — no metrics collection system is currently configured._
```

Never omit the section entirely. Explicitly marking it as not applicable communicates a deliberate decision.

---

## Checklist

- [ ] Title matches the file subject
- [ ] `> Context:` blockquote included
- [ ] `> Version:` blockquote included
- [ ] Numbered sections present
- [ ] At least one ✅ Correct and one ❌ Incorrect example per major rule
- [ ] Examples are syntactically correct Python (or clearly marked otherwise)
- [ ] Decomposition rules followed
- [ ] Forbidden content avoided
- [ ] Checklist section present at the end
- [ ] Not-applicable sections marked explicitly, not omitted
