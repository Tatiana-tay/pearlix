# 1. Purpose and Scope

This is an implementation specification, not backend code.

It is based on:

- `BACKEND_V1_SOURCE_OF_TRUTH.md`
- `FRONTEND_BACKEND_HANDOFF.md`

`BACKEND_V1_SOURCE_OF_TRUTH.md` is canonical. If the frontend handoff, mock data, current localStorage behavior, or existing UI assumptions conflict with it, the source-of-truth document wins.

This document translates the locked backend v1 decisions into a concrete Django + Django REST Framework + PostgreSQL implementation plan. It should guide backend app layout, models, serializers, permissions, services, endpoints, validation, tests, and frontend integration preparation.

This document does not:

- Implement backend code.
- Create Django apps or files.
- Edit frontend source code.
- Install packages.
- Re-open locked product decisions.

Backend v1 is REST-first. Live updates/WebSockets are deferred.

Out of scope for backend v1:

- Editable permission matrix.
- Dynamic `Permission` or `RolePermission` backend.
- Per-user permission overrides.
- Request Access.
- `PendingAccountRequest`.
- Services table.
- `InvoiceItems`.
- `ServiceCatalog`.
- Dashboard reports/charts.
- Required WebSockets/live events.
- Complex accounting.
- Clinical diagnosis workflow.

# 2. Recommended Backend Architecture

Recommended stack:

- Django.
- Django REST Framework.
- PostgreSQL.
- Django built-in auth foundation, preferably with a custom `User` model extending `AbstractUser` from the start.
- JWT-based authentication for the SPA, with short-lived access tokens and refresh tokens handled carefully.

Authentication tradeoff:

- Secure Django session auth is simple and strong if the frontend and backend are same-origin, but it requires CSRF and cookie settings to be correct for SPA deployment.
- JWT is common for a decoupled Vite SPA and DRF API, but token storage and refresh handling must be designed carefully.
- Recommendation for this project: use JWT access/refresh auth for the decoupled SPA, store access token in memory where possible, prefer an HttpOnly secure refresh cookie in production, and support `/api/auth/me/` as the frontend's session authority. If deployment becomes same-origin only, secure session auth can be reconsidered without changing most role/object permission code.

Recommended Django apps:

```text
accounts
clinic
patients
staffing
scheduling
visits
billing
attachments
ai_results
```

## accounts

Responsibility:

- Authentication identity.
- User role and account status.
- Password setup/reset.
- Fixed role list.

Models:

- `User`
- `PasswordResetToken`

Main API endpoints:

- `/api/auth/login/`
- `/api/auth/logout/`
- `/api/auth/refresh/`
- `/api/auth/me/`
- `/api/auth/forgot-password/`
- `/api/auth/reset-password/`
- `/api/auth/change-password/`
- `/api/users/`
- `/api/roles/`

Services/validators:

- Password reset token creation/validation.
- Inactive account login blocking.
- Must-change-password enforcement.
- Role validation.

Dependencies:

- Used by all apps for `createdBy`, `updatedBy`, `processedBy`, and permission checks.

## clinic

Responsibility:

- Clinic-wide settings.
- Timezone and simultaneous appointment capacity.

Models:

- `ClinicSettings`

Main API endpoints:

- `/api/clinic-settings/`

Services/validators:

- Singleton settings loader.
- IANA timezone validation.
- Clinic capacity setting validation.

Dependencies:

- Used by `scheduling` and `staffing` for timezone-aware validation.

## patients

Responsibility:

- Patient demographics and patient profile aggregation.
- Patient search/list/detail/update.

Models:

- `Patient`

Main API endpoints:

- `/api/patients/`
- `/api/patients/{patientId}/`
- `/api/patients/{patientId}/appointments/`
- `/api/patients/{patientId}/visits/`
- `/api/patients/{patientId}/invoices/`
- `/api/patients/{patientId}/attachments/`

Services/validators:

- Patient demographic validation.
- Doctor patient scope checks.
- Patient profile aggregation.

Dependencies:

- Reads appointments from `scheduling`.
- Reads visits from `visits`.
- Reads invoices/payments from `billing`.
- Reads files and AI data from `attachments` and `ai_results`.

## staffing

Responsibility:

- Doctor/staff profiles.
- Recurring working shifts.
- Temporary availability exceptions/leave.

Models:

- `EmployeeProfile`
- `WorkingShift`
- `AvailabilityException`

Main API endpoints:

- `/api/employee-profiles/`
- `/api/employee-profiles/{id}/`
- `/api/employee-profiles/{id}/shifts/`
- `/api/employee-profiles/{id}/leave-exceptions/`
- `/api/working-shifts/`
- `/api/leave-exceptions/`

Services/validators:

- Shift overlap validation.
- Leave creation/update/cancel.
- Affected appointment detection.
- Marking affected appointments `Needs Reschedule`.

Dependencies:

- Uses `accounts.User`.
- Uses `clinic.ClinicSettings`.
- Calls `scheduling` services for affected appointments.

## scheduling

Responsibility:

- Appointment scheduling.
- Availability calculation.
- Appointment status transitions.
- Reschedule queue.
- Appointment audit logs.

Models:

- `Appointment`
- `AppointmentChangeLog`

Main API endpoints:

- `/api/appointments/`
- `/api/appointments/{id}/`
- `/api/appointments/{id}/check-in/`
- `/api/appointments/{id}/cancel/`
- `/api/appointments/{id}/no-show/`
- `/api/appointments/{id}/postpone/`
- `/api/appointments/{id}/start-visit/`
- `/api/appointments/{id}/reschedule/`
- `/api/appointments/reschedule-queue/`
- `/api/appointments/{id}/change-logs/`
- `/api/available-slots/`

Services/validators:

- Appointment availability validation.
- Same-doctor overlap validation.
- Clinic capacity validation.
- Shift coverage validation.
- Leave exception validation.
- Legal status transition enforcement.

Dependencies:

- Uses `patients.Patient`.
- Uses doctor profiles from `staffing`.
- Uses `clinic.ClinicSettings`.
- Starts visits through `visits.services`.

## visits

Responsibility:

- Clinical visit lifecycle.
- Doctor notes.
- Active visit ownership.
- Doctor treatment price/invoice handoff initiation.

Models:

- `Visit`

Main API endpoints:

- `/api/visits/start/`
- `/api/visits/active/`
- `/api/visits/{id}/`
- `/api/visits/{id}/notes/`
- `/api/visits/{id}/complete/`
- `/api/visits/{id}/invoice/`
- `/api/visits/{visitId}/attachments/`

Services/validators:

- Atomic start visit.
- Prevent more than one active visit per doctor.
- Save visit notes.
- Atomic complete visit.
- Validate doctor access to active visit.

Dependencies:

- Uses `scheduling.Appointment`.
- Uses `patients.Patient`.
- Uses doctor profiles from `staffing`.
- Calls `billing` for invoice handoff.
- Works with `attachments` and `ai_results`.

## billing

Responsibility:

- Invoices.
- Cash payments.
- Financial source of truth.
- Invoice status/balance calculation.

Models:

- `Invoice`
- `Payment`
- Optional `InvoiceTotalAdjustmentLog` if audit fields on `Invoice` are not enough.

Main API endpoints:

- `/api/invoices/`
- `/api/invoices/{id}/`
- `/api/invoices/{id}/payments/`
- `/api/invoices/{id}/cancel/`
- `/api/payments/`
- `/api/invoices/{id}/print/`
- `/api/invoices/{id}/export-pdf/`

Services/validators:

- Create invoice handoff from visit.
- Calculate paid amount.
- Calculate balance.
- Calculate invoice status.
- Edit invoice total before payment with audit reason.
- Process cash payment.
- Cancel invoice.

Dependencies:

- Uses `visits.Visit`.
- Uses `patients.Patient`.
- Uses doctor profiles from `staffing`.
- Uses `accounts.User` for `processedBy` and audit.

## attachments

Responsibility:

- X-ray/original file metadata.
- Upload/delete authorization.
- Private media URL generation.

Models:

- `Attachment`

Main API endpoints:

- `/api/visits/{visitId}/attachments/`
- `/api/attachments/{id}/`
- `/api/attachments/{id}/original-url/`

Services/validators:

- File type validation.
- File size validation.
- Authorized storage key/path generation.
- Authorized original image URL generation.

Dependencies:

- Uses `patients.Patient`.
- Uses `visits.Visit`.
- Uses `accounts.User`.
- Used by `ai_results`.

## ai_results

Responsibility:

- AI analysis run metadata.
- AI result summary.
- AI findings.
- Overlay metadata.
- Retry state.

Models:

- `AIResult`
- `AIResultFinding`

Main API endpoints:

- `/api/attachments/{id}/ai-results/`
- `/api/attachments/{id}/ai-result/`
- `/api/ai-results/{analysisId}/`
- `/api/ai-results/{analysisId}/findings/`
- `/api/ai-results/{analysisId}/overlay-url/`
- `/api/ai-results/{analysisId}/retry/`

Services/validators:

- Run/retry AI analysis.
- Store AI result state.
- Store findings.
- Generate authorized overlay URL.

Dependencies:

- Uses `attachments.Attachment`.
- Uses `visits.Visit` and doctor object scope.

Simplicity note:

- `attachments` and `ai_results` may be combined into one `clinical_media` app for a small first backend if the team wants fewer apps. Keeping them separate is recommended because file storage and AI processing have different responsibilities.
- `clinic` can stay small. It should not become a broad settings/reporting module in backend v1.

# 3. Data Model Specification

Naming recommendations:

- Database columns may use snake_case through Django defaults.
- API DTOs should be camelCase.
- Store UUID primary keys for externally exposed identifiers, or use integer IDs internally with stable public IDs. Pick one convention early and keep DTOs consistent.
- Use timezone-aware datetimes.

## User

Purpose:

- Auth identity, role authority, login status, and password setup state.

Fields:

- `id`: UUID or integer primary key.
- `fullName`: string, required.
- `username`: string, required, unique.
- `email`: email string, required, unique.
- `phone`: string, optional.
- `role`: enum string, `Admin`, `Staff`, or `Doctor`.
- `status`: enum string, `Active` or `Inactive`.
- `mustChangePassword`: boolean.
- Password hash fields from Django auth.
- `lastLogin`: datetime, nullable.
- `createdAt`: datetime.
- `updatedAt`: datetime recommended.

Field types:

- Extend Django `AbstractUser`.
- `role`: `CharField` with choices.
- `status`: `CharField` with choices.
- `mustChangePassword`: boolean.

Relationships:

- One-to-one optional `EmployeeProfile` for Staff/Doctor users.
- Referenced by audit fields such as `createdBy`, `changedBy`, `processedBy`, `uploadedBy`.

Indexes:

- Unique index on `username`.
- Unique index on `email`.
- Index on `role`.
- Index on `status`.

Constraints:

- `role` must be one of `Admin`, `Staff`, `Doctor`.
- Inactive users cannot authenticate.
- Email and username are unique.

Validation rules:

- New users require full name, username, email, role.
- Role changes are Admin-only.
- `mustChangePassword` should force password setup/change flow after login.

Audit fields:

- `createdAt`, `updatedAt`.
- Optional `createdBy` if user creation audit is required.

Versioning/optimistic locking behavior:

- Not required by locked scope, but useful for Admin user edits. If added, include `version` on user update endpoints.

Delete policy:

- Do not hard-delete active users. Use `status = Inactive`.

## EmployeeProfile

Purpose:

- Doctor/staff profile details and scheduling identity.

Fields:

- `id`: primary key.
- `user`: one-to-one nullable relation to `User`.
- `fullName`: string, required.
- `role`: enum string, `Doctor` or `Staff`.
- `specialty`: string, optional; mainly for Doctor.
- `position`: string, optional for Staff if needed.
- `gender`: enum string, `Male` or `Female`.
- `email`: email string.
- `phone`: string.
- `status`: enum string, `Active`, `Inactive`, or `On Leave`.
- `avatarUrl` or `avatarPath`: optional string.
- `createdAt`: datetime.
- `updatedAt`: datetime.
- `version`: integer.

Field types:

- `OneToOneField(User, null=True, blank=True)`.
- `CharField` with choices for role/status/gender.

Relationships:

