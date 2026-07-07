# Frontend v1 Source of Truth

## Purpose

This document is the frontend v1 rules document for DentalCare / pearlix.

Future frontend work must not follow old mock/demo assumptions when backend v1 already defines the real contract. Backend v1 is the source of truth. The frontend must follow actual backend endpoints, serializers, DTOs, role permissions, and backend tests.

## Source Priority Order

When documents, mocks, UI labels, or older implementation details conflict, use this priority order:

1. Actual backend code: URLs, views, serializers, models, permissions, and tests.
2. `project_docs/FRONTEND_API_ALIGNMENT_REPORT.md`
3. `project_docs/BACKEND_FINAL_QA_REPORT.md`
4. `project_docs/BACKEND_V1_SOURCE_OF_TRUTH.md`
5. `project_docs/FRONTEND_BACKEND_HANDOFF.md`
6. `project_docs/FRONTEND_INTEGRATION_FINAL_QA_REPORT.md`
7. `project_docs/FRONTEND_BACKEND_GAP_AUDIT_REPORT.md`, if present.
8. Current frontend code.
9. Old UI/mock/design docs as background only.

## Frontend Editing Rules

- Preserve the existing app structure.
- Preserve sidebar, routes, drawers, modals, and tabs unless a small backend-supported addition is needed.
- Add missing backend-supported UI inside existing screens.
- If backend v1 supports a feature and an existing page, tab, drawer, or modal logically belongs to it, add the missing UI there without redesigning the app.
- Do not redesign.
- Do not randomly rearrange layout.
- Do not add fake data.
- Do not use `localStorage` as source of truth except for auth/session tokens and theme preference.
- Do not change backend API contracts.
- Do not edit backend files.

## No Fake Persistence

If a backend endpoint is missing for Admin Users, Roles & Permissions, dashboard summaries, or any other feature:

- Do not fake saves.
- Do not use `localStorage` as real persistence.
- Make the UI read-only, deferred, or clearly marked as demo/deferred.
- Document the limitation in the final report.

## Backend-Driven Primary Workflows

These workflows must use backend APIs as source of truth:

- Auth/session.
- Patients.
- Patient profile.
- Employee profiles.
- Working shifts.
- Leave/availability.
- Appointments.
- Visits/active visit.
- Billing/invoices/payments.
- Attachments/X-rays.
- Stored AI results/findings.
- Clinic settings.

Patient profile tabs must use backend data for appointments, visits/history, billing, attachments, and stored AI results. If data is unavailable or endpoint support is missing, show a real empty/deferred state. Never show fake patient history rows.

## Deferred Or Out Of Scope

These must not be faked as real backend-backed features:

- Editable Roles & Permissions matrix if no backend endpoint exists.
- Admin Users integration if backend user-management API is missing.
- Dashboard aggregate cards if no backend dashboard endpoint exists.
- WebSockets/live updates.
- Service catalog/invoice items.
- Real AI inference, model loading, or training.
- PDF export unless backend supports it.

## Role Rules

- Admin can manage backend-supported admin features.
- Staff handles operational workflows allowed by backend.
- Doctor sees own appointments, active visit, and profile.
- Doctor must not process payments.
- Frontend must respect backend `403` responses and backend permissions.

## UI Rules

- Show loading, error, and empty states for backend-backed surfaces.
- Show real empty states, not fake rows.
- Do not show raw ISO timestamps.
- Do not show internal `version` numbers.
- Do not display raw `filePath` or `overlayFilePath` values.
- AI result wording must be educational/research/support wording, not clinical diagnosis wording.

## Date And Time Rules

- Appointment default date is local today.
- Do not hardcode demo dates.
- Use clinic timezone when available.
- Use a safe local fallback when clinic timezone is unavailable.

## Testing Rules

Every frontend change must run from `D:\pearlix\frontend`:

```powershell
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test
```

For final QA, also run backend-backed smoke validation with `seed_dev_users` and `seed_demo_data`.

## Browser Smoke Rule

Before committing final frontend QA changes, browser smoke must be run against backend seed data.

If browser automation fails, report the exact failure and run authenticated API checks plus frontend render tests. Do not claim full browser validation if it was not actually run.

## Final Frontend Coverage Map

For final frontend QA, Codex must produce a module-by-module coverage map for:

- Auth/session/users/roles.
- Clinic settings.
- Patients.
- Patient profile.
- Employee profiles/doctors/staff.
- Working shifts.
- Leave/availability.
- Appointments.
- Appointment workflow.
- Visits/active visit.
- Billing/invoices/payments.
- Attachments/X-rays.
- Stored AI results/findings.
- Admin users.
- Roles/permissions.
- Dashboard summaries.
- Timestamps/version/conflict behavior.
- Hardcoded/demo/localStorage usage.

Each module must be classified as one of:

- `COMPLETE`
- `PARTIAL - fix now`
- `BUG - fix now`
- `DEFERRED - backend endpoint missing or out of v1`
- `ACCEPTED LEGACY/DEMO - documented and not primary workflow`

## Required Final Report Format

Frontend work final reports must include:

- Files changed.
- Backend-supported gaps found.
- Fixes made.
- Deferred items.
- Accepted legacy/demo surfaces.
- Tests/checks.
- Browser/API smoke.
- Open issues.
- Ready for review: Yes/No.

Final QA reports must also clearly separate:

- Backend-supported gaps fixed.
- Backend-supported but still not implemented, with reason.
- Deferred because backend endpoint is missing or out of v1.
- Accepted legacy/demo surfaces.
