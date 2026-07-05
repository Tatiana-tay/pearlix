# Backend Manual Test Script

Date: 2026-07-05

Purpose: manual backend smoke testing for Phase 15. These steps are intended for local development against PostgreSQL on host port `5433`.

## Prerequisites

- Docker Desktop is running with the Linux engine.
- PowerShell is opened in `D:\pearlix\backend`.
- `backend/.env` exists locally and is not committed.
- Local `.env` values match:

```text
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=dentalcare
POSTGRES_USER=dentalcare
POSTGRES_PASSWORD=dentalcare
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## Setup Commands

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d db
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_dev_users
.\.venv\Scripts\python.exe manage.py runserver
```

Seeded development users:

| Role | Username | Password | Expected |
| --- | --- | --- | --- |
| Admin | `admin@example.com` | `Admin123!` | Active admin user. |
| Staff | `staff@example.com` | `Staff123!` | Active staff user. |
| Doctor | `doctor@example.com` | `Doctor123!` | Active doctor user. |
| Staff inactive | `inactive@example.com` | `Inactive123!` | Login rejected or protected API rejected. |

## PowerShell API Helper

```powershell
$base = "http://127.0.0.1:8000"

$staffLogin = Invoke-RestMethod `
  -Method Post `
  -Uri "$base/api/auth/login/" `
  -ContentType "application/json" `
  -Body (@{ username = "staff@example.com"; password = "Staff123!" } | ConvertTo-Json)

$staffHeaders = @{ Authorization = "Bearer $($staffLogin.accessToken)" }

Invoke-RestMethod -Method Get -Uri "$base/api/health/"
Invoke-RestMethod -Method Get -Uri "$base/api/auth/me/" -Headers $staffHeaders
Invoke-RestMethod -Method Get -Uri "$base/api/auth/roles/" -Headers $staffHeaders
```

Expected:

- Health returns `{"status":"ok"}`.
- `auth/me` returns the Staff user with `role`, `status`, `createdAt`, and `mustChangePassword`.
- `auth/roles` returns only `Admin`, `Staff`, and `Doctor`.

## Auth And Role Checks

1. Login as Admin, Staff, and Doctor.
2. Confirm each login response contains `accessToken`, `refreshToken`, and `user`.
3. Login as `inactive@example.com`.
4. Expected inactive result: login fails, or any protected request made with an inactive token is rejected with `401` or `403`.
5. Request a protected endpoint without a token.
6. Expected anonymous result: `401`.

## Core Settings

1. Staff GET `/api/clinic/settings/`.
2. Confirm response includes `clinicTimezone`, `maxSimultaneousAppointments`, `createdAt`, `updatedAt`, and `version`.
3. Admin PATCH settings with a current `version`.
4. Reuse the old version in another PATCH.
5. Expected stale result: `409 Conflict`.

## Patient Workflow

1. Staff POST `/api/patients/` with:

```json
{
  "firstName": "Manual",
  "lastName": "Patient",
  "nationalIdOrPassport": "QA-001",
  "dateOfBirth": "1990-01-01",
  "gender": "Female",
  "phoneNumber": "+1-555-0100",
  "email": "manual.patient@example.com"
}
```

2. Confirm response uses `gender`, omits `sex`, keeps `nationalIdOrPassport` as a string, includes calculated `age`, and includes `version`.
3. Staff PATCH with the current `version`.
4. Repeat PATCH with the stale version.
5. Expected stale result: `409 Conflict`.
6. Admin POST or PATCH a patient.
7. Expected Admin result: `403`.
8. Doctor attempts to read/edit an unrelated patient.
9. Expected unrelated Doctor result: blocked by object scope.

## Employee Profiles, Shifts, And Leave

1. Admin creates or confirms an `EmployeeProfile` for a Doctor.
2. Admin creates a `WorkingShift` for the doctor.
3. Confirm `WorkingShift` response uses `isActive`.
4. Admin creates an `AvailabilityException` for a future window.
5. Confirm leave response uses `startAt` and `endAt`.
6. Confirm creating leave does not mutate recurring shift rows into one-time leave records.
7. Staff GETs profiles/shifts/leave and should receive read access where supported.
8. Doctor GETs own profile and own relevant schedule data only.

## Appointment Workflow