- Has many `WorkingShift`.
- Has many `AvailabilityException`.
- Doctor profiles have many `Appointment`, `Visit`, and `Invoice`.

Indexes:

- Index on `role`.
- Index on `status`.
- Index on `user`.
- Optional unique `user` when present.

Constraints:

- `role` must be `Doctor` or `Staff`.
- `specialty` is optional, but recommended for Doctor display.

Validation rules:

- Cannot schedule appointments for inactive doctor profile.
- Staff and Doctor profiles may be listed together.

Audit fields:

- `createdAt`, `updatedAt`.
- Optional `createdBy`, `updatedBy`.

Versioning/optimistic locking behavior:

- Recommended. Update requests include `version`; stale update returns `409 Conflict`; success increments `version`.

Delete policy:

- Prefer `status = Inactive`. Hard delete only if no dependent operational data exists.

## Patient

Purpose:

- Demographic and administrative patient record.

Fields:

- `patientId`: primary/public identifier.
- `firstName`: string, required.
- `lastName`: string, required.
- `nationalIdOrPassport`: string/varchar, required.
- `dateOfBirth`: date, required.
- `gender`: enum string, `Male` or `Female`.
- `phoneNumber`: string, required.
- `email`: email string, optional.
- `medicalConditionsHistory`: text.
- `bloodGroup`: enum string, optional.
- `insuranceInfo`: text/string.
- `emergencyContact`: string.
- `address`: text/string.
- `createdAt`: datetime.
- `createdBy`: user relation, nullable.
- `updatedAt`: datetime.
- `version`: integer.

Field types:

- `CharField` for national ID/passport, never integer.
- `DateField` for date of birth.
- Text fields for longer notes.

Relationships:

- Has many `Appointment`.
- Has many `Visit`.
- Has many `Invoice`.
- Has many `Attachment`.

Indexes:

- Index on name fields for search.
- Index on `phoneNumber`.
- Unique or indexed `nationalIdOrPassport` recommended.

Constraints:

- `dateOfBirth` cannot be future.
- `gender` constrained.
- `bloodGroup` constrained if provided.

Validation rules:

- Age is calculated from `dateOfBirth`, not stored as source of truth.
- Staff can create/edit.
- Doctor can edit only scoped patients.
- Admin read-only.

Audit fields:

- `createdAt`, `createdBy`, `updatedAt`.

Versioning/optimistic locking behavior:

- Required. Update requests include `version`; stale update returns `409 Conflict`; success increments `version`.

Delete policy:

- No hard delete in v1. If needed later, add archival after policy review.

## ClinicSettings

Purpose:

- Clinic scheduling settings.

Fields:

- `id`: primary key.
- `clinicTimezone`: IANA timezone string, required.
- `maxSimultaneousAppointments`: positive integer.
- `createdAt`: datetime.
- `updatedAt`: datetime.
- `version`: integer.

Field types:

- `CharField` for timezone.
- `PositiveIntegerField` for capacity.

Relationships:

- Singleton or one active clinic row.

Indexes:

- Unique singleton constraint, such as `isActive = true` unique partial index, or enforce single row in service layer.

Constraints:

- `clinicTimezone` must be valid IANA timezone.
- `maxSimultaneousAppointments >= 1`.

Validation rules:

- Settings updates are Admin-only if exposed.
- Scheduling services must read settings through a single helper.

Audit fields:

- `createdAt`, `updatedAt`.
- Optional `updatedBy`.

Versioning/optimistic locking behavior:

- Recommended. Update requests include `version`; stale update returns `409 Conflict`.

Delete policy:

- Do not delete. Maintain one active settings row.

## WorkingShift

Purpose:

- Recurring weekly availability row for a Doctor or Staff profile.

Fields:

- `id`: primary key.
- `employeeProfile`: relation to `EmployeeProfile`.
- `dayOfWeek`: enum/integer weekday.
- `shiftName`: string, optional.
- `shiftIndex`: integer for display ordering.
- `startTime`: local clinic time.
- `endTime`: local clinic time.
- `isActive`: boolean preferred backend field.
- `createdAt`: datetime.
- `updatedAt`: datetime.
- `version`: integer.

Field types:

- `TimeField` for `startTime` and `endTime`.
- `BooleanField` for `isActive`.
- `CharField` or small integer for weekday.

Relationships:

- Belongs to `EmployeeProfile`.

Indexes:

- Composite index on `(employeeProfile, dayOfWeek)`.
- Optional composite index on `(employeeProfile, dayOfWeek, isActive)`.

Constraints:

- Active shifts require `startTime < endTime`.
- No overlapping active shifts for same person/day.
- `isActive = false` means the recurring row is disabled/closed.

Validation rules:

- Do not use `WorkingShift.isOnLeave` for one-time leave.
- One-time leave uses `AvailabilityException`.
- Shift times are clinic-local wall-clock times.

Audit fields:

- `createdAt`, `updatedAt`.
- Optional `createdBy`, `updatedBy`.

Versioning/optimistic locking behavior:

- Required. Update requests include `version`; stale update returns `409 Conflict`; success increments `version`.

Delete policy:

- Prefer disabling with `isActive = false`. Hard delete only if safe and audited.

## AvailabilityException

Purpose:

- Temporary one-time leave/block that affects availability.

Fields:

- `exceptionId`: primary/public identifier.
- `employeeProfile`: relation to Doctor/Staff profile.
- `userRole`: `Doctor` or `Staff`, optional denormalized display field.
- `startAt`: UTC datetime.
- `endAt`: UTC datetime.
- `reason`: enum string.
- `note`: text, optional.
- `status`: `Active` or `Cancelled`.
- `createdBy`: user relation.
- `createdAt`: datetime.
- `updatedAt`: datetime.
- `version`: integer.
- `cancelledAt`: datetime, nullable.
- `cancelledBy`: user relation, nullable.

Field types:

- Timezone-aware `DateTimeField` for `startAt`/`endAt`.
- `CharField` choices for reason/status.

Relationships:

- Belongs to `EmployeeProfile`.
- Created/cancelled by `User`.
- Affects appointments through service logic, not a direct required join table.

Indexes:

- Composite index on `(employeeProfile, status, startAt, endAt)`.
- Index on `startAt`.
- Index on `endAt`.

Constraints:

- `startAt < endAt`.
- Prevent overlapping active leave for same person unless product later allows it.

Validation rules:

- Does not mutate `WorkingShift`.
- Doctor leave overlapping Scheduled/Arrived/Checked-in/Needs Reschedule appointments marks them `Needs Reschedule`.
- Completed, Cancelled, and No-show appointments are ignored.
- Leave overlapping an `In Visit` appointment is rejected.
- Staff leave does not mark patient appointments.

Audit fields:

- `createdBy`, `createdAt`, `updatedAt`, `cancelledBy`, `cancelledAt`.

Versioning/optimistic locking behavior:

- Required. Update/cancel requests include `version`; stale update returns `409 Conflict`.

Delete policy:

- Do not delete. Use `status = Cancelled`.

## Appointment

Purpose:

- Scheduling record only. It is not a financial source of truth.

Fields:

- `id`: primary/public identifier.
- `patient`: relation to `Patient`.
- `doctor`: relation to Doctor `EmployeeProfile`.
- `visitType`: enum/string.
- `startAt`: UTC datetime.
- `endAt`: UTC datetime.
- `durationMinutes`: positive integer.
- `status`: enum string.
- `notes`: text, optional.
- `createdAt`: datetime.
- `createdBy`: user relation.
- `updatedAt`: datetime.
- `version`: integer.

Field types:

- Timezone-aware `DateTimeField` for `startAt`/`endAt`.
- `PositiveIntegerField` for duration.
- `CharField` choices for status/visit type.

Relationships:

- Belongs to `Patient`.
- Belongs to Doctor `EmployeeProfile`.
- Has one `Visit` after visit starts.
- Has many `AppointmentChangeLog`.

Indexes:

- Composite index on `(doctor, startAt, endAt)`.
- Index on `(status, startAt)`.
- Index on `(patient, startAt)`.

Constraints:

- `startAt < endAt`.
- `durationMinutes >= 15`.
- No same-doctor overlap for blocking statuses.
- Appointment must not store `due` or `dueAmount`.

Validation rules:

- Creation is Staff-only.
- Creation request must not accept status.
- New appointment defaults to `Scheduled`.
- Validate same-doctor overlap, shift coverage, leave exceptions, clinic capacity, and duration.
- Different doctors may be booked at the same time when clinic capacity allows.

Audit fields:

- `createdAt`, `createdBy`, `updatedAt`.

Versioning/optimistic locking behavior:

- Required. Update/status transition requests include `version`; stale update returns `409 Conflict`.

Delete policy:

- Do not hard delete. Use `Cancelled`, `No-show`, `Postponed`, or `Needs Reschedule` as appropriate.

## AppointmentChangeLog

Purpose:

- Immutable audit record for reschedules and status-sensitive schedule changes.

Fields:

- `logId`: primary/public identifier.
- `appointment`: relation to `Appointment`.
- `oldDoctor`: relation to Doctor profile, nullable.
- `newDoctor`: relation to Doctor profile, nullable.
- `oldStartAt`: UTC datetime, nullable.
- `oldEndAt`: UTC datetime, nullable.
- `newStartAt`: UTC datetime, nullable.
- `newEndAt`: UTC datetime, nullable.
- `oldStatus`: string, optional.
- `newStatus`: string, optional.
- `reason`: enum string.
- `note`: text, optional.
- `changedBy`: user relation.
- `changedAt`: datetime.

Field types:

- Timezone-aware datetimes.
- `CharField` choices for reason/status.

Relationships:

- Belongs to `Appointment`.
- References `User` for `changedBy`.

Indexes:

- Index on `appointment`.
- Index on `changedAt`.

Constraints:

- Immutable after creation.

Validation rules:

- Created by reschedule/status service.
- Not directly editable through generic CRUD.

Audit fields:

- Entire record is audit.

Versioning/optimistic locking behavior:

- Not needed because immutable.

Delete policy:

- Do not delete.

## Visit

Purpose:

- Clinical visit lifecycle and doctor-authored notes.

Fields:

- `id`: primary/public identifier.
- `appointment`: one-to-one relation to `Appointment`.
- `patient`: relation to `Patient`.
- `doctor`: relation to Doctor `EmployeeProfile`.
- `visitDate`: datetime, usually appointment start or start timestamp.
- `status`: `Active`, `Pending Notes`, or `Completed`.
- `symptomsChiefComplaint`: text.
- `clinicalNotes`: text.
- `diagnosisNotes`: text.
- `treatmentNotes`: text.
- `startedAt`: datetime.
- `completedAt`: datetime, nullable.
- `createdAt`: datetime.
- `updatedAt`: datetime.
- `version`: integer.

Field types:

- `OneToOneField(Appointment)`.
- Text fields for notes.
- `CharField` choices for status.

Relationships:

- Belongs to appointment, patient, doctor.
- Has attachments.
- May have one invoice.

Indexes:

- Index on `(doctor, status)`.
- Index on `patient`.
- Index on `appointment`.

Constraints:

- One active or pending-notes visit per doctor.
- Appointment must belong to same patient/doctor.

Validation rules:

- Doctor can start only own Checked-in appointment.
- Starting visit atomically creates/activates Visit and sets Appointment `In Visit`.
- Completing visit atomically saves notes, sets Visit `Completed`, and Appointment `Completed`.

Audit fields:

- `createdAt`, `updatedAt`, `startedAt`, `completedAt`.

Versioning/optimistic locking behavior:

- Required. Notes/complete requests include `version`; stale update returns `409 Conflict`.

Delete policy:

- Do not delete. Preserve clinical-operational history.

## Invoice

Purpose:

- Financial source of truth for amount owed and invoice state.

Fields:

- `id`: primary/public identifier.
- `visit`: relation to `Visit`.
- `patient`: relation to `Patient`.
- `doctor`: relation to Doctor profile.
- `invoiceDate`: date/datetime.
- `totalAmount`: decimal.
- `status`: `Pending`, `Partially Paid`, `Paid`, or `Cancelled`.
- `createdBy` or `submittedBy`: user relation.
- `createdAt`: datetime.
- `updatedAt`: datetime.
- `version`: integer.
- `cancelledAt`: datetime, nullable.
- `cancelledBy`: user relation, nullable.
- `cancelReason`: text, optional.
- `lastTotalEditReason`: text, optional.
- `lastTotalEditedBy`: user relation, nullable.
- `lastTotalEditedAt`: datetime, nullable.

