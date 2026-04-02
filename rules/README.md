# Rules Directory — Master Orchestrator

> **Purpose:** Serve as the single entry point for AI agents to understand all mandatory rules, dependencies, and execution order for the Postery project.
> **Context:** Read this file first. Follow the steps exactly before touching any code, schema, or documentation.
> **Version:** 1.1

---

## 1. Core Principle

Before any task:

1. Understand the rules directory structure
2. Identify which files are relevant to your task
3. Follow rules strictly in order
4. Produce complete and auditable output

> The agent **must never skip reading any required file**. All domain, process, and meta rules are part of the source of truth.

---

## 2. Project Overview

**Postery** is a FastAPI-based multi-platform autoposter that publishes content to Telegram, VKontakte, and MAX Messenger. Key characteristics:

- **Language / Runtime:** Python 3.11+, FastAPI + Uvicorn
- **Database:** SQLite via SQLAlchemy ORM (no Alembic — manual additive migrations in `main.py`)
- **Admin UI:** Starlette-Admin with `CustomView` wizard flows and `ModelView` list pages
- **Background worker:** asyncio task polled every 30 s to publish scheduled `PostChannel` records
- **AI text generation:** OpenAI (gpt-4o-mini) and GigaChat (Sber OAuth)
- **Templates:** Jinja2 in `admin/templates/`
- **Security:** Fernet-encrypted token storage, bcrypt password hashing, session-based auth with role checks (superadmin / editor)

---

## 3. Directory Overview

```
rules/
├─ README.md                          <- You are here
├─ application-master-prompt.md       <- Generator prompt (do not modify)
├─ _meta/
│  └─ how-to-write-rules.md          <- File structure and writing standards
├─ database/
│  └─ schema.md                      <- Full database schema with ERD (8 active tables)
├─ domain/
│  ├─ posts.md                       <- Post + PostChannel lifecycle, wizard, images, tags
│  ├─ sources.md                     <- TelegramSource, VKSource, MAXSource management
│  ├─ publishing.md                  <- Background worker, publisher contract, platform rules
│  └─ ai-integration.md              <- AIProvider management, generation flow, GigaChat
├─ api/
│  └─ endpoints.md                   <- All REST API routes and contract rules
└─ process/
   ├─ architecture-design.md         <- Layer structure, CustomView pattern, async/sync boundary
   ├─ observability.md               <- Logging, worker events, error storage
   ├─ ai-workflow.md                 <- AI agent lifecycle rules
   ├─ ci-cd.md                       <- Manual deployment, start.sh, production checklist
   ├─ security.md                    <- Encryption, bcrypt, session auth, role guards
   └─ testing-strategy.md           <- Testing standards (no test suite currently)
```

> **Note:** Additional domain files `auth.md`, `post.md`, and `ai-generation.md` exist under `domain/` from the initial generation pass. They contain valid detail; read them when their subject is relevant. The canonical domain files per this index are the four listed above.

---

## 4. Reading & Execution Order

When performing a task, the AI agent **must follow this sequence**:

| # | File | Purpose |
|---|------|---------|
| 1 | `_meta/how-to-write-rules.md` | Understand formatting and standards for all rules files |
| 2 | `process/architecture-design.md` | Pre-implementation design: layers, boundaries, async rules |
| 3 | `process/ai-workflow.md` | Lifecycle rules: understand → design → implement → verify → document |
| 4 | `database/schema.md` | Full schema before touching models, migrations, or queries |
| 5 | `domain/posts.md` | Post lifecycle, wizard steps, PostChannel rules |
| 6 | `domain/sources.md` | Source types, wizard pattern, token encryption, test-before-save |
| 7 | `domain/publishing.md` | Worker logic, publisher contract, per-platform formatting |
| 8 | `domain/ai-integration.md` | AIProvider activation, generation flow, GigaChat OAuth |
| 9 | `api/endpoints.md` | All REST contracts. Do not implement undocumented endpoints |
| 10 | `process/observability.md` | Logging levels, worker log events, error storage |
| 11 | `process/ci-cd.md` | Deployment checklist before shipping |
| 12 | `process/security.md` | Security rules before touching auth, tokens, or secrets |
| 13 | `process/testing-strategy.md` | Test expectations before marking work done |

> **Rule:** Never implement before design and lifecycle steps are confirmed.

---

## 5. Self-Verification

Before reporting task completion, the agent **must check**:

- [ ] All relevant rules files read and applied
- [ ] Design artifacts exist if required
- [ ] Database, domain, API changes validated against rules
- [ ] Migration approach confirmed (additive ALTER TABLE in `_migrate()`, not Alembic)
- [ ] Encrypted fields use `EncryptedString` type decorator
- [ ] Role-based access applied (SuperadminOnly or EditorAccessMixin)
- [ ] Background worker implications considered for new PostChannel states
- [ ] Logging present in new code paths
- [ ] Tests created or noted as required
- [ ] No hardcoded `SECRET_KEY` left as default in production

---

## 6. Reporting / Task Output

At the end of a task, the AI agent **must produce a structured report**:

1. **Files affected** — list all files touched
2. **Rules read** — confirm each relevant rules file was read
3. **Design artifacts** — include diagrams, impact analysis, or placeholders
4. **Verification checks** — list all checklist items passed
5. **Deviations** — document any items skipped or marked `_Not applicable_`
6. **Summary** — state task completion, blockers, and next steps

**Example:**

```json
{
  "task": "Add LinkedIn source type",
  "files_affected": [
    "app/models/sources/linkedin.py",
    "app/publisher/linkedin.py",
    "rules/database/schema.md",
    "rules/domain/sources.md"
  ],
  "rules_read": [
    "process/architecture-design.md",
    "domain/sources.md",
    "domain/publishing.md",
    "database/schema.md",
    "api/endpoints.md"
  ],
  "design_artifacts": ["ERD update in database/schema.md"],
  "verification_checks": [
    "Token stored as EncryptedString",
    "Wizard pattern used (CustomView + EditorAccessMixin)",
    "Test endpoint added to /api/source/linkedin/test",
    "Worker extended for linkedin source_type",
    "ai_prompt_title and ai_prompt_description columns registered in _migrate()"
  ],
  "deviations": ["None"],
  "summary": "Task complete. New source type follows all established patterns."
}
```

---

## 7. Best Practices

- Never assume defaults — follow explicit rules
- Stop immediately if a required rules file is missing
- Maintain consistency with existing code and rules
- Incremental and verifiable steps are mandatory
- All token/secret fields must use `EncryptedString` — never `String` for credentials
- All new wizard flows must extend `CustomView` with `EditorAccessMixin` or `SuperadminOnly`
- New publisher adapters must implement `publish(text, source, image_paths) -> tuple[bool, str | None]`

## Agent Entry Point Summary

| Step | Action |
|------|--------|
| 1 | Read this `README.md` first |
| 2 | Follow the reading & execution order in Section 4 |
| 3 | Apply rules and document all steps |
| 4 | Verify using checklist in Section 5 |
| 5 | Produce structured task report as in Section 6 |
