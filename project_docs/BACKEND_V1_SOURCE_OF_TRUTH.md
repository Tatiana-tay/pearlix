# 1. Purpose

This document is the backend v1 source of truth for the DentalCare dental clinic management system.

It exists to prevent backend planning drift. If another planning document or frontend mock file suggests a broader feature, this file wins for backend v1 scope unless the product owner explicitly changes it.

This is a planning document only. It does not implement backend code and does not change frontend behavior.

# 2. Final v1 Scope

Backend v1 is a REST-first backend for:

- Auth, users, role-based access, and password reset/setup.
- Patients.
- Doctor/staff profiles.
- Recurring working shifts.
- Temporary availability exceptions/leave.
- Appointment scheduling, availability validation, status workflow, and reschedule queue.
- Visit lifecycle and doctor visit notes.
- Doctor-entered treatment price and invoice handoff from Active Visit.
- Invoices and cash payments.
- X-ray attachments.
- AI result and AI finding storage/display support.
- Clinic settings for timezone and simultaneous appointment capacity.
- Optimistic locking on important editable records.

Backend v1 uses simple role-based permissions:

```text
User.role = Admin | Staff | Doctor
```

Backend code enforces permissions directly from `User.role` and object ownership rules.

# 3. Explicitly Out Of Scope

Do not build these in backend v1:

- Editable permission matrix.
- Per-user permission overrides.
- Dynamic role-permission management UI/backend.
- Pending account requests.
- Request access workflow.
- Services table.
- InvoiceItem / Invoice_Items table.
- ServiceCatalog / Service Catalog.
- Dashboard chart/report models.
- Complex accounting module.
- WebSocket event models as required backend v1 scope.
- Clinical diagnosis workflow based on AI output.

The frontend currently contains mock `Permission` and `rolePermissions` data. Treat that as prototype data only, not required backend v1 scope.

# 4. Role Permissions

## Admin

Admin can:

- Manage users.
- Change user roles from the individual user view.
- Activate/deactivate users.
- Reset/setup passwords.
- Manage doctor/staff profiles.
- Manage recurring working shifts.
- Add/edit/cancel leave exceptions.
- View affected appointments from leave.

Admin cannot:

- Create general appointments.
- Edit operational appointment scheduling directly.
- Edit patient demographics or clinical-operational records.
- Process payments.
- Edit invoices.
- Clinically edit visits, X-rays, or AI output.

Admin is read-only for:

- Appointments.
- Patients.
- Billing.
- Invoices/payments.
- Clinical-operational records.

## Staff

Staff can:

- Create appointments.
- Edit/reschedule appointments.
- Check in patients.
- Manage the `Needs Reschedule` queue.
- Create/edit patient demographics.
- Manage billing.
- Process cash payments.
- View doctor/staff schedules read-only if the UI exposes that.

Staff cannot:

- Manage users.
- Change roles.
- Manage global backend settings unless explicitly exposed later.
- Edit clinical visit notes as a doctor.

## Doctor

Doctor can:

- View own appointments.
- View assigned/relevant patients.
- Edit individual assigned/relevant patient demographics like Staff.
- Start/continue/complete own active visits.
- Edit visit notes.
- Upload/manage X-rays during active visit.
- Run/review AI analysis during active visit.
- Enter treatment price/charge from Active Visit.
- Create/send invoice handoff from Active Visit to billing/front desk.
- View invoice/handoff status for their own visit if shown in patient/visit context.

Doctor cannot:

- Create general appointments.
- Access standalone/global Billing page.
- Process payments.
- See/manage full clinic billing.
- Edit payments.
- Cancel invoices unless explicitly added later.
- See full payment history unless intentionally exposed read-only for their own visit.
- Manage users.
- Manage other doctors/staff.
- Manage leave for everyone.

Doctor patient scope is defined in section 9. Frontend/backend alignment note: if the frontend currently has inconsistent `canEdit` behavior across doctor pages, backend v1 should follow this final decision: Doctor can edit individual assigned/relevant patient demographics like Staff.

# 5. Backend Models Required

Backend v1 model groups:

- `User`
- `Patient`
- `EmployeeProfile` or equivalent Staff/Doctor profile
- `WorkingShift`
- `AvailabilityException`
- `Appointment`
- `AppointmentChangeLog`
- `Visit`
- `Attachment`
- `AIResult`
- `AIResultFinding`
- `Invoice`
- `Payment`
- `ClinicSettings`
- `PasswordResetToken` if password reset/setup is implemented