Field types:

- `DecimalField` for `totalAmount`.
- `CharField` choices for status.

Relationships:

- Belongs to Visit, Patient, Doctor.
- Has many `Payment`.

Indexes:

- Index on `status`.
- Index on `invoiceDate`.
- Index on `patient`.
- Index on `doctor`.
- Unique invoice per visit recommended.

Constraints:

- `totalAmount > 0`.
- No services/items in backend v1.
- Cancelled invoice is terminal for edits/payments.

Validation rules:

- Created from Doctor treatment price/invoice handoff or by Staff.
- `paidAmount` and `balance` are calculated from payments.
- Total can be edited only before any payment exists.
- Total edit requires audit reason.
- Total cannot be edited after partial/full payment or cancellation.

Audit fields:

- `createdBy/submittedBy`, `createdAt`, `updatedAt`, cancellation fields, total edit audit fields.

Versioning/optimistic locking behavior:

- Required. Edit/payment/cancel requests include `version`; stale update returns `409 Conflict`.

Delete policy:

- Do not delete. Use `Cancelled`.

## Payment

Purpose:

- Cash payment record applied to an invoice.

Fields:

- `id`: primary/public identifier.
- `invoice`: relation to `Invoice`.
- `amountPaid`: decimal.
- `paymentMethod`: enum, `Cash`.
- `paymentDate`: date/datetime.
- `notes`: text, optional.
- `processedBy`: user relation.
- `createdAt`: datetime.

Field types:

- `DecimalField` for amount.
- `CharField` choices for method.

Relationships:

- Belongs to Invoice.
- Processed by Staff user.

Indexes:

- Index on `invoice`.
- Index on `paymentDate`.
- Index on `processedBy`.

Constraints:

- `amountPaid > 0`.
- `paymentMethod = Cash` in v1.

Validation rules:

- Staff-only.
- Payment cannot exceed remaining balance.
- Payment cannot be added to Cancelled invoice.
- Payment cannot be added if invoice is already Paid.

Audit fields:

- `processedBy`, `createdAt`, `paymentDate`.

Versioning/optimistic locking behavior:

- Payment is immutable after creation. The process payment request should include invoice `version` to guard against stale balance/status.

Delete policy:

- Do not delete or edit in v1. Use future adjustment policy if needed.

## Attachment

Purpose:

- Private X-ray/original uploaded file metadata.

Fields:

- `id`: primary/public identifier.
- `patient`: relation to `Patient`.
- `visit`: relation to `Visit`.
- `uploadedBy`: user relation.
- `fileName`: original file name.
- `fileType`: MIME type.
- `storageKey` or `filePath`: private storage path.
- `fileSize`: integer bytes.
- `uploadedAt`: datetime.
- `deletedAt`: datetime, nullable.
- `deletedBy`: user relation, nullable.

Field types:

- `CharField` for metadata.
- `PositiveIntegerField` for size.
- `DateTimeField`.

Relationships:

- Belongs to Patient and Visit.
- Has zero or more AI results, depending on retry/history policy.

Indexes:

- Index on `patient`.
- Index on `visit`.
- Index on `uploadedAt`.

Constraints:

- Accepted types: `image/png`, `image/jpeg`, `application/dicom`.
- Accepted extensions: `.png`, `.jpg`, `.jpeg`, `.dcm`.
- Max file size: 10 MB unless policy changes.

Validation rules:

- Validate file belongs to authorized visit/patient/doctor context.
- Doctor can upload/manage X-rays during active visit.
- Files and overlays must be private, not public static assets.

Audit fields:

- `uploadedBy`, `uploadedAt`, `deletedBy`, `deletedAt`.

Versioning/optimistic locking behavior:

- Not required for metadata in v1. Delete should be permission checked and audited.

Delete policy:

- Prefer soft delete or remove file with retained audit metadata.

## AIResult

Purpose:

- AI analysis result metadata and summary for an attachment.

Fields:

- `analysisId`: primary/public identifier.
- `attachment`: relation to `Attachment`.
- `resultSummary`: text.
- `overallConfidence`: decimal/float percentage.
- `processedDate`: datetime.
- `modelVersion`: string.
- `status`: `Pending`, `Processing`, `Completed`, or `Failed`.
- `overlayFilePath` or `overlayStorageKey`: private path.
- `errorMessage`: text, optional.
- `createdAt`: datetime.
- `updatedAt`: datetime.

Field types:

- `CharField` choices for status.
- Decimal or float for confidence.

Relationships:

- Belongs to Attachment.
- Has many `AIResultFinding`.

Indexes:

- Index on `attachment`.
- Index on `status`.
- Index on `processedDate`.

Constraints:

- AI output is support/educational/research only, not clinical diagnosis.
- `overallConfidence` between 0 and 1 or 0 and 100; pick one and document DTO conversion.

Validation rules:

- Doctor can run/review AI during active visit.
- Retry failed analysis only for authorized context.
- Store model version.

Audit fields:

- `createdAt`, `updatedAt`, `processedDate`.
- Optional `requestedBy`.

Versioning/optimistic locking behavior:

- Not required for UI edits because AI result is generated system data.

Delete policy:

- Do not hard delete while attachment exists unless attachment is deleted.

## AIResultFinding

Purpose:

- Individual AI finding displayed to support review.

Fields:

- `findingId`: primary/public identifier.
- `aiResult`: relation to `AIResult`.
- `fdiToothId`: string.
- `diseaseLabel`: enum string.
- `confidenceScore`: decimal/float.
- Optional future geometry fields if product later needs bounding boxes.

Field types:

- `CharField` for tooth and label.
- Decimal or float for confidence.

Relationships:

- Belongs to `AIResult`.

Indexes:

- Index on `aiResult`.
- Index on `diseaseLabel`.

Constraints:

- `confidenceScore` between 0 and 1 or 0 and 100, consistent with `AIResult`.

Validation rules:

- Finding label must be a support label, not diagnosis.

Audit fields:

- Inherited from `AIResult` generation context.

Versioning/optimistic locking behavior:

- Not required.

Delete policy:

- Delete only with parent AI result.

## PasswordResetToken

Purpose:

- Password setup/reset token lifecycle.

Fields:

- `id`: primary key.
- `user`: relation to `User`.
- `tokenHash`: string, never store raw token.
- `purpose`: `setup` or `reset`.
- `createdAt`: datetime.
- `expiresAt`: datetime.
- `usedAt`: datetime, nullable.
- `createdBy`: user relation, nullable for forgot password.

Field types:

- `CharField` for token hash/purpose.
- `DateTimeField` for lifecycle.

Relationships:

- Belongs to `User`.

Indexes:

- Index on `user`.
- Index on `tokenHash`.
- Index on `expiresAt`.

Constraints:

- Token can be used once.
- Expired token cannot be used.

Validation rules:

- Never log raw tokens.
- Reset/setup should set `mustChangePassword` appropriately.

Audit fields:

- `createdAt`, `createdBy`, `usedAt`.

Versioning/optimistic locking behavior:

- Not required.

Delete policy:

- Expired/used tokens can be periodically purged.

# 4. Enum and Status Specification

## Role

Values:

- `Admin`
- `Staff`
- `Doctor`

Models:

- `User`

Validation notes:

- Backend permissions are coded against this enum.
- Do not create editable role permission tables.

Frontend:

- Already uses these values.

## UserStatus

Values:

- `Active`
- `Inactive`

Models:

- `User`

Validation notes:

- Inactive users cannot authenticate.

Frontend:

- Already uses these values.

## ProfileStatus

Values:

- `Active`
- `Inactive`
- `On Leave`

Models:

- `EmployeeProfile`

Validation notes:

- `On Leave` is a profile status/display state, not a replacement for `AvailabilityException`.

Frontend:

- Already uses these values.

## AppointmentStatus

Values:

- `Scheduled`
- `Arrived`
- `Checked-in`
- `In Visit`
- `Completed`
- `Cancelled`
- `No-show`
- `Postponed`
- `Needs Reschedule`

Models:

- `Appointment`

Validation notes:

- Enforce legal transitions server-side.
- Blocking statuses for overlap should include `Scheduled`, `Arrived`, `Checked-in`, `In Visit`, and `Needs Reschedule`.

Frontend:

- Already uses these values.

## VisitStatus

Values:

- `Active`
- `Pending Notes`
- `Completed`

Models:

- `Visit`

Validation notes:

- Active or pending-notes visits count against one active visit per doctor.

Frontend:

- Already uses these values.

## InvoiceStatus

Values:

- `Pending`
- `Partially Paid`
- `Paid`
- `Cancelled`

Models:

- `Invoice`

Validation notes:

- `Pending`, `Partially Paid`, and `Paid` are calculated from payments.
- `Cancelled` is terminal for edits/payments.

Frontend:

- Already uses these values.

## PaymentMethod

Values:

- `Cash`

Models:

- `Payment`

Validation notes:

- Cash-only in backend v1.

Frontend:

- Already uses `Cash`.

## LeaveReason

Values:

- `Leave`
- `Sick Leave`
- `Personal`
- `Training`
- `Emergency`
- `Other`

Models:

- `AvailabilityException`

Validation notes:

- Use optional note for details.

Frontend:

- Already uses these values.

## LeaveStatus

Values:

- `Active`
- `Cancelled`

Models:

- `AvailabilityException`

Validation notes:

- Cancelled restores availability but does not auto-restore appointments from the reschedule queue.

Frontend:

- Already uses these values.

## AIStatus

Values:

- `Pending`
- `Processing`
- `Completed`
- `Failed`

Models:

- `AIResult`

Validation notes:

- Retry allowed from `Failed` for authorized users.

Frontend:

- Already uses these values.

## DiseaseLabel

Values:

- `Caries`
- `Deep Caries`
- `Impacted`
- `Periapical Lesion`

Models:

- `AIResultFinding`

Validation notes:

- Labels are support/research findings, not diagnosis.

Frontend:

- Already uses these values.

## Gender

Values:

- `Male`
- `Female`

Models:

- `Patient`
- `EmployeeProfile`

Validation notes:

- API field should be `gender`; UI may label it `Sex`.

Frontend:

- Already uses these values.

## BloodGroup

Values:

- `A+`
- `A-`
- `B+`
- `B-`
- `AB+`
- `AB-`
- `O+`
- `O-`

Models:

- `Patient`

Validation notes:

- Optional/nullable, constrained if provided.

Frontend:

- Already uses these values.

## Weekday

Values:

- `Monday`
- `Tuesday`
- `Wednesday`
- `Thursday`
- `Friday`
- `Saturday`
- `Sunday`

Models:

- `WorkingShift`

Validation notes:

- Can store as constrained string or integer plus display label.

Frontend:

- Already uses these labels.

## VisitType

Values:

- `Initial Consultation`
- `Routine Checkup`
- `Treatment Continuation`
- `Follow-up Visit`
- `Emergency Visit`
- `X-ray Review`
- `Post-treatment Review`
- `Cleaning Visit`

Models:

- `Appointment`

Validation notes:

- Treat as enum/string in v1. Do not add Services or ServiceCatalog.

Frontend:

- Already uses these values.

## RescheduleReason

Values:

- `Doctor on leave`
- `Patient requested reschedule`
- `Clinic schedule adjustment`
- `Other`

Models:

- `AppointmentChangeLog`

Validation notes:

- Required for reschedule audit.

Frontend:

- Already uses these values.

# 5. Permission and Authorization Design

Do not build editable RBAC. Backend permissions are coded directly from `User.role` plus object-level checks.

Doctor patient scope:

A Doctor can access/edit a patient only if at least one is true:

1. The patient has an appointment with that Doctor.
2. The patient has a visit with that Doctor.
3. The patient is currently in an active visit with that Doctor.

Admin read-only rule:

- Admin can view but not mutate patients, appointments, billing, invoices/payments, and clinical-operational records.
- Admin can manage users, employee profiles, working shifts, and leave exceptions.

