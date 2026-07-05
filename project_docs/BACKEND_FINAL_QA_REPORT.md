# Backend Final QA Report

Date: 2026-07-05

Phase: 15 - Final backend QA

Status: Ready for ChatGPT review

This report summarizes the backend v1 implementation state after Phases 0A through 14. It is a backend QA artifact only. It does not approve Phase 15, does not claim production readiness, and does not move work into a new phase.

## Source Basis

Source priority used for this QA pass:

1. `project_docs/BACKEND_V1_SOURCE_OF_TRUTH.md`
2. `project_docs/BACKEND_IMPLEMENTATION_SPEC.md`
3. `project_docs/FRONTEND_BACKEND_HANDOFF.md`
4. `project_docs/CODEX_BACKEND_RULES.md`
5. `project_docs/BACKEND_PHASE_TRACKER.md`

Key source decisions re-confirmed:

- Backend v1 uses Django, Django REST Framework, PostgreSQL, JWT auth, and a custom User model.
- Roles are simple role checks: `Admin`, `Staff`, `Doctor`.
- Editable permission matrices, per-user permissions, request-access flows, and `RolePermission` APIs are out of scope.
- Financial source of truth is `Invoice` and `Payment`; appointments and visits must not carry due/balance/payment state.
- Services, InvoiceItems, ServiceCatalog, complex accounting, dashboard/report models, WebSockets, and clinical diagnosis workflows are out of scope.
- Attachments and AI results are storage/display support only. No model loading, inference, or training is implemented in backend v1.
- Frontend code remains unchanged until a separate frontend integration phase.

## Implemented Backend Apps

| Area | App | Current QA result |
| --- | --- | --- |
| Auth and users | `accounts` | Custom user, JWT login/refresh/logout/me, simple roles, inactive-user rejection. |
| Core settings | `core` | Health endpoint and clinic settings with timezone/capacity. |
| Patients | `patients` | Source-aligned patient DTOs, `gender`, calculated age, string national ID/passport, optimistic locking. |
| Employee profiles | `employees` | Neutral doctor/staff profile model and role-scoped access. |
| Scheduling | `scheduling` | Working shifts, availability exceptions, appointments, status workflow, reschedule queue, change logs. |
| Visits | `visits` | Doctor-owned visit lifecycle, notes, start/complete flow, active visit guardrails. |
| Billing | `billing` | Doctor invoice handoff, Staff cash payments, invoice status/balance calculation, audit/version behavior. |
| Attachments | `attachments` | Patient/visit file metadata, upload validation, authenticated original-file access. |
| AI results | `ai_results` | AI result/finding metadata storage and retrieval, no inference/training endpoints. |

## Endpoint Surface

Implemented groups:

- `/api/health/`
- `/api/clinic/settings/`
- `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/logout/`, `/api/auth/me/`, `/api/auth/roles/`
- `/api/patients/`, `/api/patients/{id}/`
- `/api/employee-profiles/`, `/api/employee-profiles/me/`, `/api/employee-profiles/{id}/`
- `/api/working-shifts/`, `/api/working-shifts/{id}/`
- `/api/availability-exceptions/`, `/api/availability-exceptions/{id}/`
- `/api/leave-exceptions/`, `/api/leave-exceptions/{id}/`
- `/api/appointments/`, appointment workflow actions, reschedule queue, and change logs
- `/api/visits/`, `/api/visits/start/`, `/api/visits/active/`, visit notes and complete endpoints
- `/api/invoices/`, `/api/invoices/{id}/`, `/api/invoices/{id}/payments/`, `/api/invoices/{id}/cancel/`
- `/api/payments/`, `/api/payments/{id}/`
- `/api/attachments/`, `/api/attachments/{id}/`, `/api/attachments/{id}/original-url/`
- `/api/visits/{id}/attachments/`
- `/api/ai-results/`, `/api/ai-results/{id}/`, `/api/ai-results/{id}/findings/`
- `/api/attachments/{id}/ai-results/`, `/api/attachments/{id}/ai-result/`

Intentionally absent:

