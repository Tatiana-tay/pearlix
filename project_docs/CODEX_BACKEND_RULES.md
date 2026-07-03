# CODEX Backend Rules

## 1. Purpose

This file controls every Codex backend implementation phase for DentalCare.

It exists to ensure:

- Clean minimal code.
- Source-grounded implementation.
- No hallucinated backend features.
- Every phase tested.
- No phase moves forward without ChatGPT review.

Codex must treat this file as an implementation guardrail, not as a replacement for the product/backend source of truth.

## 2. Source Document Priority

Use this priority order:

```text
1. project_docs/BACKEND_V1_SOURCE_OF_TRUTH.md
2. project_docs/BACKEND_IMPLEMENTATION_SPEC.md
3. project_docs/FRONTEND_BACKEND_HANDOFF.md
4. project_docs/CODEX_BACKEND_RULES.md
5. project_docs/BACKEND_PHASE_TRACKER.md
```

Clarifications:

- `project_docs/BACKEND_V1_SOURCE_OF_TRUTH.md` wins on product/backend rules.
- `project_docs/BACKEND_IMPLEMENTATION_SPEC.md` guides Django/DRF implementation structure.
- `project_docs/FRONTEND_BACKEND_HANDOFF.md` records frontend facts and DTO needs but does not override backend rules.
- Existing frontend mock/localStorage behavior is not automatically final backend behavior.

## 3. Required Pre-Work Before Every Phase

Before every backend implementation phase, Codex must inspect:

```text
project_docs/BACKEND_V1_SOURCE_OF_TRUTH.md
project_docs/BACKEND_IMPLEMENTATION_SPEC.md
project_docs/FRONTEND_BACKEND_HANDOFF.md
project_docs/CODEX_BACKEND_RULES.md
project_docs/BACKEND_PHASE_TRACKER.md
```

Codex must also inspect existing backend files once backend code exists.

Codex must not assume file structure, model names, endpoint names, or test setup without checking the repo.

## 4. Backend Stack Rules

The locked backend stack is:

```text
Django
Django REST Framework
PostgreSQL
Custom User model from the start
Simple role-based permissions: Admin | Staff | Doctor
JWT auth for the decoupled SPA unless later changed explicitly
```

SQLite is not the main project database. PostgreSQL is required for development and production-like testing because scheduling, payments, and concurrency behavior matter.

## 5. Scope Rules

Codex must implement only the requested phase.

Codex must not add:

- Editable permission matrix backend.
- Dynamic Permission / RolePermission backend.
- Per-user permissions.
- Request Access.
- PendingAccountRequest.
- Services table.
- InvoiceItems.
- ServiceCatalog.
- Dashboard reports/charts.
- Required WebSockets/live events.
- Complex accounting.
- Clinical diagnosis workflow.

## 6. Minimal Code Rules

- Keep code clean, minimal, direct, and readable.
- Prefer simple Django/DRF patterns over premature abstractions.
- Do not create helpers, services, base classes, or utilities unless they are clearly needed by the current phase.
- Do not duplicate business logic.
- Do not create placeholder code for future phases unless required for imports/tests in the current phase.
- Do not modify frontend code during backend phases unless the phase explicitly asks for frontend integration.
- Do not silently change product behavior.

## 7. Testing Rules

Every implementation phase must include tests appropriate to the phase.

If migrations are intentionally created, Codex must run:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py test
python manage.py check
```

If no migration should be created, Codex must run:

```bash
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py check
```

If formatting/lint tools are already configured, also run them. Do not add new formatting tools unless the phase explicitly asks.

Frontend checks are required only if frontend code changes:

```bash
npm run typecheck
npm run build
```

## 8. Manual Testing / Sanity Rules

Every phase must include a short manual testing note.

Examples:

- Endpoint tested with curl/Postman.
- Admin page opens.
- Login works for seeded roles.
- Forbidden role receives 403.
- Stale version returns 409.
- Payment cannot exceed balance.

Only include manual tests relevant to the phase.

## 9. Phase Report Format

Every Codex phase response must end with this exact structure:

```text
PHASE X COMPLETE

Files changed:
- ...

Files created:
- ...

Database changes:
- migrations created: Yes/No
- migration names: ...

Tests run:
- command:
- result:

Sanity checks:
- command:
- result:

Manual testing notes:
- ...

Scope control:
- Out-of-phase files/features avoided: Yes/No
- Any source-of-truth conflict found: Yes/No

Open issues:
- ...

Ready for ChatGPT review:
- Yes/No
```

## 10. Approval Rule

Codex must never say:

```text
Ready for next phase
```

Codex must only say:

```text
Ready for ChatGPT review
```

ChatGPT decides whether the next phase can start.