| Action | Admin | Staff | Doctor | Object scope | Notes |
| --- | --- | --- | --- | --- | --- |
| Manage users | Yes | No | No | Global | Admin only. |
| Change user roles | Yes | No | No | Individual user view | Fixed roles only. |
| Manage employee profiles | Yes | Read-only if exposed | Own profile read/update if allowed | Profile | Doctor/Staff cannot manage others. |
| Manage working shifts | Yes | Read-only if exposed | Read-only own/profile | Employee profile | Backend uses `isActive`. |
| Manage leave exceptions | Yes | Read-only if exposed | Read-only own/profile | Employee profile | Admin create/update/cancel. |
| Create appointment | No | Yes | No | Global operational | Staff-only. |
| Edit/reschedule appointment | Read-only | Yes | No, except own start/continue flow | Appointment | Staff handles scheduling edits. |
| Check in patient | No | Yes | No | Appointment | Staff handles `Scheduled -> Arrived -> Checked-in`. |
| Start visit | No | No | Yes | Own Checked-in appointment | Atomically creates/activates Visit and sets appointment In Visit. |
| Complete visit | No | No | Yes | Own active visit | Atomically saves notes and completes visit/appointment. |
| Edit patient demographics | Read-only | Yes | Yes | Doctor scoped patient only | Doctor scope rule above. |
| Upload X-ray | Read-only if exposed | Optional read/manage if product allows | Yes | Own active visit | X-ray is support asset. |
| Run AI analysis | Read-only if exposed | Optional read only | Yes | Own active visit | Support/research only. |
| Create invoice handoff | No | Yes | Yes | Doctor own visit or Staff | Doctor enters treatment price/charge. |
| Edit invoice total | No | Yes | No | Invoice | Only before payment, audit reason required. |
| Process payment | No | Yes | No | Invoice | Cash only. |
| Cancel invoice | No | Yes | No | Invoice | Cancelled is terminal for edits/payments. |
| View billing | Read-only | Yes | Own visit status only if shown | Invoice/payment | Doctor cannot access global Billing. |
| View patient profile | Read-only | Yes | Scoped only | Patient | Doctor cannot browse unrelated/global patients. |

# 6. API Endpoint Specification

Use camelCase request/response fields. All update endpoints on versioned models must require `version` and return `409 Conflict` for stale updates.

## Auth

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/auth/login/` | Public | `LoginRequest` | `LoginResponse` | Active user, password valid | `accounts.services.login_user` | `401`, `FORBIDDEN_ROLE` if inactive |
| `POST` | `/api/auth/logout/` | Authenticated | None or refresh token | `{ ok: true }` | Token/session valid | `accounts.services.logout_user` | `401` |
| `POST` | `/api/auth/refresh/` | Refresh token | Refresh token/cookie | `TokenRefreshResponse` | Refresh valid and not revoked | `accounts.services.refresh_token` | `401` |
| `GET` | `/api/auth/me/` | Authenticated | None | `UserDTO` plus profile | User active | `accounts.services.get_current_user_context` | `401` |
| `POST` | `/api/auth/forgot-password/` | Public | `{ usernameOrEmail }` | `{ ok: true }` | User may exist, do not leak | `accounts.services.create_password_reset_token` | `400` |
| `POST` | `/api/auth/reset-password/` | Public | `{ token, newPassword }` | `{ ok: true }` | Token valid, unused, not expired | `accounts.services.reset_password` | `400`, `TOKEN_EXPIRED` |
| `POST` | `/api/auth/change-password/` | Authenticated | `{ currentPassword, newPassword }` | `{ ok: true }` | Current password valid | `accounts.services.change_password` | `400`, `401` |

## Users

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/users/` | Admin | Query search/role/status | `{ results: UserDTO[] }` | Admin only | `accounts.services.list_users` | `403` |
| `POST` | `/api/users/` | Admin | `CreateUserRequest` | `UserDTO` | Unique username/email, fixed role | `accounts.services.create_user` | `400`, `FORBIDDEN_ROLE` |
| `GET` | `/api/users/{id}/` | Admin | None | `UserDTO` | Admin only | `accounts.services.get_user` | `403`, `404` |
| `PATCH` | `/api/users/{id}/` | Admin | `UpdateUserRequest` | `UserDTO` | Role/status valid | `accounts.services.update_user` | `400`, `403` |
| `POST` | `/api/users/{id}/activate/` | Admin | None | `UserDTO` | User exists | `accounts.services.set_user_status` | `404` |
| `POST` | `/api/users/{id}/deactivate/` | Admin | None | `UserDTO` | User exists | `accounts.services.set_user_status` | `404` |
| `POST` | `/api/users/{id}/reset-password/` | Admin | Optional `{ mustChangePassword }` | `{ ok: true }` | User exists | `accounts.services.create_setup_token` | `404` |
| `GET` | `/api/roles/` | Admin | None | `RoleDTO[]` | Fixed roles only | `accounts.services.list_fixed_roles` | `403` |

## Clinic Settings

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/clinic-settings/` | Authenticated | None | `ClinicSettingsDTO` | Settings exists/bootstrap default | `clinic.services.get_settings` | `404` |
| `PATCH` | `/api/clinic-settings/timezone/` | Admin | `{ clinicTimezone, version }` | `ClinicSettingsDTO` | Valid IANA timezone, version | `clinic.services.update_timezone` | `400`, `409`, `INVALID_TIMEZONE` |
| `PATCH` | `/api/clinic-settings/capacity/` | Admin | `{ maxSimultaneousAppointments, version }` | `ClinicSettingsDTO` | Integer >= 1, version | `clinic.services.update_capacity` | `400`, `409` |

## Patients

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/patients/` | Staff, Admin read, Doctor scoped | Query search | `{ results: PatientDTO[] }` | Doctor sees only scoped patients | `patients.services.list_patients` | `403`, `PATIENT_SCOPE_DENIED` |
| `POST` | `/api/patients/` | Staff | `CreatePatientRequest` | `PatientDTO` | Required fields, DOB not future | `patients.services.create_patient` | `400` |
| `GET` | `/api/patients/{patientId}/` | Staff, Admin read, Doctor scoped | None | `PatientProfileDTO` | Object scope | `patients.services.get_patient_profile` | `403`, `404` |
| `PATCH` | `/api/patients/{patientId}/` | Staff, Doctor scoped | `UpdatePatientRequest` plus `version` | `PatientDTO` | Version, object scope | `patients.services.update_patient` | `400`, `403`, `409` |
| `GET` | `/api/patients/{patientId}/appointments/` | Staff, Admin read, Doctor scoped | None | `AppointmentDTO[]` | Object scope | `patients.services.list_patient_appointments` | `403` |
| `GET` | `/api/patients/{patientId}/visits/` | Staff, Admin read, Doctor scoped | None | `VisitDTO[]` | Object scope | `patients.services.list_patient_visits` | `403` |
| `GET` | `/api/patients/{patientId}/invoices/` | Staff, Admin read, Doctor own context only | None | `InvoiceDTO[]` | Billing scope | `patients.services.list_patient_invoices` | `403` |
| `GET` | `/api/patients/{patientId}/attachments/` | Staff read, Admin read, Doctor scoped | None | `AttachmentDTO[]` plus AI | Object scope | `patients.services.list_patient_attachments` | `403` |

## Employee profiles

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/employee-profiles/` | Admin, Staff read, Doctor limited | Query role/status | `{ results: EmployeeProfileDTO[] }` | Role filters valid | `staffing.services.list_profiles` | `403` |
| `POST` | `/api/employee-profiles/` | Admin | `CreateEmployeeProfileRequest` | `EmployeeProfileDTO` | Role Doctor/Staff | `staffing.services.create_profile` | `400` |
| `GET` | `/api/employee-profiles/{id}/` | Admin, Staff read, Doctor own | None | `EmployeeProfileDTO` | Object scope | `staffing.services.get_profile` | `403`, `404` |
| `PATCH` | `/api/employee-profiles/{id}/` | Admin, Doctor own limited | `UpdateEmployeeProfileRequest` plus `version` | `EmployeeProfileDTO` | Version, allowed fields | `staffing.services.update_profile` | `400`, `403`, `409` |
| `GET` | `/api/employee-profiles/{id}/shifts/` | Admin, Staff read, Doctor own | None | `WorkingShiftDTO[]` | Object scope | `staffing.services.list_profile_shifts` | `403` |
| `GET` | `/api/employee-profiles/{id}/leave-exceptions/` | Admin, Staff read, Doctor own | Query status/date | `AvailabilityExceptionDTO[]` | Object scope | `staffing.leave_services.list_leave` | `403` |

## Working shifts

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/working-shifts/` | Admin | `CreateWorkingShiftRequest` | `WorkingShiftDTO` | No overlapping active shift | `staffing.shift_services.create_shift` | `400`, `DOCTOR_NOT_AVAILABLE` |
| `PATCH` | `/api/working-shifts/{id}/` | Admin | `UpdateWorkingShiftRequest` plus `version` | `WorkingShiftDTO` | Version, no overlap | `staffing.shift_services.update_shift` | `400`, `409` |
| `PUT` | `/api/employee-profiles/{id}/shifts/` | Admin | `{ shifts, version? }` | `WorkingShiftDTO[]` | Bulk validation before save | `staffing.shift_services.bulk_replace_shifts` | `400`, `409` |
| `POST` | `/api/working-shifts/{id}/disable/` | Admin | `{ version }` | `WorkingShiftDTO` | Version | `staffing.shift_services.disable_shift` | `409` |
| `POST` | `/api/working-shifts/validate/` | Admin | Shift draft | `{ valid, errors }` | Overlap/time rules | `staffing.shift_services.validate_shift` | `400` |

## Leave exceptions

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/leave-exceptions/` | Admin, Staff read, Doctor own | Query | `AvailabilityExceptionDTO[]` | Object scope | `staffing.leave_services.list_leave` | `403` |
| `POST` | `/api/leave-exceptions/` | Admin | `CreateLeaveExceptionRequest` | `AvailabilityExceptionDTO` plus affected count | UTC range, no In Visit overlap | `staffing.leave_services.create_leave` | `400`, `LEAVE_OVERLAPS_IN_VISIT` |
| `PATCH` | `/api/leave-exceptions/{exceptionId}/` | Admin | `UpdateLeaveExceptionRequest` plus `version` | `AvailabilityExceptionDTO` plus affected count | Version, re-evaluate affected appointments | `staffing.leave_services.update_leave` | `400`, `409` |
| `POST` | `/api/leave-exceptions/{exceptionId}/cancel/` | Admin | `{ version, note? }` | `AvailabilityExceptionDTO` | Version, queue not auto-restored | `staffing.leave_services.cancel_leave` | `409` |
| `POST` | `/api/leave-exceptions/preview/` | Admin | Leave draft | `{ affectedAppointments }` | UTC range | `staffing.leave_services.preview_affected_appointments` | `400` |

## Appointments

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/appointments/` | Admin read, Staff, Doctor own | Query date/range/doctor/status | `AppointmentDTO[]` | Doctor only own | `scheduling.services.list_appointments` | `403` |
| `POST` | `/api/appointments/` | Staff | `CreateAppointmentRequest` | `AppointmentDTO` | No status, availability validation | `scheduling.services.create_appointment` | `400`, `APPOINTMENT_CONFLICT`, `CLINIC_CAPACITY_REACHED` |
| `GET` | `/api/appointments/{id}/` | Admin read, Staff, Doctor own | None | `AppointmentDTO` | Object scope | `scheduling.services.get_appointment` | `403`, `404` |
| `PATCH` | `/api/appointments/{id}/` | Staff | `UpdateAppointmentRequest` plus `version` | `AppointmentDTO` | Version, availability | `scheduling.services.update_appointment` | `400`, `409` |
| `POST` | `/api/appointments/{id}/check-in/` | Staff | `{ version }` | `AppointmentDTO` | Scheduled/Arrived to Checked-in | `scheduling.transitions.check_in` | `400`, `409` |
| `POST` | `/api/appointments/{id}/cancel/` | Staff | `{ reason?, version }` | `AppointmentDTO` | Legal status | `scheduling.transitions.cancel` | `400`, `409` |
| `POST` | `/api/appointments/{id}/no-show/` | Staff | `{ note?, version }` | `AppointmentDTO` | Legal status | `scheduling.transitions.no_show` | `400`, `409` |
| `POST` | `/api/appointments/{id}/postpone/` | Staff | `{ reason?, version }` | `AppointmentDTO` | Legal status | `scheduling.transitions.postpone` | `400`, `409` |
| `POST` | `/api/appointments/{id}/start-visit/` | Doctor own | `{ version }` | `{ appointment, visit }` | Appointment must be own and Checked-in | `visits.services.start_visit_from_appointment` | `400`, `403`, `409` |
| `POST` | `/api/appointments/{id}/reschedule/` | Staff | `RescheduleAppointmentRequest` | `{ appointment, changeLog }` | Availability, reason, version | `scheduling.services.reschedule_appointment` | `400`, `409` |
| `GET` | `/api/appointments/reschedule-queue/` | Admin read, Staff | Query | `AppointmentDTO[]` | Only `Needs Reschedule` | `scheduling.services.list_reschedule_queue` | `403` |
| `GET` | `/api/appointments/{id}/change-logs/` | Admin read, Staff, Doctor own | None | `AppointmentChangeLogDTO[]` | Object scope | `scheduling.services.list_change_logs` | `403` |
| `GET` | `/api/available-slots/` | Admin read, Staff | Query doctor/date/duration | `AvailableSlotDTO[]` | UTC + clinic timezone rules | `scheduling.availability.calculate_available_slots` | `400`, `INVALID_TIMEZONE` |