Recommended model notes:

| Model | Required purpose |
| --- | --- |
| `User` | Auth identity with `role = Admin | Staff | Doctor`, status, and password setup flags. |
| `Patient` | Demographics and administrative patient data. Include `updatedAt` and `version`. |
| `EmployeeProfile` | Doctor/staff profile details tied to a user when applicable. Recommended `updatedAt` and `version`. |
| `WorkingShift` | Recurring weekly availability. Prefer `isActive`; include `updatedAt` and `version`. |
| `AvailabilityException` | Temporary leave/block with UTC `startAt` and `endAt`. Include `updatedAt` and `version`. |
| `Appointment` | Scheduling record only, not billing source of truth. Store UTC `startAt` and `endAt`; include `updatedAt` and `version`. |
| `AppointmentChangeLog` | Audit trail for rescheduling and schedule changes. |
| `Visit` | Clinical visit lifecycle and notes. Include `updatedAt` and `version`. |
| `Attachment` | X-ray/original uploaded file metadata. |
| `AIResult` | AI analysis status/summary/model/overlay. |
| `AIResultFinding` | Individual support findings shown in the UI. |
| `Invoice` | Billing source of truth for total amount and status. Include `updatedAt` and `version`. |
| `Payment` | Cash payment records. |
| `ClinicSettings` | IANA clinic timezone and simultaneous appointment capacity. Recommended `updatedAt` and `version`. |
| `PasswordResetToken` | Password setup/reset token lifecycle. |

## Optimistic locking

Important editable models must include:

```text
updatedAt
version
```

Apply at minimum to:

- `Patient`
- `Appointment`
- `Visit`
- `Invoice`
- `WorkingShift`
- `AvailabilityException`

Recommended also for:

- `EmployeeProfile`
- `ClinicSettings`

Backend behavior:

- Frontend sends the last known `version` when updating a record.
- Backend rejects stale updates if the stored version has changed.
- Return HTTP `409 Conflict` or equivalent conflict response.
- Frontend should show a message like: "This record was updated by someone else. Please refresh and try again."
- Increment `version` on every successful update.
- Always update `updatedAt` on successful update.

Example:

```text
Staff opens appointment version 4.
Doctor starts visit, appointment becomes version 5.
Staff tries to save old version 4.
Backend rejects with 409 Conflict.
```

# 6. Backend Models Not Allowed In v1

Do not add required v1 models for:

- Editable `Permission` matrix.
- `RolePermission`.
- Per-user permission overrides.
- `RequestAccess`.
- `PendingAccountRequest`.
- `Service`.
- `InvoiceItem`.
- `ServiceCatalog`.
- Reports/charts.
- WebSocket events as a required v1 model.

If a codebase later keeps a fixed enum/list of available roles, that is fine. It should not become an editable RBAC product surface in v1.

# 7. Appointment Rules

Appointment creation is Staff-only.

Admin and Doctor cannot create general appointments.

`CreateAppointmentRequest` must not accept status from the UI. Backend defaults new appointments to:

```text
Scheduled
```

Appointment creation fields:

```text
patientId
doctorId
visitType
startAt
endAt
durationMinutes
notes
```

Appointment status must not appear in the appointment creation form.

Appointment validation order:

1. Same-doctor overlap.
2. Doctor working shifts.
3. Doctor leave exceptions.
4. Clinic simultaneous appointment capacity.
5. Appointment duration.

Conflict and capacity rules:

- Same doctor cannot have overlapping appointments.
- Different doctors can have appointments at the same time.
- Clinic capacity can limit total simultaneous appointments across all doctors.
- Backend stores appointment `startAt` and `endAt` as timezone-aware UTC datetimes.
- Backend may return derived frontend display fields such as `date`, `time`, `durationMinutes`, and local display strings.
- Backend scheduling and conflict logic must use UTC datetimes plus `ClinicSettings.clinicTimezone` conversion.

Clinic capacity setting:

```text
ClinicSettings.maxSimultaneousAppointments
```

or equivalent:

```text
clinicConcurrentAppointmentLimit
```

Use "clinic capacity", not "number of doctors allowed at the same time". Capacity may represent chairs, rooms, staffing, or clinic policy.

Financial rule:

