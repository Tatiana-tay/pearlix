# Frontend API Alignment Report

Phase: 14 - Frontend API alignment
Date: 2026-07-05

## Scope

This report reviews the current backend API against the source documents and the existing frontend mock/data shapes.

No frontend source files were changed. The frontend remains mock/localStorage based until a later approved frontend integration phase.

## Sources Inspected

- `project_docs/BACKEND_V1_SOURCE_OF_TRUTH.md`
- `project_docs/BACKEND_IMPLEMENTATION_SPEC.md`
- `project_docs/FRONTEND_BACKEND_HANDOFF.md`
- `project_docs/CODEX_BACKEND_RULES.md`
- `project_docs/BACKEND_PHASE_TRACKER.md`
- Backend apps: `accounts`, `core`, `patients`, `employees`, `scheduling`, `visits`, `billing`, `attachments`, `ai_results`
- Frontend read-only surfaces: `frontend/src/types/models.ts`, `frontend/src/data/adapters.ts`, mock data/loaders, auth/session context, appointment, billing, patient, staff, attachment, and AI UI components

## Backend Alignment Summary

The backend is aligned with the Phase 14 source-of-truth contract for the implemented v1 scope:

- REST-first API with simple `User.role = Admin | Staff | Doctor`.
- No editable permission matrix or per-user permission backend.
- JWT auth is available through `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/logout/`, `/api/auth/me/`, and `/api/auth/roles/`.
- DTOs are camelCase at the API boundary.
- Editable records return `409 Conflict` with `detail` and `currentVersion` on stale updates.
- Appointment DTOs do not expose `due`, `dueAmount`, `paidAmount`, `balance`, or payment state.
- Invoice DTOs expose backend-calculated `paidAmount`, `balance`, and status.
- Payment processing is Staff-only and cash-only in Phase 11 scope.
- X-ray attachments are metadata/private-file records, not public static paths.
- AI results are storage/display records only; no inference/training endpoint or clinical diagnosis workflow exists.

Small backend-only alignment fixes made in Phase 14:

- Auth user DTO now includes `phone` and `createdAt`.
- Login response now includes `accessToken` and `refreshToken` aliases while preserving existing `access` and `refresh` keys.
- Login response now includes top-level `mustChangePassword`.
- Patient DTO now includes read-only `patientId` while preserving existing `id`.
- Added cross-app API alignment smoke tests in `backend/core/test_api_alignment.py`.

## Contract Notes By Area

### Auth And Roles

- `/api/auth/login/` accepts the current backend login payload and returns JWT tokens plus `user`.
- Response includes compatibility token keys: `access`, `refresh`, `accessToken`, and `refreshToken`.
- `UserDTO` includes `id`, `username`, `email`, `phone`, `fullName`, `role`, `status`, `createdAt`, and `mustChangePassword`.
- `/api/auth/roles/` returns the fixed role list only: `Admin`, `Staff`, `Doctor`.
- No `Permission`, `RolePermission`, dynamic RBAC, request-access, or pending-account API was added.

### Clinic Settings

- `/api/clinic/settings/` returns `clinicTimezone`, `maxSimultaneousAppointments`, and `updatedAt`.
- Admin can update settings; Staff and Doctor can read.
- Invalid IANA timezone and invalid capacity are rejected.

### Patients

- Patient API uses `gender`, not `sex`.
- `gender` is constrained to `Male` or `Female`.
- `nationalIdOrPassport` is a string field.
- `age` is calculated from `dateOfBirth`, not stored.
- `patientId` is returned as a read-only alias for the persisted `id`.
- Staff can create/update. Admin is read-only. Doctor global patient browsing remains rejected unless object scope exists through later workflows.
- Stale update returns `409 Conflict`.

### Employee Profiles And Shifts

- Employee profiles use a neutral `EmployeeProfile` model for Doctor and Staff.
- Staff/Doctor profile DTOs expose camelCase fields.
- Working shifts use backend `isActive`.
- Frontend `isOnLeave` remains a frontend compatibility concern; one-time leave is represented by `AvailabilityException`.

### Scheduling And Leave