## Visits

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/visits/start/` | Doctor own | `{ appointmentId, version }` | `{ appointment, visit }` | Checked-in only, one active visit | `visits.services.start_visit` | `400`, `403`, `409` |
| `GET` | `/api/visits/active/` | Doctor | Optional `appointmentId` | `VisitDTO` | Own active visit | `visits.services.get_active_visit` | `404` |
| `GET` | `/api/visits/{id}/` | Staff read, Admin read, Doctor own | None | `VisitDTO` | Object scope | `visits.services.get_visit` | `403`, `404` |
| `PATCH` | `/api/visits/{id}/notes/` | Doctor own | `UpdateVisitNotesRequest` plus `version` | `VisitDTO` | Version | `visits.services.save_notes` | `400`, `409` |
| `POST` | `/api/visits/{id}/complete/` | Doctor own | `UpdateVisitNotesRequest` plus `version` | `{ visit, appointment }` | Atomic complete | `visits.services.complete_visit` | `400`, `409` |
| `GET` | `/api/visits/` | Staff/Admin read, Doctor own | Query patient/doctor/status | `VisitDTO[]` | Object scope | `visits.services.list_visits` | `403` |

## Billing

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/invoices/` | Admin read, Staff | Query search/status/date | `InvoiceDTO[]` | Doctor not global | `billing.services.list_invoices` | `403` |
| `GET` | `/api/invoices/{id}/` | Admin read, Staff, Doctor own context | None | `InvoiceDTO` plus payments if allowed | Scope | `billing.services.get_invoice` | `403`, `404` |
| `POST` | `/api/visits/{visitId}/invoice/` | Doctor own, Staff | `{ treatmentDescription?, totalAmount, internalNote? }` | `InvoiceDTO` | Total > 0, visit scope | `billing.services.create_invoice_handoff` | `400`, `403` |
| `PATCH` | `/api/invoices/{id}/` | Staff | `UpdateInvoiceTotalRequest` | `InvoiceDTO` | No payments, not Cancelled, audit reason, version | `billing.services.edit_invoice_total` | `400`, `409`, `INVOICE_CANCELLED`, `INVOICE_ALREADY_PAID` |
| `POST` | `/api/invoices/{id}/cancel/` | Staff | `{ reason?, version }` | `InvoiceDTO` | Pending/unpaid only, not already terminal, version | `billing.services.cancel_invoice` | `400`, `409` |
| `GET` | `/api/invoices/{id}/payments/` | Staff, Admin read | None | `PaymentDTO[]` | Scope | `billing.services.list_payments` | `403` |
| `GET` | `/api/payments/` | Staff, Admin read | Query invoice/patient/date | `PaymentDTO[]` | Scope | `billing.services.list_payments` | `403` |
| `POST` | `/api/payments/` | Staff | `ProcessPaymentRequest` with invoiceId | `{ invoice, payment }` | Cash, amount <= balance, invoice version | `billing.services.process_cash_payment` | `400`, `409`, `PAYMENT_EXCEEDS_BALANCE` |
| `GET` | `/api/invoices/{id}/print/` | Staff, Admin read | None | printable payload | Cancelled allowed | `billing.services.get_print_payload` | `403` |
| `GET` | `/api/invoices/{id}/export-pdf/` | Staff, Admin read | None | file response or placeholder | Cancelled allowed | `billing.services.export_pdf_placeholder` | `403` |

## Attachments/X-rays

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/visits/{visitId}/attachments/` | Doctor own active visit | Multipart file | `AttachmentDTO` | Type, size, visit scope | `attachments.services.upload_attachment` | `400`, `403`, `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE` |
| `GET` | `/api/visits/{visitId}/attachments/` | Doctor own, Staff/Admin read | None | `AttachmentDTO[]` | Scope | `attachments.services.list_visit_attachments` | `403` |
| `DELETE` | `/api/attachments/{id}/` | Doctor own/uploader, Staff if allowed | None | `{ ok: true }` | Scope, audit | `attachments.services.delete_attachment` | `403`, `404` |
| `GET` | `/api/attachments/{id}/original-url/` | Authorized | None | `{ url, expiresAt }` | Scope | `attachments.services.get_original_url` | `403`, `404` |

## AI

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/attachments/{id}/ai-results/` | Doctor own active visit | Optional `{ modelVersion }` | `AIResultDTO` | Attachment scope | `ai_results.services.run_analysis` | `400`, `403` |
| `GET` | `/api/attachments/{id}/ai-result/` | Doctor own, Staff/Admin read | None | `AIResultDTO` | Scope | `ai_results.services.get_result_for_attachment` | `403`, `404` |
| `GET` | `/api/ai-results/{analysisId}/` | Authorized | None | `AIResultDTO` | Scope | `ai_results.services.get_result` | `403`, `404` |
| `GET` | `/api/ai-results/{analysisId}/findings/` | Authorized | None | `AIResultFindingDTO[]` | Scope | `ai_results.services.get_findings` | `403` |
| `GET` | `/api/ai-results/{analysisId}/overlay-url/` | Authorized | None | `{ url, expiresAt }` | Scope | `ai_results.services.get_overlay_url` | `403`, `404` |
| `POST` | `/api/ai-results/{analysisId}/retry/` | Doctor own active visit | Optional `{ modelVersion }` | `AIResultDTO` | Failed or retryable | `ai_results.services.retry_analysis` | `400`, `403` |

## Settings/Profile

