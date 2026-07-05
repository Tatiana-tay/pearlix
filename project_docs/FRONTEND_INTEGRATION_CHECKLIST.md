# Frontend Integration Checklist

Date: 2026-07-05

Purpose: guide the future frontend integration phase. This checklist does not change frontend behavior and does not authorize frontend edits during Phase 15.

## Integration Guardrails

- Keep backend DTOs as the source of truth once integration begins.
- Replace mock/localStorage data gradually by domain.
- Preserve frontend UX unless a product decision explicitly changes it.
- Do not add backend features that are out of v1 scope to satisfy prototype-only mock data.
- Do not build editable permission matrices, role-permission endpoints, services catalog, invoice line items, WebSockets, or AI inference workflows.

## API Client Foundation

- Add a single frontend API client with a configurable base URL, for example `VITE_API_BASE_URL=http://127.0.0.1:8000`.
- Send `Authorization: Bearer <accessToken>` on protected requests.
- Handle `401` by clearing session state and redirecting to login.
- Handle `403` as a role/object-scope denial.
- Handle `404` as missing record or intentionally absent route.
- Handle `409 Conflict` by refreshing the record and showing a stale-record message.
- Add common loading and error states around every API-backed workflow.

## Auth Replacement

Replace demo role switching and mock login with:

- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`
- `GET /api/auth/roles/`

Expected login response includes:

- `accessToken`
- `refreshToken`
- `user`
- legacy-compatible `access` and `refresh` fields if still present

Expected user fields include:

- `id`
- `fullName`
- `username`
- `email`
- `phone`
- `role`
- `status`
- `createdAt`
- `mustChangePassword`

Do not wire frontend mock `Permission` or `rolePermissions` into a backend permission API. They are prototype-only.

## Patient Integration

Use `/api/patients/` and `/api/patients/{id}/`.

Required frontend alignment:

- Use `gender`, even where UI label displays "Sex".
- Do not send or expect `sex`.
- Treat `nationalIdOrPassport` as a string.
- Treat `age` as calculated response data.
- Include `version` on PATCH/PUT.
- Handle `409 Conflict`.
- Admin patient pages remain read-only.
- Staff can create/edit.
- Doctor can edit only assigned/relevant patients.

## Employee Profiles, Shifts, And Leave

Use:

- `/api/employee-profiles/`
- `/api/employee-profiles/me/`
- `/api/working-shifts/`
- `/api/availability-exceptions/`
- `/api/leave-exceptions/`

Required frontend alignment:

- Use neutral employee profile IDs, not mock `Doctor_ID` semantics.
- Use `WorkingShift.isActive` for recurring shift active/disabled state.
- Use `AvailabilityException` for one-time leave/block.
- Do not map one-time leave to `WorkingShift.isOnLeave` in API-backed flows.
- Include `version` on editable shift/leave updates.
- Handle leave-created reschedule effects through appointment status and queue data.

## Appointments

Use:

- `/api/appointments/`
- `/api/appointments/reschedule-queue/`
- `/api/appointments/{id}/`
- Appointment workflow action endpoints.
- `/api/appointments/{id}/change-logs/`

Required frontend alignment:

- Staff creates general appointments.
- Admin and Doctor cannot create general appointments.
- Do not send appointment status during creation.
- Convert frontend date/time controls to UTC `startAt` and `endAt`.
- Use backend `durationMinutes` where returned.
- Use `clinicTimezone` for display logic.
- Remove `due`, `dueAmount`, `paidAmount`, `balance`, and payment fields from appointment-backed UI data.
- Include `version` on appointment edits and workflow actions where required.
- Handle `409 Conflict`.

## Visits

Use:

- `/api/visits/`
- `/api/visits/start/`
- `/api/appointments/{id}/start-visit/`
- `/api/visits/active/`
- `/api/visits/{id}/`
- `/api/visits/{id}/notes/`
- `/api/visits/{id}/complete/`

Required frontend alignment:

- Doctor starts only own checked-in appointments.
- Backend allows one active visit per doctor.
- Active visit notes and completion include current `version`.
- Visit and appointment status updates are backend-owned workflow effects.
- Visit responses must not be treated as billing sources.
- Handle `409 Conflict`.

## Billing

Use:

- `/api/invoices/`
- `/api/invoices/{id}/`
- `/api/visits/{id}/invoice/`
- `/api/invoices/{id}/payments/`
- `/api/invoices/{id}/cancel/`
- `/api/payments/`
- `/api/payments/{id}/`

Required frontend alignment:

- Doctor invoice handoff requires doctor-entered `totalAmount`.
- Doctor can create handoff only for own completed visit.
- Staff processes cash payments.
- Admin reads billing data only.
- Doctor reads own invoice/payment context only where backend scope allows.
- Invoice total edits are Staff-only, require reason and current `version`, and are allowed only before payment.
- Payments are cash-only.
- Calculate display balance from invoice response; do not store appointment due.
- Appointment and visit views should not render payment state from their own DTOs.

## Attachments

Use:

- `/api/attachments/`
- `/api/attachments/{id}/`
- `/api/attachments/{id}/original-url/`
- `/api/visits/{id}/attachments/`

Required frontend alignment:

- Upload with multipart form data.
- Use `fileUrl` or original-url endpoint for authorized file access.
- Do not depend on server file path.
- Validate and display backend errors for file type and size.
- Doctor uploads only in own active visit context.
- Staff can manage patient attachments where permitted.
- Admin is read-only.

## AI Results

Use:

- `/api/ai-results/`
- `/api/ai-results/{id}/`
- `/api/ai-results/{id}/findings/`
- `/api/attachments/{id}/ai-results/`
- `/api/attachments/{id}/ai-result/`

Required frontend alignment:

- Treat AI output as support/educational/research metadata only.
- Do not label AI output as clinical diagnosis.
- Use `modelName`, `modelVersion`, `status`, `overallConfidence`, `overlayUrl`, and findings.
- Do not expect backend inference, training, retry execution, model upload, or model loading.
- Do not expect `/api/predict/`, `/api/infer/`, `/api/train/`, `/api/run-ai/`, or `/api/analyze-xray/`.
- Do not expect clinical diagnosis, final diagnosis, treatment plan, payment, due, or balance fields on AI responses.

## Clinic Settings

Use `/api/clinic/settings/`.

Required frontend alignment:

- Use `clinicTimezone` as an IANA timezone.
- Use `maxSimultaneousAppointments` for capacity display/configuration.
- Scheduling submissions should use UTC datetimes.
- Handle `version` if settings edits are exposed.

## Test Coverage For Frontend Integration

Recommended frontend tests once integration begins:

- Login success/failure and inactive-user flow.
- Token refresh and logout.
- Role routing from real `auth/me`.
- Patient create/edit/stale conflict.
- Appointment creation and conflict display.
- Leave creates reschedule queue display.
- Doctor active visit start/complete.
- Doctor invoice handoff with treatment amount.
- Staff partial/full cash payment.
- Attachment upload success and validation errors.
- AI result display from stored metadata.
- API errors: `401`, `403`, `404`, `409`, and validation `400`.

## Still Deferred

- Production deployment.
- WebSockets/live updates.
- Service catalog and invoice line items.
- Complex accounting.
- Clinical diagnosis workflow.
- AI inference/model training.
- Real PDF/export implementation unless separately scoped.

Backend Phase 15 only prepares and validates the backend for ChatGPT review and future frontend integration work.