- `/api/predict/`
- `/api/infer/`
- `/api/train/`
- `/api/run-ai/`
- `/api/analyze-xray/`
- `/api/services/`
- `/api/service-catalog/`
- `/api/invoice-items/`
- `/api/role-permissions/`

## Role Boundary Summary

Admin:

- Can manage backend admin data where exposed by the current backend.
- Can read operational records where source docs require read-only access.
- Cannot mutate appointments, patients, billing, invoices/payments, visits, attachments, or AI results through operational APIs.

Staff:

- Can create/edit patients.
- Can create and manage appointments and reschedule work.
- Can process arrival/check-in status changes.
- Can read team schedules.
- Can process cash payments and edit/cancel invoices within billing rules.
- Cannot manage users/roles or clinical doctor-only visit actions.

Doctor:

- Can access own appointments and active visit context.
- Can start/continue/complete own visits.
- Can edit assigned/relevant patients only.
- Can upload/manage X-rays and AI result metadata in own active visit context.
- Can create invoice handoff for own completed visit with a treatment amount.
- Cannot create general appointments, access global billing, process payments, edit payments, cancel invoices, or access unrelated patient/visit records.

Anonymous and inactive users:

- Anonymous users are rejected from protected APIs.
- Inactive users cannot authenticate normally and protected API access is rejected.

## Data Contract Highlights

- DTOs use camelCase for API-facing fields.
- `Patient` uses `gender`, not `sex`.
- Patient `age` is calculated from date of birth and is not authoritative stored state.
- `nationalIdOrPassport` remains a string.
- `WorkingShift.isActive` is the backend recurring shift state; one-time leave is `AvailabilityException`.
- Appointments and visits omit `due`, `dueAmount`, `paidAmount`, `balance`, and payment fields.
- Invoices expose `totalAmount`, `paidAmount`, `balance`, status, audit/version data, and related IDs.
- Payments are cash-only in v1.
- Attachment responses expose authenticated file access metadata and omit server file paths.
- AI result responses expose support metadata, model name/version, status, overlay URL/path, findings, and omit clinical diagnosis/treatment-plan fields.

## Automated Validation

| Command | Result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` | Passed. Requirements already satisfied. |
| `docker compose up -d db` | Passed. PostgreSQL container reported running. |
| `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` | Passed. No changes detected. |
| `.\.venv\Scripts\python.exe manage.py migrate` | Passed. No migrations to apply. |
| `.\.venv\Scripts\python.exe manage.py seed_dev_users` | Passed. Local dev users updated. |
| `.\.venv\Scripts\python.exe manage.py test core.test_final_backend_qa --noinput` | Passed. 4 tests OK. |
| `.\.venv\Scripts\python.exe manage.py test accounts core patients employees scheduling visits billing attachments ai_results --noinput` | Passed. 347 tests OK. |
| `.\.venv\Scripts\python.exe manage.py check` | Passed. System check identified no issues. |
| `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` | Passed. No changes detected. |
| `.\.venv\Scripts\python.exe manage.py test --noinput` | Passed. 347 tests OK; no stall. |

Test run notes:

- JWT tests emitted `InsecureKeyLengthWarning` for the dev-only secret key length. This is a local development configuration warning and did not produce Django system-check issues.
- Some tests intentionally create tokens for inactive users to verify inactive access rejection. The SimpleJWT warning is expected for those negative-path tests.

## Final QA Additions

- Added a final smoke test module at `backend/core/test_final_backend_qa.py`.
- Added documentation for final QA, manual testing, backend runbook, and frontend integration.
- No frontend source files were changed.

## Current Non-Blocking Limits

- Frontend still uses mock/localStorage flows until a frontend integration phase replaces them.
- Production deployment, HTTPS, object storage, email delivery, observability, and backup policy are not configured by this backend QA phase.
- WebSockets/live updates remain deferred.
- AI inference/model loading/training remains out of scope; only result metadata storage is implemented.

## Readiness Statement

Validation succeeded. Backend v1 is ready for ChatGPT review and frontend integration planning. This is not a production-readiness certification.
