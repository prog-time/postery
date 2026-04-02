# AI Workflow Rules

> **Context:** Read this file before performing any modification, refactor, migration, or feature implementation. Apply it for every task, regardless of size.
> **Version:** 1.0

---

## 1. Core Principle

The agent must behave like a careful mid-level engineer, not an auto-generator.
- Always analyze before coding
- Always design before implementing
- Always test before finishing
- Never generate large changes blindly
- Never modify files you did not read

---

## 2. Mandatory Development Lifecycle

**Step 1 — Understand**

- Read `rules/README.md`
- Read `process/architecture-design.md`
- Read the relevant domain file(s) for the task
- Read the relevant source files before proposing changes
- Identify existing patterns to follow (wizard, publisher, model, router)

**Step 2 — Design**

- Identify all affected layers: models, routers, views, publishers, worker, templates
- List all files that will change
- Identify DB impact: new table or column → plan `_migrate()` entry and update `schema.md`
- Identify access control: `SuperadminOnly` or `EditorAccessMixin`
- Identify worker impact: new `source_type` or new `PostChannel` state
- Do not write code yet

**Step 3 — Implement**

- Make the smallest possible change that satisfies the requirement
- Follow existing conventions exactly (naming, structure, patterns)
- Reuse existing abstractions: `build_text()`, `EncryptedString`, `TokenField`, publisher contract
- Avoid introducing new patterns unless no existing pattern fits

**Step 4 — Verify**

- Check that all `EncryptedString` rules are followed for new secrets
- Check that access control mixins are applied correctly
- Check that the publisher contract is respected (return tuple, no raise)
- Check that no lazy ORM load occurs inside async publisher functions
- Check that migrations are registered in `_migrate()` and the schema is documented

**Step 5 — Document**

- Update `rules/database/schema.md` if any schema changed
- Update the relevant `rules/domain/*.md` if business rules changed
- Update `rules/api/endpoints.md` if any endpoint was added or changed
- The task is not complete until documentation is updated

---

## 3. Scope Control Rules

```python
# ✅ Correct — minimal targeted change
def _post_edit(self, request, templates, pk, source_data, wizard_url):
    # only update the specific fields needed
    source.name = name
    if bot_token:
        source.bot_token = bot_token

# ❌ Incorrect — mixes unrelated refactoring with the feature
def _post_edit(...):
    # rewrote the entire view, renamed variables, changed error handling,
    # AND updated the field
```

---

## 4. Generation Size Limits

- Prefer small iterations over large outputs
- Never generate more than one new module at a time without review
- Break large features (e.g., new source type) into subtasks following the checklist in `domain/sources.md`
- Large monolithic generations increase hallucination risk and make review impossible

---

## 5. Safety Rules

```python
# ✅ Correct — uses field that exists in the model
source.ai_prompt_title        # confirmed in app/models/sources/telegram.py

# ❌ Incorrect — hallucinated field
source.system_prompt          # does not exist
post.published_by             # does not exist
```

- Never reference database columns that are not in `rules/database/schema.md`
- Never invent API fields not defined in `rules/api/endpoints.md`
- Never guess business logic — verify against domain rules files
- If unsure, read the source file before proposing a change
- Do not fabricate packages not in `requirements.txt`

---

## 6. Test-First Expectations

- Add or update tests for every behavior change
- Bug fixes must include a regression test
- New features must cover: happy path + validation edge case + error case
- See `process/testing-strategy.md` for the current test baseline

---

## 7. Documentation Coupling Rules

Every change must update rules. Failure to update documentation means the task is incomplete.

| Change type | Required documentation update |
|-------------|-------------------------------|
| New DB column | `database/schema.md` |
| New business rule | Relevant `domain/*.md` with BR-NNN number |
| New API endpoint | `api/endpoints.md` |
| New source type | `domain/sources.md`, `domain/publishing.md`, `database/schema.md` |
| New AI provider | `domain/ai-integration.md`, `database/schema.md` |
| Changed access control | `domain/auth.md` |

---

## 8. Forbidden Behaviors

- ❌ Editing files without reading them first
- ❌ Ignoring existing conventions (naming, structure, access control mixins)
- ❌ Silent schema changes (adding columns without updating `_migrate()` AND `schema.md`)
- ❌ Skipping tests
- ❌ Skipping documentation updates
- ❌ Making speculative optimizations or refactors not requested
- ❌ Introducing new dependencies (`requirements.txt`) without explicit discussion

---

## Checklist

- [ ] Relevant rules files read before starting
- [ ] Existing source files inspected before proposing changes
- [ ] Design documented before implementation
- [ ] Minimal change applied; no unrelated modifications
- [ ] All `EncryptedString` and `TokenField` rules respected
- [ ] Publisher contract respected (return tuple, catch all exceptions)
- [ ] No hallucinated fields, columns, or packages
- [ ] Documentation updated: schema, domain, API as applicable
- [ ] Tests added or noted as pending (see `testing-strategy.md`)