- Appointment create/update uses UTC `startAt` and `endAt`.
- Backend validates same-doctor overlap, working shift coverage, leave overlap, clinic capacity, and duration.
- Appointment creation is Staff-only.
- Admin and Doctor cannot create general appointments.
- Appointment response omits financial `due`/`dueAmount`.
- `doctorProfileId` is the canonical backend field; `doctorId` is accepted as an input alias for appointment create/update filters.
- `availability-exceptions/` is canonical; `leave-exceptions/` exists as a route alias.

### Visits

- Visit lifecycle is Doctor-owned and versioned.
- Staff/Admin can read visits; Doctor is scoped to own visits.
- Visit DTOs expose backend note fields: `subjectiveNotes`, `objectiveNotes`, `assessmentNotes`, `planNotes`, and `generalNotes`.
- No payment, invoice-balance, or AI diagnosis state is stored on visits.

### Billing And Payments

- Doctor creates invoice handoff only for own completed visit.
- Staff/Admin cannot create invoice handoffs.
- Staff can list/retrieve invoices and process cash payments.
- Admin can list/retrieve invoices read-only.
- Doctor can list/retrieve own invoices/payments only.
- Invoice response includes calculated `paidAmount` and `balance`.
- Payment response is cash-only and does not include gateway/card/service-catalog fields.
- Appointment/Visit status is not mutated by invoice creation or payment processing.

### Attachments

- Attachments are linked to patient and optional visit.
- Staff can upload; Doctor can upload only for own active visit.
- File metadata includes `originalFilename`, `contentType`, `sizeBytes`, `fileUrl`, `uploadedById`, and timestamps.
- Original file access is authorized through `/api/attachments/{id}/original-url/`.

### AI Results

- AI result storage supports `Pending`, `Processing`, `Completed`, and `Failed`.
- AI result fields include `attachmentId`, `patientId`, `visitId`, `resultSummary`, `modelName`, `modelVersion`, `overallConfidence`, `overlayUrl`, `errorMessage`, and nested findings.
- Findings include `toothFdi`, `diseaseLabel`, and `confidence`.
- No inference, training, diagnosis, prescription, treatment-plan, or payment endpoint was added.

## Frontend Adapter Work Still Needed Later

The current frontend still uses mock data, adapter arrays, in-memory state, and localStorage. Later frontend integration should:

- Replace `SessionContext` demo login with auth API calls.
- Replace localStorage/mock loaders with an API client and cache/refetch strategy.
- Use `accessToken`/`refreshToken` from login.
- Map backend `id`/`patientId` into the frontend patient route and list keys.
- Map backend `doctorProfileId` to current frontend `doctorId` where needed, or update frontend types intentionally.
- Convert frontend appointment date/time controls into UTC `startAt`/`endAt`.
- Remove API-backed use of appointment `due`.
- Use Invoice/Payment for all billing balances.
- Map backend `isActive` to any temporary frontend `isOnLeave` display compatibility.
- Map visit note field names if the current frontend keeps legacy `clinicalNotes`/`diagnosisNotes`/`treatmentNotes` names.
- Map attachment `fileUrl`, `originalFilename`, `contentType`, and `sizeBytes` to viewer/download UI fields.
- Map AI result `id`/`attachmentId`/`overlayUrl` to current frontend `analysisId`/`fileId`/`overlayFilePath` names if the frontend types are not updated.
- Add `version` to update forms and show refresh/retry messaging for `409 Conflict`.
- Render backend field validation errors and 401/403 auth errors.

## Validation Status

Validation passed from `backend/` on 2026-07-05:

- `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`: passed; requirements already satisfied.
- `docker compose up -d db`: passed; PostgreSQL container running.
- `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: passed; no changes detected.
- `.\.venv\Scripts\python.exe manage.py migrate`: passed; no migrations to apply.
- `.\.venv\Scripts\python.exe manage.py test core.test_api_alignment --noinput -v 2`: passed; 3 tests OK.
- `.\.venv\Scripts\python.exe manage.py test accounts core patients employees scheduling visits billing attachments ai_results --noinput`: passed; 343 tests OK.
- `.\.venv\Scripts\python.exe manage.py check`: passed; no issues.
- `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: passed; no changes detected.

No frontend files were changed.