| Method | Endpoint | Permission | Request DTO | Response DTO | Validation | Service function used | Important errors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/profile/` | Authenticated | None | `{ user, employeeProfile? }` | User active | `accounts.services.get_own_profile` | `401` |
| `PATCH` | `/api/profile/` | Authenticated | Own allowed fields plus `version` if profile update | `EmployeeProfileDTO` | Allowed own fields only | `accounts.services.update_own_profile` | `400`, `403`, `409` |
| `POST` | `/api/profile/change-password/` | Authenticated | `{ currentPassword, newPassword }` | `{ ok: true }` | Current password valid | `accounts.services.change_password` | `400` |

# 7. DTO Specification

DTOs should be frontend-facing and camelCase. Internal model fields can remain Django/Python style.

## UserDTO

Source model:

- `User`

Fields:

- `id`
- `fullName`
- `username`
- `email`
- `phone`
- `role`
- `status`
- `createdAt`
- `mustChangePassword`

Calculated fields:

- None required.

Intentionally omitted:

- Password hash.
- Token data.
- Permission matrix.

## EmployeeProfileDTO

Source model:

- `EmployeeProfile`

Fields:

- `id`
- `userId`
- `fullName`
- `role`
- `specialty`
- `gender`
- `email`
- `phone`
- `status`
- `avatarUrl`
- `updatedAt`
- `version`

Calculated fields:

- Optional display schedule summaries later.

Intentionally omitted:

- Internal audit fields unless needed.

## PatientDTO

Source model:

- `Patient`

Fields:

- `patientId`
- `firstName`
- `lastName`
- `nationalIdOrPassport`
- `dateOfBirth`
- `gender`
- `phoneNumber`
- `medicalConditionsHistory`
- `bloodGroup`
- `insuranceInfo`
- `emergencyContact`
- `address`
- `createdAt`
- `updatedAt`
- `version`
- `email`
- `age`

Calculated fields:

- `age`, calculated from `dateOfBirth`.

Intentionally omitted:

- Appointment `due` or financial balance.

## PatientProfileDTO

Source models:

- `Patient`
- `Appointment`
- `Visit`
- `Invoice`
- `Attachment`
- `AIResult`

Fields:

- All `PatientDTO` fields.
- `visits`
- `appointments`
- `invoices`
- `attachments`

Calculated fields:

- Nested aggregates are permission-filtered.

Intentionally omitted:

- Unrelated Doctor/global clinic data.

## ClinicSettingsDTO

Source model:

- `ClinicSettings`

Fields:

- `clinicTimezone`
- `maxSimultaneousAppointments`
- `updatedAt`
- `version`

Calculated fields:

- None required.

Intentionally omitted:

- Any dashboard/report settings.

## WorkingShiftDTO

Source model:

- `WorkingShift`

Fields:

- `id`
- `staffOrDoctorId`
- `dayOfWeek`
- `shiftName`
- `shiftIndex`
- `startTime`
- `endTime`
- `isActive`
- `updatedAt`
- `version`

Calculated fields:

- Optional display label.

Intentionally omitted:

- `isOnLeave` as backend source field.

## AvailabilityExceptionDTO

Source model:

- `AvailabilityException`

Fields:

- `exceptionId`
- `userId`
- `userRole`
- `startAt`
- `endAt`
- `reason`
- `note`
- `status`
- `createdBy`
- `createdAt`
- `updatedAt`
- `version`
- `affectedAppointmentCount`

Calculated fields:

- `affectedAppointmentCount`.

Intentionally omitted:

- Automatic restoration state. Cancelling leave does not auto-restore appointments.

## AppointmentDTO

Source model:

- `Appointment`

Fields:

- `id`
- `patientId`
- `doctorId`
- `visitType`
- `startAt`
- `endAt`
- `date`
- `time`
- `durationMinutes`
- `status`
- `notes`
- `updatedAt`
- `version`

Calculated fields:

- `date` and `time` are optional clinic-local display fields derived from UTC `startAt`/`endAt`.

Intentionally omitted:

- `due`
- `dueAmount`
- Any invoice balance.

## AppointmentChangeLogDTO

Source model:

- `AppointmentChangeLog`

Fields:

- `logId`
- `appointmentId`
- `oldDoctorId`
- `newDoctorId`
- `oldStartAt`
- `oldEndAt`
- `newStartAt`
- `newEndAt`
- `oldStatus`
- `newStatus`
- `reason`
- `note`
- `changedBy`
- `changedAt`

Calculated fields:

- Optional display names for doctor/user if useful.

Intentionally omitted:

- Edit fields; immutable audit record.

## VisitDTO

Source model:

- `Visit`

Fields:

- `id`
- `appointmentId`
- `patientId`
- `doctorId`
- `visitDate`
- `symptomsChiefComplaint`
- `clinicalNotes`
- `diagnosisNotes`
- `treatmentNotes`
- `status`
- `updatedAt`
- `version`

Calculated fields:

- Optional linked appointment/patient summaries.

Intentionally omitted:

- Payment processing fields.

## InvoiceDTO

Source model:

- `Invoice`
- `Payment`

Fields:

- `id`
- `patientId`
- `visitId`
- `doctorId`
- `invoiceDate`
- `totalAmount`
- `paidAmount`
- `balance`
- `status`
- `updatedAt`
- `version`

Calculated fields:

- `paidAmount`, calculated from payments.
- `balance`, calculated as total minus payments.
- Status from payments unless Cancelled.

Intentionally omitted:

- Services/items.
- Editable accounting ledger details.

## PaymentDTO

Source model:

- `Payment`

Fields:

- `id`
- `invoiceId`
- `amountPaid`
- `paymentMethod`
- `paymentDate`
- `notes`
- `processedBy`
- `createdAt`

Calculated fields:

- Optional processedBy display name.

Intentionally omitted:

- Edit/delete controls.

## AttachmentDTO

Source model:

- `Attachment`

Fields:

- `id`
- `patientId`
- `visitId`
- `filePath`
- `fileName`
- `fileType`
- `fileSize`
- `uploadedBy`
- `uploadedAt`
- `originalUrl`

Calculated fields:

- `originalUrl` should be authorized and short-lived if returned.

Intentionally omitted:

- Public storage details.

## AIResultDTO

Source model:

- `AIResult`

Fields:

- `analysisId`
- `fileId`
- `resultSummary`
- `overallConfidence`
- `processedDate`
- `modelVersion`
- `status`
- `overlayFilePath`
- `overlayUrl`

Calculated fields:

- `overlayUrl`, authorized and short-lived.

Intentionally omitted:

- Diagnosis conclusions.

## AIResultFindingDTO

Source model:

- `AIResultFinding`

Fields:

- `findingId`
- `analysisId`
- `fdiToothId`
- `diseaseLabel`
- `confidenceScore`

Calculated fields:

- None required.

Intentionally omitted:

- Bounding box/geometry until a later product decision.

# 8. Service Layer Design

Keep complex business logic out of views. DRF views/viewsets should parse input, run permissions, call services, serialize output, and map exceptions to consistent errors.

## accounts/services.py

Functions:

- `login_user(username_or_email, password)`
- `logout_user(user, token_context)`
- `refresh_token(refresh_token)`
- `get_current_user_context(user)`
- `create_user(data, actor)`
- `update_user(user_id, data, actor)`
- `set_user_status(user_id, status, actor)`
- `create_password_reset_token(username_or_email)`
- `create_setup_token(user_id, actor)`
- `reset_password(token, new_password)`
- `change_password(user, current_password, new_password)`
- `list_fixed_roles()`

Responsibilities:

- Auth lifecycle.
- Password reset/setup.
- Role/status validation.
- No editable RBAC.

## clinic/services.py

Functions:

- `get_settings()`
- `ensure_default_settings()`
- `update_timezone(clinic_timezone, version, actor)`
- `update_capacity(max_simultaneous_appointments, version, actor)`
- `validate_iana_timezone(value)`

Responsibilities:

- Singleton settings.
- Versioned settings updates.
- Timezone validation.

## scheduling/availability.py

Functions:

- `calculate_available_slots(date, duration_minutes, doctor_id=None)`
- `validate_same_doctor_overlap(doctor, start_at, end_at, exclude_appointment_id=None)`
- `validate_clinic_capacity(start_at, end_at, exclude_appointment_id=None)`
- `validate_shift_coverage(doctor, start_at, end_at)`
- `validate_leave_exceptions(doctor, start_at, end_at)`
- `validate_duration(duration_minutes, start_at, end_at)`

Responsibilities:

- Scheduling validation using UTC datetimes plus clinic timezone.
- Clinic capacity and doctor availability.

## scheduling/transitions.py

Functions:

- `mark_arrived(appointment, actor, version)`
- `check_in(appointment, actor, version)`
- `cancel(appointment, actor, reason, version)`
- `no_show(appointment, actor, note, version)`
- `postpone(appointment, actor, reason, version)`
- `reschedule(appointment, data, actor, version)`
- `start_visit(appointment, doctor_user, version)`

Responsibilities:

- Legal appointment status transitions.
- AppointmentChangeLog creation.
- Rejection of invalid transitions.

## scheduling/services.py

Functions:

- `list_appointments(filters, actor)`
- `create_appointment(data, actor)`
- `get_appointment(appointment_id, actor)`
- `update_appointment(appointment_id, data, actor)`
- `reschedule_appointment(appointment_id, data, actor)`
- `list_reschedule_queue(actor, filters)`
- `list_change_logs(appointment_id, actor)`

Responsibilities:

- Appointment CRUD-like orchestration.
- Call availability and transitions services.

## staffing/shift_services.py

Functions:

- `create_shift(data, actor)`
- `update_shift(shift_id, data, version, actor)`
- `bulk_replace_shifts(employee_profile_id, shifts, actor)`
- `disable_shift(shift_id, version, actor)`
- `validate_shift(data, exclude_shift_id=None)`
- `detect_shift_overlap(employee_profile, day_of_week, start_time, end_time, exclude_shift_id=None)`

Responsibilities:

- Recurring shift validation.
- `WorkingShift.isActive` semantics.

## staffing/leave_services.py

Functions:

- `create_leave(data, actor)`
- `update_leave(exception_id, data, version, actor)`
- `cancel_leave(exception_id, version, actor, note=None)`
- `preview_affected_appointments(data, actor)`
- `detect_affected_appointments(employee_profile, start_at, end_at)`
- `mark_affected_appointments_needs_reschedule(appointments, actor)`
- `validate_leave_not_in_visit(employee_profile, start_at, end_at)`

Responsibilities:

- Temporary leave/block lifecycle.
- Does not mutate recurring shifts.
- Marks affected appointments `Needs Reschedule`.

## visits/services.py

Functions:

- `start_visit(appointment_id, doctor_user, version)`
- `start_visit_from_appointment(appointment, doctor_user, version)`
- `get_active_visit(doctor_user, appointment_id=None)`
- `get_visit(visit_id, actor)`
- `list_visits(filters, actor)`
- `save_notes(visit_id, data, version, actor)`
- `complete_visit(visit_id, data, version, actor)`
- `assert_doctor_owns_visit(visit, doctor_user)`
- `assert_no_other_active_visit(doctor_profile)`

Responsibilities:

- Atomic visit start/complete.
- One active visit per doctor.
- Doctor-owned notes.

## billing/services.py

Functions:

- `create_invoice_handoff(visit_id, data, actor)`
- `list_invoices(filters, actor)`
- `get_invoice(invoice_id, actor)`
- `calculate_paid_amount(invoice)`
- `calculate_balance(invoice)`
- `calculate_invoice_status(invoice)`
- `edit_invoice_total(invoice_id, total_amount, audit_reason, version, actor)`
- `process_cash_payment(invoice_id, amount_paid, payment_date, notes, version, actor)`
- `cancel_invoice(invoice_id, reason, version, actor)`
- `list_payments(filters, actor)`
- `get_print_payload(invoice_id, actor)`
- `export_pdf_placeholder(invoice_id, actor)`

Responsibilities:

- Invoice/payment financial truth.
- Cash payment only.
- Cancelled invoice protection.
- Total edit before payment only.

## attachments/services.py

Functions:

- `upload_attachment(visit_id, file, actor)`
- `list_visit_attachments(visit_id, actor)`
- `delete_attachment(attachment_id, actor)`
- `get_authorized_original_url(attachment_id, actor)`
- `validate_file_type(file)`
- `validate_file_size(file)`
- `build_storage_key(file, visit)`

Responsibilities:

- Private file metadata.
- File validation.
- Authorization for original image access.

## ai_results/services.py

Functions:

- `run_analysis(attachment_id, actor, model_version=None)`
- `retry_analysis(analysis_id, actor, model_version=None)`
- `get_result(analysis_id, actor)`
- `get_result_for_attachment(attachment_id, actor)`
- `get_findings(analysis_id, actor)`
- `get_overlay_url(analysis_id, actor)`
- `store_result(attachment, result_payload)`
- `store_findings(ai_result, findings_payload)`

Responsibilities:

- AI result/finding state.
- Overlay access.
- Support/research labeling.

## common optimistic locking helper

Suggested location:

- `common/locking.py` or a shared utility module.

Functions:

- `check_version(instance, request_version)`
- `increment_version(instance)`
- `save_with_version(instance, request_version, update_fields=None)`

Responsibilities:

- Compare request version to database version.
- Raise conflict exception on mismatch.
- Increment version and update `updatedAt` on success.

## timezone service

Suggested location:

- `clinic/timezone_services.py` or `scheduling/timezone.py`.

Functions:

- `validate_iana_timezone(value)`
- `parse_utc_datetime(value)`
- `clinic_local_to_utc(local_date, local_time, timezone)`
- `utc_to_clinic_display(dt, timezone)`
- `derive_appointment_display_fields(start_at, end_at)`

Responsibilities:

- No browser-local scheduling authority.
- UTC storage and clinic-local display.

# 9. Status Transition Rules

## Appointment transitions

| From | To | Role | Service | Notes |
| --- | --- | --- | --- | --- |
| `Scheduled` | `Arrived` | Staff | `mark_arrived` | Reception arrival. |
| `Arrived` | `Checked-in` | Staff | `check_in` | Ready for doctor. |
| `Checked-in` | `In Visit` | Doctor own only | `start_visit` | Atomic Visit create/activate. |
| `In Visit` | `Completed` | Doctor own only | `complete_visit` | Atomic visit/appointment complete. |
| `Scheduled`/`Arrived`/`Checked-in` | `Cancelled` | Staff | `cancel` | Operational cancellation. |
| `Scheduled`/`Arrived`/`Checked-in` | `No-show` | Staff | `no_show` | Operational no-show. |
| `Scheduled`/`Arrived`/`Checked-in`/`Needs Reschedule` | `Needs Reschedule` | System/Admin leave service | `mark_affected_appointments_needs_reschedule` | Due to Doctor leave. |
| `Needs Reschedule` | `Scheduled` | Staff | `reschedule` | Valid new slot required. |
| `Scheduled`/`Arrived`/`Checked-in` | `Postponed` | Staff | `postpone` | Supported because frontend enum exists. |

Explicitly reject:

- Doctor starting from `Arrived`.
- Doctor starting another doctor's appointment.
- Admin mutating appointment status.
- Starting visit when doctor already has active/pending-notes visit.
- Creating appointment with client-supplied status.

## Visit transitions

| From | To | Role | Service | Notes |
| --- | --- | --- | --- | --- |
| None | `Active` | Doctor own | `start_visit` | Created/activated on appointment start. |
| `Active` | `Pending Notes` | Doctor own | `save_notes` | Optional if save-draft policy uses it. |
| `Active` | `Completed` | Doctor own | `complete_visit` | Save notes and complete appointment. |
| `Pending Notes` | `Completed` | Doctor own | `complete_visit` | Save final notes and complete. |

## Invoice transitions

| From | To | Role | Service | Notes |
| --- | --- | --- | --- | --- |
| None | `Pending` | Doctor own or Staff | `create_invoice_handoff` | Created from treatment price/charge. |
| `Pending` | `Partially Paid` | Staff | `process_cash_payment` | Calculated from payments. |
| `Pending` | `Paid` | Staff | `process_cash_payment` | Full payment. |
| `Partially Paid` | `Paid` | Staff | `process_cash_payment` | Remaining balance paid. |
| `Pending` | `Cancelled` | Staff | `cancel_invoice` | Editable unpaid invoice can be cancelled. |

Cancelled is terminal for edits/payments unless explicit restore policy is added later.

# 10. Timezone and Scheduling Design

Rules:

- Store appointment source datetimes as UTC `startAt` and `endAt`.
- Store leave source datetimes as UTC `startAt` and `endAt`.
- `ClinicSettings.clinicTimezone` is required.
- `clinicTimezone` must be an IANA timezone name.
- Scheduling authority uses clinic timezone, not browser local timezone.
- Working shift `startTime` and `endTime` are clinic-local wall-clock times.

Recommended request strategy:

- API create/update requests should accept UTC ISO `startAt` and `endAt`.
- Backend validates these UTC timestamps against clinic timezone, shifts, leave, capacity, and duration.
- Backend may return derived clinic-local display fields such as `date`, `time`, and formatted labels.

Reason:

- UTC request fields keep the API unambiguous.
- The frontend can later adapt date/time controls into UTC before sending.
- Backend remains the scheduling authority and validates against clinic timezone.

Appointment creation:

- Parse `startAt` and `endAt` as timezone-aware UTC.
- Validate `startAt < endAt`.
- Validate `durationMinutes` matches interval.
- Convert interval to clinic local time for shift coverage checks.
- Validate same-doctor overlap using UTC.
- Validate clinic capacity using UTC.
- Validate leave overlap using UTC.

Available slots:

- Accept clinic-local date and duration, plus optional doctor filter.
- Use `ClinicSettings.clinicTimezone` to build candidate local intervals.
- Convert candidates to UTC for database overlap checks.
- Return local `date`/`time` display plus UTC interval if useful.

Leave exceptions:

- Accept UTC `startAt`/`endAt`.
- Validate against In Visit appointments using UTC overlap.
- Mark affected appointments using UTC overlap.
- Derive display with clinic timezone.

Shift times:

- Store recurring `startTime`/`endTime` as clinic-local time.
- Interpret weekday in clinic timezone.
- On appointment validation, convert appointment UTC interval into clinic local date/time and compare to shift rows.

Display conversion:

- Return UTC `startAt`/`endAt` as source fields.
- Return optional clinic-local `date`, `time`, and display strings.
- Do not rely on browser-local timezone for authoritative scheduling.

Daylight saving changes:

- IANA timezone conversion handles DST if the clinic timezone observes it.
- Ambiguous/nonexistent local times should be rejected or normalized in the backend if local inputs are ever supported.
- UTC storage prevents historical appointment time drift.

# 11. Optimistic Locking Design

Versioned models:

- `Patient`
- `Appointment`
- `Visit`
- `Invoice`
- `WorkingShift`
- `AvailabilityException`

Recommended versioned models:

- `EmployeeProfile`
- `ClinicSettings`

Standard behavior:

1. Client reads record with `version`.
2. Client sends the last known `version` on update.
3. Backend fetches current row inside a transaction when needed.
4. Backend compares request version with database version.
5. If mismatch, backend returns HTTP `409 Conflict`.
6. On success, backend increments `version`.
7. On success, backend updates `updatedAt`.

Frontend message recommendation:

```text
This record was updated by someone else. Please refresh and try again.
```

Example stale appointment:

```text
Staff opens appointment version 4.
Doctor starts the visit, appointment becomes version 5.
Staff submits edit with version 4.
Backend returns 409 Conflict with code STALE_VERSION.
```

Example stale invoice:

```text
Staff opens invoice version 2 with balance 120.
Another staff member processes payment, invoice becomes version 3.
First staff member submits invoice total edit with version 2.
Backend returns 409 Conflict.
```

Affected endpoints:

- `PATCH /api/patients/{patientId}/`
- `PATCH /api/appointments/{id}/`
- Appointment status actions.
- Appointment reschedule.
- Visit notes and complete.
- Invoice total edit.
- Invoice cancel.
- Payment processing, using invoice version.
- Working shift create/update/disable where updating existing rows.
- Leave update/cancel.
- Clinic settings update if versioned.
- Employee profile update if versioned.

# 12. Validation Rules

## Users

- Username required and unique.
- Email required and unique.
- Role must be `Admin`, `Staff`, or `Doctor`.
- Status must be `Active` or `Inactive`.
- Inactive users cannot log in.
- Password reset/setup tokens expire and cannot be reused.
- `mustChangePassword` forces change-password flow.

## Patients

- First name, last name, national ID/passport, date of birth, phone, emergency contact, address, insurance info, and medical conditions history are required if matching current UI.
- `nationalIdOrPassport` is string/varchar.
- Date of birth cannot be future.
- Age is calculated.
- Gender is constrained.
- Blood group constrained if provided.
- Updates require `version`.
- Doctor update requires patient scope.

## Employee profiles

- Role must be `Doctor` or `Staff`.
- Status constrained.
- Inactive Doctor cannot receive new appointments.
- User link must be unique when present.
- Updates require `version` if versioned.

## Shifts

- Day of week valid.
- `startTime < endTime` for active shifts.
- No overlapping active shifts for same person/day.
- `isActive = false` disables recurring row.
- Do not use shift `isOnLeave` for one-time leave.
- Updates require `version`.

## Leave exceptions

- `startAt < endAt`.
- UTC timezone-aware datetimes required.
- No overlapping active leave for same person unless later allowed.
- Doctor leave cannot overlap `In Visit`.
- Doctor leave marks affected Scheduled/Arrived/Checked-in/Needs Reschedule appointments as `Needs Reschedule`.
- Completed, Cancelled, and No-show appointments ignored.
- Cancelling leave does not auto-restore appointments.
- Updates/cancel require `version`.

## Appointments

- Staff-only creation.
- Client cannot set status on create.
- New appointment defaults to `Scheduled`.
- `startAt < endAt`.
- Duration at least 15 minutes.
- Duration matches interval.
- Doctor profile is active and role Doctor.
- Patient exists.
- Same doctor cannot overlap blocking appointments.
- Appointment must fit active shift.
- Appointment must not overlap active leave.
- Clinic simultaneous appointment capacity enforced.
- Appointment response must omit `due` and `dueAmount`.
- Updates and transitions require `version`.

## Visits

- Doctor can start only own Checked-in appointment.
- Doctor cannot start from Arrived.
- Doctor cannot start another doctor's appointment.
- One active/pending-notes visit per doctor.
- Start is atomic: create/activate Visit and set Appointment In Visit.
- Complete is atomic: save notes, set Visit Completed, set Appointment Completed.
- Notes/complete require `version`.

## Invoices

- Total amount must be positive.
- Invoice created from Doctor treatment price/charge or Staff handoff.
- No Services, InvoiceItems, or ServiceCatalog.
- Paid amount and balance calculated from payments.
- Total edit Staff-only.
- Total edit only before any payment exists.
- Total edit requires audit reason.
- No total edits on Cancelled invoice.
- Cancelled invoices cannot be paid.
- Edit/cancel/payment requires invoice `version`.

## Payments

- Staff-only.
- Payment method `Cash`.
- Amount must be positive.
- Amount cannot exceed remaining balance.
- Payment cannot be added to Cancelled invoice.
- Payment cannot be added to fully Paid invoice.
- Payment is immutable after creation.

## Attachments

- Validate MIME type and file extension.
- Validate max size 10 MB.
- Validate attachment belongs to visit/patient context.
- Doctor upload/manage only during own active visit.
- Files are private.

## AI results

- AI analysis only for authorized attachment context.
- Store model version.
- Store status.
- Store overlay path.
- Store findings.
- Label as support/educational/research output only.

## Clinic settings

- `clinicTimezone` required and valid IANA timezone.
- `maxSimultaneousAppointments >= 1`.
- Updates require `version` if versioned.

# 13. Error Response Specification

Use one consistent error envelope:

```json
{
  "error": {
    "code": "APPOINTMENT_CONFLICT",
    "message": "This doctor already has an appointment at this time.",
    "fields": {
      "startAt": ["Overlaps an existing appointment."]
    }
  }
}
```

HTTP status behavior:

| HTTP status | Meaning | Example codes |
| --- | --- | --- |
| `400` | Validation error | `INVALID_FIELD`, `UNSUPPORTED_FILE_TYPE` |
| `401` | Not authenticated | `AUTH_REQUIRED`, `TOKEN_EXPIRED` |
| `403` | Authenticated but forbidden | `FORBIDDEN_ROLE`, `PATIENT_SCOPE_DENIED` |
| `404` | Not found or hidden by scope | `NOT_FOUND` |
| `409` | Stale version/conflict | `STALE_VERSION`, `APPOINTMENT_CONFLICT` |
| `422` | Business rule error if separated from validation | `LEAVE_OVERLAPS_IN_VISIT`, `PAYMENT_EXCEEDS_BALANCE` |
| `500` | Unexpected server error | `INTERNAL_ERROR` |

Important business error codes:

- `APPOINTMENT_CONFLICT`
- `CLINIC_CAPACITY_REACHED`
- `DOCTOR_NOT_AVAILABLE`
- `LEAVE_OVERLAPS_IN_VISIT`
- `STALE_VERSION`
- `FORBIDDEN_ROLE`
- `PATIENT_SCOPE_DENIED`
- `PAYMENT_EXCEEDS_BALANCE`
- `INVOICE_CANCELLED`
- `INVOICE_ALREADY_PAID`
- `INVALID_TIMEZONE`
- `UNSUPPORTED_FILE_TYPE`
- `FILE_TOO_LARGE`

# 14. Backend Test Plan

## Accounts tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_admin_can_create_user` | Admin creates user with fixed role | User created, role stored. |
| `test_staff_cannot_manage_users` | Staff posts to users endpoint | 403. |
| `test_inactive_user_cannot_login` | Inactive user logs in | 401/403. |
| `test_password_reset_token_expires` | Expired token used | 400 with token error. |
| `test_roles_are_fixed` | Request roles list | Only Admin/Staff/Doctor returned. |