1. Staff POST `/api/appointments/` with patient ID, doctor profile ID, visit type, `startAt`, `endAt`, and duration.
2. Confirm backend defaults status to `Scheduled`.
3. Confirm appointment response omits `due`, `dueAmount`, `paidAmount`, `balance`, and payment fields.
4. Try overlapping appointment for the same doctor.
5. Expected result: rejected.
6. Try same time for a different doctor while clinic capacity allows it.
7. Expected result: accepted.
8. Try appointment outside shift or during leave.
9. Expected result: rejected.
10. Staff moves appointment through arrival/check-in actions.
11. Doctor tries to create a general appointment.
12. Expected Doctor result: `403`.
13. Admin tries to create a general appointment.
14. Expected Admin result: `403`.

## Visit Workflow

1. Doctor starts a visit for their own checked-in appointment.
2. Confirm appointment moves to `In Visit` and a `Visit` is created or activated.
3. Doctor GET `/api/visits/active/`.
4. Confirm only the doctor's own active visit is returned.
5. Doctor saves notes with current `version`.
6. Repeat update with stale `version`.
7. Expected stale result: `409 Conflict`.
8. Doctor completes the visit.
9. Confirm visit and appointment move to `Completed`.
10. Confirm only one active visit per doctor is allowed.

## Billing And Payment Workflow

1. Doctor POST `/api/invoices/` or `/api/visits/{visitId}/invoice/` for their own completed visit with `totalAmount`.
2. Confirm invoice status is `Pending`, `paidAmount` is `0.00`, and `balance` equals `totalAmount`.
3. Staff POST `/api/payments/` with `method: "Cash"` and a partial amount.
4. Confirm invoice status becomes `Partially Paid`, `paidAmount` increases, and `balance` decreases.
5. Staff posts the remaining cash payment.
6. Confirm invoice status becomes `Paid` and `balance` becomes `0.00`.
7. Attempt payment above balance, zero payment, negative payment, and non-cash payment.
8. Expected results: all rejected.
9. Doctor attempts to process payment.
10. Expected Doctor result: `403`.
11. Admin attempts to process payment.
12. Expected Admin result: `403`.
13. Confirm appointment and visit responses still omit payment/due/balance fields after payments.

## Attachments And X-Ray Metadata

1. Staff uploads an attachment to `/api/attachments/` with multipart form data.
2. Confirm response includes `fileUrl`, `originalFilename`, `contentType`, `sizeBytes`, `attachmentType`, and `uploadedById`.
3. Confirm response omits server file path fields.
4. Upload unsupported type and oversized file.
5. Expected result: rejected.
6. Doctor uploads an X-ray only in own active visit context.
7. Expected own active visit result: accepted.
8. Doctor attempts patient-only upload or another doctor's visit upload.
9. Expected result: `403`.

## AI Result Storage

1. Staff or scoped Doctor POST `/api/ai-results/` for an existing attachment.
2. Include model name/version, status, optional overlay URL, and findings.
3. Confirm response includes `modelName`, `modelVersion`, `status`, `overlayUrl`, and nested findings.
4. Confirm response omits clinical diagnosis, final diagnosis, treatment plan, payment, due, and balance fields.
5. GET `/api/attachments/{attachmentId}/ai-results/`.
6. GET `/api/attachments/{attachmentId}/ai-result/`.
7. POST to `/api/predict/`, `/api/infer/`, `/api/train/`, `/api/run-ai/`, and `/api/analyze-xray/`.
8. Expected inference/training endpoint result: `404`.

## Out-Of-Scope Checks

Confirm these routes return `404`:

- `/api/services/`
- `/api/service-catalog/`
- `/api/invoice-items/`
- `/api/role-permissions/`

Confirm no manual workflow depends on:

- Editable permission matrix.
- Services catalog.
- Invoice line items.
- WebSockets.
- AI inference or model training.
- Clinical diagnosis workflow based on AI output.

## Final Manual Pass Criteria

- Auth, roles, settings, patient, scheduling, visit, billing, attachment, and AI storage flows are manually reachable.
- Role/object-scope blocks return `401`, `403`, or `404` as appropriate.
- Stale editable updates return `409 Conflict`.
- Frontend remains unchanged.
- Backend is ready for frontend integration planning only after automated validation also passes.