- Appointment must not store billing due as source of truth.
- Do not use `Appointment.due`, `dueAmount`, or display due in backend v1.
- Do not return appointment `dueAmount` as a display-only field in v1.
- Financial data belongs to `Invoice` and `Payment`.

# 8. Visit Lifecycle

Recommended workflow:

```text
Scheduled
-> Arrived
-> Checked-in
-> In Visit
-> Completed
```

Staff/reception handles:

- `Scheduled -> Arrived`
- `Arrived -> Checked-in`
- Operational cancellation/no-show/postpone when appropriate.

Doctor handles:

- `Checked-in -> In Visit`
- `In Visit -> Completed`

Backend rules:

- Doctor can only start own appointment.
- Doctor can start a visit only from a `Checked-in` appointment.
- Staff/reception handles arrival and check-in before the Doctor starts the clinical visit.
- Backend prevents more than one active visit per doctor.
- Starting a visit atomically creates or activates a `Visit` record and changes appointment status to `In Visit`.
- Completing a visit atomically saves notes, sets `Visit` to `Completed`, and sets `Appointment` to `Completed`.

# 9. Patient Rules

Patient demographics are editable by:

- Staff.
- Doctor for individual assigned/relevant patients.

Admin is read-only for patient demographics and clinical-operational records in v1.

Backend must keep:

- `nationalIdOrPassport` as string/varchar, not integer.
- Patient age calculated from `dateOfBirth`, not stored as authoritative.
- Gender values aligned with the frontend: `Male`, `Female`.
- Blood group values aligned with the frontend if constrained.

Doctor can access/edit a patient if at least one of these is true:

```text
1. The patient has an appointment with that doctor.
2. The patient has a visit with that doctor.
3. The patient is currently in an active visit with that doctor.
```

Doctor can:

- View these patients.
- Edit individual patient demographics like Staff.
- View related visit/X-ray/AI records according to active visit and patient-record rules.

Doctor cannot:

- Browse or edit unrelated clinic patients.
- Access every patient globally unless a future product decision changes this.

# 10. Billing/payment Rules

Payment method is Cash-only in backend v1.

Invoice balance and status are calculated by backend from payments.

Rules:

- Payment amount must be positive.
- Payment amount cannot exceed remaining balance.
- Payments cannot be added to Cancelled invoices.
- Cancelled invoices cannot be edited or paid.
- Print/export may remain available for Cancelled invoices.
- Invoice total can be edited only before any payment exists.
- Invoice total cannot be edited after partial/full payment.
- Invoice total cannot be edited if invoice is Cancelled.
- If invoice total is edited before payment, backend requires an audit reason.
- Backend stores who changed invoice total and when.
- Invoice total cannot be lower than already-paid amount, though this should be impossible if editing is blocked after payment.

Invoice status calculation:

```text
no payment -> Pending
partial payment -> Partially Paid
full payment -> Paid
cancelled -> Cancelled
```

Do not add:

- Services table.
- Invoice_Items table.
- Service Catalog.
- Complex accounting module.

# 11. Doctor Treatment Price/Invoice Handoff

Doctor should not only click "send to billing".

Active Visit -> Billing/Closure must support:

- Treatment description or billing note.
- Treatment price / total charge.
- Optional internal note.
- Send to billing / create invoice handoff.

When Doctor sends to billing, backend creates `Invoice`:

```text
patientId
doctorId
visitId
totalAmount = doctor-entered treatment price
status = Pending
invoiceDate / createdAt
createdBy or submittedBy
```

Doctor does not process payment.

Staff processes payment later in Billing.

After handoff:

- Invoice is created as `Pending`.
- Staff processes payment.
- Invoice/Payment are the financial source of truth.
- Doctor can view invoice/handoff status for their own visit if shown in patient/visit context.
- Doctor cannot edit payments, cancel invoices, manage full clinic billing, or see full payment history unless intentionally exposed read-only for their own visit.

# 12. Working Shifts And Leave Exceptions

`WorkingShift` is recurring weekly availability.

Preferred backend v1 field:

```text
WorkingShift.isActive
```

Meaning:

- `WorkingShift` = recurring weekly availability row.
- `isActive = false` means this recurring shift row is disabled/closed.
- `AvailabilityException` = temporary one-time leave/block.

`AvailabilityException` is a temporary leave/block.

Do not use `WorkingShift.isOnLeave` for one-time leave.