## Permission tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_admin_read_only_patient` | Admin patches patient | 403. |
| `test_doctor_patient_scope_allowed` | Doctor accesses patient with own appointment | 200. |
| `test_doctor_patient_scope_denied` | Doctor accesses unrelated patient | 403 or 404. |
| `test_doctor_cannot_global_billing` | Doctor lists invoices globally | 403. |
| `test_staff_can_process_payment` | Staff posts payment | Payment created. |

## Patient tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_patient_national_id_string` | Create alphanumeric national ID | Stored as string. |
| `test_patient_age_calculated` | Retrieve patient DTO | Age derived from DOB. |
| `test_patient_future_dob_rejected` | Future DOB | 400. |
| `test_patient_stale_update_conflict` | Update old version | 409. |

## Shift tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_create_active_shift` | Valid shift | Created. |
| `test_shift_overlap_rejected` | Same person/day overlap | 400. |
| `test_shift_disable_sets_inactive` | Disable shift | `isActive=false`. |
| `test_shift_version_conflict` | Update stale version | 409. |

## Leave/reschedule tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_leave_marks_affected_appointments` | Doctor leave overlaps Scheduled appointment | Appointment Needs Reschedule. |
| `test_leave_ignores_completed_cancelled_no_show` | Leave overlaps terminal appointments | No change. |
| `test_leave_overlaps_in_visit_rejected` | Leave overlaps In Visit appointment | 422/400. |
| `test_cancel_leave_does_not_restore_queue` | Cancel leave after queue marking | Appointment remains Needs Reschedule. |
| `test_leave_stale_update_conflict` | Update old version | 409. |

## Appointment tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_staff_can_create_appointment` | Staff creates valid appointment | Scheduled appointment created. |
| `test_admin_cannot_create_appointment` | Admin creates appointment | 403. |
| `test_doctor_cannot_create_appointment` | Doctor creates appointment | 403. |
| `test_create_appointment_ignores_status` | Client sends status | Rejected or ignored; result Scheduled. |
| `test_same_doctor_overlap_rejected` | Same doctor overlapping slot | 409/400 conflict. |
| `test_different_doctors_same_time_allowed_under_capacity` | Different doctors same slot | Created if capacity allows. |
| `test_clinic_capacity_reached` | Too many simultaneous appointments | Capacity error. |
| `test_appointment_outside_shift_rejected` | Slot outside shift | Doctor unavailable. |
| `test_appointment_during_leave_rejected` | Slot during leave | Doctor unavailable. |
| `test_appointment_no_due_fields` | Retrieve AppointmentDTO | No due/dueAmount. |
| `test_appointment_version_conflict` | Update old version | 409. |

## Visit tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_doctor_starts_checked_in_appointment` | Own Checked-in appointment | Visit Active, appointment In Visit. |
| `test_doctor_cannot_start_arrived` | Own Arrived appointment | Rejected. |
| `test_doctor_cannot_start_other_doctors_appointment` | Other doctor appointment | 403. |
| `test_one_active_visit_per_doctor` | Doctor already active | Rejected. |
| `test_complete_visit_atomic` | Complete visit with notes | Visit and appointment Completed. |
| `test_visit_stale_update_conflict` | Save old version | 409. |

## Billing/payment tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_doctor_creates_invoice_handoff` | Doctor submits treatment price | Pending invoice created. |
| `test_doctor_cannot_process_payment` | Doctor posts payment | 403. |
| `test_staff_processes_cash_payment` | Staff pays invoice | Payment created, status recalculated. |
| `test_payment_exceeds_balance_rejected` | Pay too much | 400/422. |
| `test_invoice_total_edit_before_payment` | Staff edits unpaid invoice with reason | Total updated, audit stored. |
| `test_invoice_total_edit_after_payment_rejected` | Payment exists | Rejected. |
| `test_cancelled_invoice_cannot_be_paid` | Pay Cancelled invoice | Rejected. |
| `test_cancelled_invoice_print_export_available` | Print/export Cancelled | Available. |
| `test_invoice_stale_update_conflict` | Edit old version | 409. |

