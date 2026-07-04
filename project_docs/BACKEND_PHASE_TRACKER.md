# Backend Phase Tracker

## 1. Purpose

This file tracks DentalCare backend implementation phase-by-phase.

No phase is complete until:

1. Implementation matches `project_docs/BACKEND_V1_SOURCE_OF_TRUTH.md`.
2. No out-of-phase features were added.
3. Migrations are intentional and clean.
4. Tests pass.
5. Sanity checks pass.
6. Codex final report is complete.
7. ChatGPT reviews and approves moving forward.

## 2. Status Legend

Use these status values:

```text
Not started
In progress
Implemented
Tests passing
Ready for ChatGPT review
Reviewed by ChatGPT
Approved to continue
Blocked
```

Default status for all phases:

```text
Not started
```

## 3. Global Phase Gate

```text
A phase is complete only when:
- Source documents were inspected.
- Implementation stayed inside the requested phase.
- No out-of-scope features were added.
- Migrations are intentional and clean.
- Required automated tests pass.
- Required sanity checks pass.
- Manual testing notes are documented.
- Codex final report is complete.
- ChatGPT reviewed the phase.
- ChatGPT approved continuing to the next phase.
```

## 4. Backend Phase List

| Phase | Name | Status | Goal | Main scope | Do not build yet | Required tests | Required sanity checks | Acceptance criteria | ChatGPT review status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0A | Project foundation | Approved to continue | Django backend skeleton with PostgreSQL, DRF, custom User skeleton, and health endpoint. | Backend project folder; Django project; PostgreSQL config; environment variables; DRF config; CORS config if needed; custom User model with role/status/mustChangePassword fields; admin registration; health endpoint; initial migrations; basic tests. | JWT auth endpoints; password reset; patients; appointments; visits; billing; attachments; AI results. | Health endpoint test; custom user model test; basic settings/import test. | makemigrations; migrate; test; check. | Backend runs; migrations apply cleanly; custom User exists from first migration; health endpoint works; tests pass. | Reviewed by ChatGPT |
| 0B | Minimal auth | Approved to continue | JWT auth and seeded manual-test users. | Login; refresh if configured; logout if applicable; `/api/auth/me/`; fixed roles endpoint; seeded Admin/Staff/Doctor users for local manual testing; inactive user login blocked; mustChangePassword surfaced. | Forgot/reset password email flow; patients; appointments; billing. | Login success; inactive login blocked; `/auth/me` returns role; each seeded role can authenticate. | makemigrations check/dry-run unless migrations are intentional; test; check; manual token auth. | Admin/Staff/Doctor can be tested manually through token auth. | Reviewed by ChatGPT |
| 1 | Permission foundation | Approved to continue | Backend role/object permission foundation. | Role helpers; base DRF permission classes; Admin/Staff/Doctor permission tests; object-scope helpers structure for later phases. | Appointment logic; doctor patient scope implementation beyond helper skeleton if dependent models do not exist. | Admin allowed/blocked cases; Staff allowed/blocked cases; Doctor allowed/blocked cases. | makemigrations check/dry-run unless migrations are intentional; test; check. | No endpoint relies on frontend-only authorization. | Reviewed by ChatGPT |
| 2 | Clinic settings | Approved to continue | Clinic-wide timezone and capacity settings. | ClinicSettings model; singleton behavior; `clinicTimezone`; `maxSimultaneousAppointments`; validation for IANA timezone; API get/update. | Appointment scheduling; dashboard reports/charts. | Valid timezone accepted; invalid timezone rejected; capacity validation; permission tests. | makemigrations; migrate; test; check. | Scheduling authority settings exist before appointments. | Reviewed by ChatGPT |
| 3 | Patients | Approved to continue | Patient demographics API. | Patient model; create/list/search/retrieve/update; calculated age; nationalIdOrPassport as string; version/updatedAt optimistic locking; Admin read-only; Staff create/edit; Doctor scope later when appointments/visits exist. | Appointment logic; visits; billing; global doctor patient browsing. | CRUD; search; Admin read-only; Staff write; version conflict 409. | makemigrations; migrate; test; check. | Patient API is stable before scheduling. | Reviewed by ChatGPT |
| 4 | Employee profiles | Approved to continue | Doctor/staff profiles linked to users. | EmployeeProfile model; Doctor/Staff profile CRUD; specialty for Doctor; Admin management; Staff read-only team list; Doctor own profile read. | Working shift scheduling logic beyond profile relation; appointments. | Profile CRUD; role validation; permission tests. | makemigrations; migrate; test; check. | Doctors exist before appointments/shifts. | Reviewed by ChatGPT |
| 5 | Working shifts | Approved to continue | Recurring weekly availability. | WorkingShift model; employee relation; dayOfWeek; startTime/endTime; `isActive`; no overlapping active shifts for same person/day; API CRUD/bulk replace if specified; version/updatedAt. | One-time leave in WorkingShift; appointment scheduling. | start < end; overlap rejected; multiple non-overlapping shifts allowed; inactive shift behavior. | makemigrations; migrate; test; check. | Recurring schedule is separate from temporary leave. | Reviewed by ChatGPT |
| 6 | Leave exceptions | Approved to continue | Temporary leave/block model. | AvailabilityException model; startAt/endAt UTC; reason/status; create/update/cancel; does not mutate WorkingShift; affected appointment logic can be minimal until appointments exist, then completed in Phase 8/9. | Appointment scheduling beyond minimal future hook; mutating WorkingShift for leave. | Invalid interval rejected; cancel leave; leave does not edit shifts; permission tests. | makemigrations; migrate; test; check. | Temporary leave exists separately from recurring schedule. | Reviewed by ChatGPT |
| 7 | Appointment core | Approved to continue | Staff-only appointment creation with availability validation. | Appointment model; startAt/endAt UTC; durationMinutes validation; status defaults Scheduled; no due/dueAmount; same-doctor overlap validation; shift coverage validation; leave validation; clinic capacity validation; version/updatedAt; list/retrieve/create/update basics. | Visit lifecycle; billing; payment; AI. | Staff can create; Admin cannot create; Doctor cannot create; overlap rejected for same doctor; different doctors can overlap; leave blocks appointment; outside shift rejected; capacity enforced. | makemigrations; migrate; test; check. | Appointment creation is safe and source-of-truth aligned. | Reviewed by ChatGPT |
| 8 | Appointment workflow | Approved to continue | Status transitions and reschedule queue. | Check-in flow; cancel; no-show; postpone if supported; Needs Reschedule; reschedule endpoint; AppointmentChangeLog; status transition validation. | Visit model; invoice handoff; payments. | Scheduled -> Arrived by Staff; Arrived -> Checked-in by Staff; invalid transitions rejected; reschedule creates change log; affected leave appointments handled. | makemigrations; migrate; test; check. | Operational appointment workflow works before visits. | Reviewed by ChatGPT |
| 9 | Visit lifecycle | Approved to continue | Doctor clinical visit workflow. | Visit model; Doctor starts only own Checked-in appointment; appointment becomes In Visit; one active visit per doctor; notes fields; complete visit; appointment becomes Completed; version/updatedAt. | Invoice payment; attachments; AI inference. | Doctor cannot start Arrived appointment; Doctor cannot start another doctor's appointment; Doctor cannot have two active visits; Admin/Staff cannot clinically complete visit; complete visit updates appointment. | makemigrations; migrate; test; check. | Visit lifecycle is atomic and permission-safe. | Reviewed by ChatGPT |
| 10 | Invoice handoff | Approved to continue | Doctor treatment price creates pending invoice handoff. | Create invoice from visit; doctor enters treatment price/charge; pending invoice status; doctor cannot process payment; own-visit handoff only. | Cash payment processing; complex accounting; services/items. | Doctor can create invoice handoff for own completed visit; Doctor cannot create for other doctor; duplicate invoice prevention; Staff/Admin permission behavior. | makemigrations; migrate; test; check. | Doctor-to-front-desk billing handoff works. | Reviewed by ChatGPT |
| 11 | Billing/payments | Approved to continue | Invoices and cash payments. | Invoice; Payment; cash payment; paidAmount/balance calculated from payments; invoice status calculation; invoice total edit before payment only with audit reason; cancelled invoice terminal for edits/payments; version updates after payment. | Services table; InvoiceItems; ServiceCatalog; complex accounting. | Process valid payment; reject payment over balance; reject payment on cancelled invoice; partial payment status; paid status; edit total before payment with reason; reject edit after payment; Staff can process payment; Doctor cannot process payment; Admin read-only. | makemigrations; migrate; test; check. | Billing source of truth is Invoice/Payment only. | Reviewed by ChatGPT |
| 12 | Attachments/X-rays | Ready for ChatGPT review | X-ray/file metadata and upload authorization. | Attachment model; patient/visit relation; upload metadata; file type validation; file size validation; authorized original URL; delete behavior. | AI results; real external storage integration unless requested. | Valid upload metadata; invalid type rejected; oversized file rejected; permission tests. | makemigrations; migrate; test; check; manual upload sanity if endpoint exists. | X-ray files can be linked to visit/patient safely. | Pending review |
| 13 | AI results | Not started | AI result storage/display endpoints only. | AIResult; AIResultFinding; status; modelVersion; overallConfidence; overlay path; findings by FDI tooth/disease/confidence; retry placeholder if specified; educational/research support only. | Clinical diagnosis decision workflow; real AI inference service unless explicitly requested. | Create/store result; list findings; permissions; failed/processing/completed statuses. | makemigrations; migrate; test; check. | Backend stores AI outputs for frontend display. | Not reviewed |
| 14 | Frontend API alignment | Not started | Check DTOs, endpoint shapes, and frontend integration readiness. | CamelCase DTO review; endpoint consistency; error shape consistency; 409 conflict behavior; role response shapes; no due/dueAmount in AppointmentDTO; invoice balance calculated. | Frontend source changes unless explicitly requested. | Full backend test suite; representative API smoke tests. | makemigrations check/dry-run; test; check; smoke test core endpoints. | Frontend can begin replacing mock/localStorage with API calls. | Not reviewed |
| 15 | Final backend QA | Not started | Final backend cleanup and manual test script. | Full test run; manual Postman/curl testing script; seed/demo data review; environment docs; known limitations; frontend integration checklist. | New product features; live-update implementation unless explicitly approved. | Full backend test suite; permission regression tests; workflow regression tests. | makemigrations check/dry-run; migrate on clean DB; test; check; documented manual script. | Backend ready for frontend integration. | Not reviewed |

## 5. Current Phase

```text
Current phase: 12 - Attachments/X-rays
Current status: Ready for ChatGPT review
Next required action: ChatGPT must review Phase 12 implementation report.
```