Do not mutate recurring weekly shifts when creating temporary leave.

If the frontend still expects `isOnLeave`, an adapter layer can map backend `isActive` to frontend-compatible display logic later. Do not edit frontend code to rename the field during backend planning.

Leave exception workflow:

- Admin adds/edits/cancels leave.
- Backend detects affected future appointments.
- Affected appointments become `Needs Reschedule`.
- Staff reschedules them.
- Cancelling leave restores availability but does not automatically restore or move appointments.
- Backend stores leave `startAt` and `endAt` as timezone-aware UTC datetimes.

Ignore completed/cancelled/no-show appointments when detecting affected appointments.

In-Visit appointments should be protected or require special handling.

# 13. Clinic Settings

Backend v1 requires a clinic settings model or singleton configuration.

Recommended fields:

```text
ClinicSettings
- clinicTimezone
- maxSimultaneousAppointments
```

`clinicTimezone` must be an IANA timezone name, for example:

- `Asia/Damascus`
- `Europe/Amsterdam`
- `Asia/Beirut`

Admin Settings should expose clinic timezone and simultaneous appointment capacity when the frontend is integrated.

Capacity should be validated during appointment scheduling after same-doctor conflict, shifts, and leave checks.

# 14. Timezone Policy

Backend must use timezone-aware datetimes.

Backend must:

- Store appointment and leave datetimes in UTC.
- Use `ClinicSettings.clinicTimezone` as clinic scheduling authority.
- Require `clinicTimezone` to be an IANA timezone name.
- Return date/time strings consistently to frontend.
- Avoid relying on browser-local timezone behavior for scheduling authority.
- Store appointment source fields as `startAt` and `endAt`, timezone-aware UTC datetimes.
- Store leave exception source fields as `startAt` and `endAt`, timezone-aware UTC datetimes.
- Frontend may still receive derived display fields such as `date`, `time`, `durationMinutes`, and local display strings.
- Scheduling/conflict logic must use UTC plus clinic timezone conversion.

Frontend currently uses local date/time strings and browser date behavior in several places. Backend v1 should normalize this.

# 15. AI/X-ray Scope

AI/X-ray output is support/educational/research output only.

Do not describe AI output as clinical diagnosis.

Keep:

- Attachment/X-ray upload.
- `AIResult`.
- `AIResultFinding`.
- Original X-ray.
- Overlay path.
- Finding list.
- Model version.
- Status.

Doctor can run/review AI in active visit.

# 16. Deferred Live Updates Decision

Do not design live updates/WebSockets as required backend v1 scope.

Backend v1 should be REST-first.

Future discussion may decide between:

- Polling.
- Refetch-on-action.
- WebSockets.
- Server-Sent Events.

For now, live updates are deferred.

# 17. Frontend/backend Mismatches To Fix Later

Known mismatches from current frontend inspection:

- Mock `Permission` and `rolePermissions` data exist, but backend v1 must use simple role checks only.
- `rolePermissions.Doctor` includes `appointments.book`, but backend v1 must keep general appointment creation Staff-only.
- Doctor patient demographic editing is inconsistent across frontend entry points. Backend v1 final decision: Doctor can edit individual patients only when the patient has an appointment, visit, or active visit with that doctor.
- Current `Appointment`/`BackendAppointment` includes `due`; backend v1 must not store or return appointment due/dueAmount.
- Current Active Visit invoice handoff creates an invoice from existing appointment due/fallback amount. Backend v1 must require doctor-entered treatment price/charge before invoice handoff.
- Current frontend invoice details allow Staff invoice total edits. Backend v1 must allow invoice total edits only before any payment exists, require an audit reason, and block edits after payment or cancellation.
- `WorkingShift.isOnLeave` exists in frontend recurring shift data, but backend v1 should prefer `WorkingShift.isActive`; one-time leave must use `AvailabilityException`.
- Frontend scheduling uses local date/time strings and browser-local behavior; backend v1 must store UTC `startAt`/`endAt` and use IANA clinic timezone.
- Admin Settings currently has only simple mock preferences. Backend v1 should add clinic timezone and max simultaneous appointments.
- `Export PDF` currently creates a frontend demo text file; backend can later provide real export without adding complex accounting scope.
- Patient/invoice/appointment data are sometimes loaded from static adapter arrays and sometimes localStorage-backed loaders; real backend should become the single source of truth.
- Frontend currently has no version conflict handling. Backend v1 must add `version`/`updatedAt` optimistic locking and return 409 for stale updates.