## Timezone tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_invalid_timezone_rejected` | Update settings with bad timezone | 400 `INVALID_TIMEZONE`. |
| `test_appointment_stored_utc` | Create appointment | UTC source fields stored. |
| `test_display_fields_use_clinic_timezone` | Retrieve appointment | Derived date/time match clinic timezone. |
| `test_shift_validation_uses_clinic_timezone` | UTC interval maps to local shift | Correct allow/reject. |
| `test_leave_overlap_uses_utc` | Leave overlap across timezone boundary | Correct affected appointments. |

## Attachment/AI tests

| Test name | Scenario | Expected result |
| --- | --- | --- |
| `test_upload_supported_xray_type` | Upload png/jpeg/dicom | Attachment created. |
| `test_upload_unsupported_type_rejected` | Upload unsupported file | `UNSUPPORTED_FILE_TYPE`. |
| `test_upload_too_large_rejected` | File over 10 MB | `FILE_TOO_LARGE`. |
| `test_ai_result_created_for_attachment` | Run AI | AIResult stored. |
| `test_ai_findings_return_labels` | Fetch findings | Expected disease labels. |
| `test_ai_retry_failed_result` | Retry Failed analysis | Status reset/processing. |

# 15. Implementation Phases

## 1. Project setup and dependencies

Files/apps likely affected:

- Django project settings.
- Root URL config.
- DRF settings.
- Environment settings.

Models:

- None yet.

Serializers:

- None yet.

Views/endpoints:

- Health check optional.

Services:

- Shared error handling.
- Shared response/error format.

Tests:

- Settings import.
- API health/auth baseline.

Acceptance criteria:

- Django starts.
- PostgreSQL configured.
- DRF installed/configured.
- Timezone support enabled.

Do-not-break notes:

- Do not add frontend changes.

## 2. Auth/User roles/password reset

Files/apps likely affected:

- `accounts`

Models:

- `User`
- `PasswordResetToken`

Serializers:

- Login, token, user, password reset.

Views/endpoints:

- Auth endpoints.
- User management endpoints.
- Fixed roles list.

Services:

- `accounts/services.py`

Tests:

- Login/logout/refresh.
- Role enforcement.
- Password reset/setup.

Acceptance criteria:

- Fixed role auth works.
- Inactive users blocked.
- No editable permission matrix.

Do-not-break notes:

- Frontend demo role switching remains untouched until integration.

## 3. ClinicSettings

Files/apps likely affected:

- `clinic`

Models:

- `ClinicSettings`

Serializers:

- `ClinicSettingsDTO`

Views/endpoints:

- Get/update settings.

Services:

- Settings singleton.
- Timezone validation.

Tests:

- IANA timezone validation.
- Capacity validation.
- Version conflict.

Acceptance criteria:

- Settings row available.
- Scheduling services can read timezone/capacity.

Do-not-break notes:

- No dashboard reports/charts.

## 4. Patients

Files/apps likely affected:

- `patients`

Models:

- `Patient`

Serializers:

- `PatientDTO`
- `PatientProfileDTO` skeleton.

Views/endpoints:

- List/search/create/retrieve/update.

Services:

- Patient validation.
- Doctor scope helper stub.

Tests:

- CRUD permissions.
- National ID string.
- Age calculation.
- Version conflict.

Acceptance criteria:

- Staff can manage patients.
- Admin read-only.
- Doctor scope enforced once related data exists.

Do-not-break notes:

- No appointment due/dueAmount.

## 5. Employee profiles

Files/apps likely affected:

- `staffing`

Models:

- `EmployeeProfile`

Serializers:

- `EmployeeProfileDTO`

Views/endpoints:

- Profile list/create/retrieve/update.

Services:

- Profile validation.

Tests:

- Admin manage.
- Staff read-only.
- Doctor own profile.

Acceptance criteria:

- Doctor and Staff profiles are represented by one neutral model.

Do-not-break notes:

- Do not duplicate DoctorProfile/StaffProfile tables unless needed.

## 6. Working shifts

Files/apps likely affected:

- `staffing`

Models:

- `WorkingShift`

Serializers:

- `WorkingShiftDTO`

Views/endpoints:

- Create/update/bulk replace/disable/validate.

Services:

- `staffing/shift_services.py`

Tests:

- Overlap.
- `isActive`.
- Version conflict.

Acceptance criteria:

- Recurring availability works.
- `isActive=false` disables row.

Do-not-break notes:

- Do not use `isOnLeave` for temporary leave.

## 7. Availability exceptions

Files/apps likely affected:

- `staffing`
- `scheduling`

Models:

- `AvailabilityException`

Serializers:

- `AvailabilityExceptionDTO`

Views/endpoints:

- Create/update/cancel/preview/list.

Services:

- `staffing/leave_services.py`

Tests:

- Affected appointments.
- In Visit rejection.
- Cancel does not restore queue.
- Version conflict.

Acceptance criteria:

- Temporary leave works without mutating shifts.

Do-not-break notes:

- Use UTC `startAt`/`endAt`.

## 8. Appointment scheduling and availability

Files/apps likely affected:

- `scheduling`

Models:

- `Appointment`

Serializers:

- `AppointmentDTO`
- Create/update/reschedule requests.

Views/endpoints:

- Appointment list/create/retrieve/update.
- Available slots.

Services:

- `scheduling/availability.py`
- `scheduling/services.py`

Tests:

- Staff-only creation.
- Overlap.
- Capacity.
- Shift/leave.
- No due fields.
- Version conflict.

Acceptance criteria:

- Backend is scheduling authority.
- Appointment stores UTC source datetimes.

Do-not-break notes:

- Do not accept client status on create.

## 9. Reschedule queue and change logs

Files/apps likely affected:

- `scheduling`

Models:

- `AppointmentChangeLog`

Serializers:

- `AppointmentChangeLogDTO`

Views/endpoints:

- Reschedule.
- Queue.
- Change logs.

Services:

- Reschedule service.
- Change log creation.

Tests:

- Needs Reschedule queue.
- Reschedule to Scheduled.
- Immutable logs.

Acceptance criteria:

- Staff can recover leave-affected appointments.

Do-not-break notes:

- Cancelling leave does not auto-restore appointments.

## 10. Visit lifecycle

Files/apps likely affected:

- `visits`
- `scheduling`

Models:

- `Visit`

Serializers:

- `VisitDTO`
- Notes request.

Views/endpoints:

- Start active visit.
- Active visit retrieval.
- Notes.
- Complete.

Services:

- `visits/services.py`

Tests:

- Checked-in-only start.
- One active visit per doctor.
- Atomic start/complete.
- Version conflict.

Acceptance criteria:

- Doctor handles `Checked-in -> In Visit -> Completed`.

Do-not-break notes:

- Doctor cannot start Arrived appointment.

## 11. Doctor treatment price and invoice handoff

Files/apps likely affected:

- `visits`
- `billing`

Models:

- `Invoice`

Serializers:

- Invoice handoff request.
- `InvoiceDTO`

Views/endpoints:

- `/api/visits/{visitId}/invoice/`

Services:

- `billing.services.create_invoice_handoff`

Tests:

- Doctor enters price.
- Pending invoice created.
- Doctor cannot process payment.

Acceptance criteria:

- Invoice handoff requires treatment price/charge.

Do-not-break notes:

- Do not use appointment due/fallback amount.

## 12. Billing and payments

Files/apps likely affected:

- `billing`

Models:

- `Invoice`
- `Payment`

Serializers:

- `InvoiceDTO`
- `PaymentDTO`
- Payment request.
- Invoice total edit request.

Views/endpoints:

- Invoice list/detail/edit/cancel.
- Payment list/create.
- Print/export placeholders.

Services:

- `billing/services.py`

Tests:

- Cash payment.
- Balance/status calculation.
- Cancelled invoice behavior.
- Total edit before payment only.
- Version conflict.

Acceptance criteria:

- Invoice/Payment are financial source of truth.

Do-not-break notes:

- No Services, InvoiceItems, or complex accounting.

## 13. Attachments/X-rays

Files/apps likely affected:

- `attachments`

Models:

- `Attachment`

Serializers:

- `AttachmentDTO`

Views/endpoints:

- Upload/list/delete/original URL.

Services:

- `attachments/services.py`

Tests:

- File type.
- File size.
- Authorization.

Acceptance criteria:

- Private X-ray metadata and access works.

Do-not-break notes:

- Do not expose public raw media by default.

## 14. AI results/findings

Files/apps likely affected:

- `ai_results`

Models:

- `AIResult`
- `AIResultFinding`

Serializers:

- `AIResultDTO`
- `AIResultFindingDTO`

Views/endpoints:

- Run/get/findings/overlay/retry.

Services:

- `ai_results/services.py`

Tests:

- AI status.
- Findings.
- Retry.
- Authorization.

Acceptance criteria:

- AI output is stored and shown as support/research, not diagnosis.

Do-not-break notes:

- No clinical diagnosis workflow.

## 15. Frontend API integration preparation

Files/apps likely affected:

- Backend serializers and endpoint docs.
- Frontend later, but not in this backend planning step.

Models:

- None new.

Serializers:

- Confirm all camelCase DTOs.

Views/endpoints:

- Confirm endpoint shapes stable.

Services:

- Error mapper.

Tests:

- Contract tests for DTO field names.
- No appointment due/dueAmount.
- 409 shape.

Acceptance criteria:

- Frontend can replace mock loaders with API client later.

Do-not-break notes:

- Do not change frontend UI until endpoints are stable.

## 16. Live updates decision later

Files/apps likely affected:

- None in v1.

Models:

- None.

Serializers:

- None.

Views/endpoints:

- None required.

Services:

- REST refetch/polling can be used initially.

Tests:

- Not required for v1.

Acceptance criteria:

- Live updates remain deferred.

Do-not-break notes:

- Do not add required WebSocket infrastructure in backend v1.

# 16. Frontend Integration Notes

Later frontend integration should:

- Replace `SessionContext` demo login with auth API calls.
- Use `/api/auth/login/`, `/api/auth/me/`, refresh, logout, and change password.
- Replace mock/localStorage loaders with an API client.
- Preserve camelCase DTOs unless the adapter layer is intentionally expanded.
- Map backend `WorkingShift.isActive` to any frontend compatibility display that still expects `isOnLeave`.
- Treat one-time leave as `AvailabilityException`, not shift state.
- Convert frontend appointment date/time controls into UTC `startAt`/`endAt` before API submission.
- Use backend-derived appointment display `date`/`time` if provided.
- Remove appointment `due`/`dueAmount` usage from API-backed flows.
- Use Invoice/Payment for all billing balances.
- Add `version` to update forms and modal state.
- Handle `409 Conflict` with refresh/retry message.
- Render backend validation errors from the standard error envelope.
- Add loading/error states around API calls.
- Avoid changing UI behavior until backend endpoint contracts are stable.

# 17. Open Decisions

No product decisions currently block backend implementation planning.

Non-blocking future decisions:

- Live updates strategy later: polling, refetch-on-action, Server-Sent Events, or WebSockets.
- Real PDF export later.
- Whether AI geometry/bbox findings are needed later.
- Whether additional payment methods are added later.
- Whether Doctor sees own-visit payment history later as read-only.

# 18. Final Readiness Statement

Backend implementation readiness: Ready

Reason:

- Backend v1 scope is locked.
- Canonical role permissions are defined.
- Required models are identified.
- Appointment, visit, leave, billing, timezone, and optimistic locking rules are concrete.
- No blocking product decisions remain for initial backend implementation.
- Non-blocking future decisions are explicitly deferred.

# 19. Validation Report

Frontend code changed:

- No.

Backend code changed:

- No.

Validation commands run:

- `npm run typecheck`: not run because this was Markdown-only.
- `npm run build`: not run because this was Markdown-only.
- Backend tests: not run because no backend code exists/changed.

Files inspected:

- `BACKEND_V1_SOURCE_OF_TRUTH.md`
- `FRONTEND_BACKEND_HANDOFF.md`
- `C:\Users\i\.codex\attachments\e0c94924-90c9-4880-924d-14b7b8700286\pasted-text.txt`

Files created/updated:

- `BACKEND_IMPLEMENTATION_SPEC.md`

Backend implementation readiness:

- Ready for ChatGPT review: Yes.