# 18. Backend Implementation Order

Recommended order:

1. Auth/User roles/password reset.
2. ClinicSettings: timezone + max simultaneous appointments.
3. Patients.
4. Doctor/staff profiles.
5. Working shifts.
6. Availability exceptions.
7. Appointments + availability validation.
8. Reschedule queue + AppointmentChangeLog.
9. Visits.
10. Doctor treatment price + invoice handoff.
11. Billing/payments.
12. Attachments/X-rays.
13. AI results/findings.
14. Frontend integration cleanup.
15. Live updates decision later.

# 19. Backend Test Checklist

Auth and roles:

- Admin can manage users and change roles.
- Staff cannot manage users or roles.
- Doctor cannot manage users or roles.
- Inactive user cannot log in.
- Password reset/setup tokens expire and cannot be reused.

Appointments:

- Staff can create appointments.
- Admin cannot create general appointments.
- Doctor cannot create general appointments.
- Create appointment request ignores/rejects status.
- New appointment defaults to `Scheduled`.
- Same doctor overlap is rejected.
- Different doctors can have appointments at same time when clinic capacity allows.
- Clinic simultaneous appointment capacity is enforced.
- Appointment outside doctor shift is rejected.
- Appointment during doctor leave is rejected.
- Appointment duration is validated.
- Appointment response does not include due/dueAmount in backend v1.
- Appointment stores UTC `startAt` and `endAt`; display date/time is derived using clinic timezone.
- Stale appointment updates with old `version` are rejected with 409 Conflict.

Visits:

- Staff/reception can move appointments through arrival/check-in states.
- Doctor can start a visit only from own Checked-in appointment.
- Starting a visit atomically creates/activates Visit and changes Appointment to In Visit.
- Backend prevents more than one active visit per doctor.
- Completing visit atomically saves notes, sets Visit to Completed, and sets Appointment to Completed.
- Stale visit updates with old `version` are rejected with 409 Conflict.

Patients:

- Staff can create/edit patient demographics.
- Doctor can edit patient demographics only when the patient has an appointment, visit, or active visit with that doctor.
- Doctor cannot browse/edit unrelated clinic patients.
- Admin is read-only for patient records.
- Patient age is calculated from date of birth.
- National ID/passport is stored as string.
- Stale patient updates with old `version` are rejected with 409 Conflict.

Billing:

- Doctor can submit invoice handoff with treatment price from Active Visit.
- Doctor can view invoice/handoff status for own visit if shown in context.
- Doctor cannot process payment.
- Doctor cannot access standalone/global Billing, edit payments, cancel invoices, or manage full clinic billing.
- Staff can process cash payment.
- Payment amount must be positive.
- Payment amount cannot exceed remaining balance.
- Invoice status is calculated from payments.
- Invoice total can be edited only before payment exists and requires an audit reason.
- Invoice total cannot be edited after partial/full payment.
- Cancelled invoice cannot be edited or paid.
- Stale invoice updates with old `version` are rejected with 409 Conflict.

Shifts and leave:

- WorkingShift is recurring weekly availability.
- Backend prefers `WorkingShift.isActive`; `isActive = false` disables/closes the recurring row.
- Temporary leave uses AvailabilityException.
- Creating leave does not mutate recurring shifts.
- Doctor leave marks affected future appointments as Needs Reschedule.
- Completed/cancelled/no-show appointments are ignored for leave effects.
- Cancelling leave does not auto-restore or move appointments.
- Leave stores UTC `startAt` and `endAt`.
- Stale WorkingShift or AvailabilityException updates with old `version` are rejected with 409 Conflict.

Clinic settings/timezone:

- Clinic timezone is required and must be an IANA timezone name.
- Scheduling uses UTC backend datetimes plus clinic timezone conversion.
- Admin can configure max simultaneous appointments.
- Stale ClinicSettings updates with old `version` are rejected with 409 Conflict if versioning is implemented for settings.

AI/X-ray:

- Doctor can upload/manage X-rays during active visit.
- Doctor can run/review AI during active visit.
- AI result stores model version, status, overlay path, and findings.
- AI output is labeled support/educational/research only.

Deferred:

- No WebSockets required for backend v1.
- Live updates decision remains deferred.
