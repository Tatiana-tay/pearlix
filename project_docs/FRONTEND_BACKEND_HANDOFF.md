# Backend v1 Source-of-Truth Notice

`BACKEND_V1_SOURCE_OF_TRUTH.md` is the canonical backend v1 scope document. This handoff still records confirmed frontend facts from the current React/Vite prototype, but final backend v1 decisions are controlled by the source-of-truth document.

Final backend v1 decisions that override prototype ambiguity:

- Use simple role-based permissions only: `User.role = Admin | Staff | Doctor`.
- Backend enforces permissions in code; do not build an editable permission matrix, per-user permission overrides, request-access flow, pending account requests, dynamic permission editor, or role-permission management backend/UI in v1.
- Mock `Permission` and `rolePermissions` data in the frontend are prototype data only.
- Admin manages users, roles on individual users, doctor/staff profiles, recurring shifts, and leave exceptions. Admin remains read-only for appointments, patients, billing, invoices/payments, and clinical-operational records.
- Staff creates/edits/reschedules appointments, checks in patients, manages patient demographics, manages billing, and processes cash payments.
- Doctor can edit individual assigned/relevant patient demographics like Staff, start/continue/complete own active visits, manage X-rays/AI during active visit, and enter treatment price/charge before sending invoice handoff. Doctor cannot create general appointments or process payments.
- Appointment creation is Staff-only and must not accept status from the UI; backend defaults new appointments to `Scheduled`.
- Appointment records must not store or return `due`, `dueAmount`, or display due in backend v1. Invoice/Payment are the only source of financial balance.
- Scheduling must validate same-doctor overlap, doctor shifts, doctor leave, clinic simultaneous appointment capacity, and duration.
- Add `ClinicSettings.clinicTimezone` and `ClinicSettings.maxSimultaneousAppointments`.
- Backend stores appointment and leave source datetimes as UTC `startAt`/`endAt`, and uses IANA `ClinicSettings.clinicTimezone` for scheduling authority.
- Doctor can start a visit only from a Checked-in appointment. Staff handles `Scheduled -> Arrived` and `Arrived -> Checked-in`; Doctor handles `Checked-in -> In Visit` and `In Visit -> Completed`.
- Doctor patient scope is final: a Doctor can access/edit a patient only when the patient has an appointment, visit, or active visit with that Doctor.
- Doctor billing visibility is limited to treatment price/handoff and own-visit handoff status if shown in context. Doctor cannot access global Billing, process payments, edit payments, cancel invoices, or manage full clinic billing.
- Invoice total can be edited only before any payment exists, requires an audit reason, and is blocked after payment or cancellation.
- Important editable models use optimistic locking with `updatedAt` and `version`; stale updates return HTTP `409 Conflict`.
- `WorkingShift` is recurring weekly availability; backend should prefer `WorkingShift.isActive` for recurring row state. `AvailabilityException` is temporary leave/block. Do not use `WorkingShift.isOnLeave` for one-time leave.
- Live updates/WebSockets are deferred and not required for backend v1.

# 1. Executive Summary

This frontend is a React + Vite + TypeScript single page application for a DentalCare dental clinic management system. The visible role model is:

- Admin: system/user/team/schedule oversight, with read-only appointment, patient, and billing exposure through shared operational pages.
- Staff: front-desk operations, including appointments, rescheduling, patient creation/editing, and billing/payment handling.
- Doctor: own appointment queue, active visit notes, X-ray upload/AI review, patient record viewing, and own profile/settings.

Confirmed from frontend: the app currently uses local mock data, in-memory React state, and `localStorage` persistence. There is no real API layer, no backend authentication, and no server-side authorization. `src/context/SessionContext.tsx` stores a selected demo role/user in localStorage and exposes role-switching helpers.

Purpose of this handoff: define the backend data model, REST API contracts, permissions, validations, and workflow rules needed to replace the mock/local state without changing the intended frontend behavior.

Important warning: the frontend mock data is not automatically the final database design. Some mock shapes use legacy PascalCase/snake-like names, generated IDs, hardcoded dates, display-only calculations, and prototype-only assumptions. Backend implementation should use the confirmed frontend DTO needs while applying server-side constraints and normalization.

# 2. Frontend Tech Stack

| Area | Confirmed from frontend | Source |
| --- | --- | --- |
| App framework | React `^19.0.0` | `package.json` |
| Build tool | Vite `^6.1.0`; build output reported Vite `v6.4.3` | `package.json`, `npm run build` |
| Language | TypeScript `^5.7.3`, strict mode enabled | `package.json`, `tsconfig.app.json` |
| Routing | `react-router-dom` `^7.1.5` with route guards in `App.tsx` | `package.json`, `src/App.tsx` |
| Icons | `lucide-react` `^0.475.0` | `package.json` |
| Unit tests | Vitest `^4.1.9`, jsdom, React Testing Library | `package.json`, `vitest.config.ts` |
| E2E tests | Playwright with Chrome channel, base URL `http://127.0.0.1:4173` | `playwright.config.ts` |
| Styling | CSS modules are not used; global CSS under `src/styles/*.css` with reusable class names | `src/styles` |
| State | React `useState`, `useMemo`, `useEffect`; no Redux/query client | inspected pages/components |
| Session | `SessionProvider` stores demo selected role in localStorage | `src/context/SessionContext.tsx` |
| Mock persistence | `loadRows`, `saveRows`, `loadRecord`, `saveRecord` wrap localStorage JSON | `src/utils/mockStorage.ts` |

Important reusable UI components:

- `src/components/ui/Button.tsx`
- `src/components/ui/Input.tsx`
- `src/components/ui/Select.tsx`
- `src/components/ui/TimeInput.tsx`
- `src/components/ui/Textarea.tsx`
- `src/components/ui/Modal.tsx`
- `src/components/ui/Drawer.tsx`
- `src/components/ui/Tabs.tsx`
- `src/components/tables/DataTable.tsx`
- `src/components/ui/Badge.tsx`
- `src/components/ui/Card.tsx`
- `src/components/ui/FilterPopover.tsx`
- `src/components/ui/SegmentedControl.tsx`
- `src/components/ui/StatCard.tsx`

Command results:

| Command | Result |
| --- | --- |
| `Get-ChildItem -Force` | Passed. Root contains `src`, `dist`, `e2e`, `node_modules`, config files, reports, `.git` directory. |
| `npm.cmd run typecheck` | Passed. `tsc -b` completed with exit code 0. |
| `npm.cmd run build` | Passed. `tsc -b && vite build` completed with exit code 0. Build transformed 1670 modules and wrote `dist`. |
| `npm.cmd run lint` | Not run because `package.json` has no `lint` script. |
| `git status --short` | Failed with `fatal: not a git repository (or any of the parent directories): .git`. Treat this folder as not a valid Git worktree for this handoff. |

# 3. Route Map

| Route | Role(s) | Page/component | Purpose | Backend data needed |
| --- | --- | --- | --- | --- |
| `/` | Current session role | `Navigate` to `roleHome[currentUser.role]` | Default redirect | Current authenticated user role |
| `/login` | Public/mock | `LoginPage` | Mock username/email + password login; demo role buttons | Auth endpoint, active user status, must-change-password flag |
| `/forgot-password` | Public | `ForgotPasswordPage` | Request reset instructions | Password reset request endpoint |
| `/reset-password` | Public | `ResetPasswordPage` | Reset password; handles query `state=expired/used` in mock UI | Password reset token validation and submit endpoint |
| `/admin/dashboard` | Admin | `AdminDashboardPage` | User/team/invoice/appointment overview | Counts for users, staff profiles, invoices, appointments |
| `/admin/users` | Admin | `UsersPage` | Create/edit users, role/status, password reset mock | Users, roles, activation/deactivation, password reset |
| `/admin/doctors-staff` | Admin | `DoctorsStaffPage` | Manage doctor/staff profiles, shifts, leave exceptions | Employee profiles, shifts, leave exceptions, affected appointments |
| `/admin/appointments` | Admin | `AppointmentsPage` | Read-only appointment calendar and reschedule queue view | Appointment calendar, queue, patients, doctors, shifts, leave |
| `/admin/patients` | Admin | `PatientsPage` | Read-only patient list/profile through `canWritePatients=false` | Patients, profile aggregate data |
| `/admin/billing` | Admin | `BillingPage` | Read-only billing page through `canEditInvoice=false`, `canProcessPayment=false` | Invoices, patients, visits, payments |
| `/admin/settings` | Admin | `SettingsPage` | Admin profile plus clinic/system preferences | Current user, configurable clinic preferences |
| `/staff/dashboard` | Staff | `StaffDashboardPage` | Reception overview and quick actions | Today appointments, checked-in count, pending invoices, on-duty team |
| `/staff/appointments` | Staff | `AppointmentsPage` | Create/edit/status appointments, reschedule queue | Patients, doctors, shifts, availability exceptions, appointments, logs |
| `/staff/patients` | Staff | `PatientsPage` | Create/edit patient records, open patient drawer | Patients and aggregate visits/appointments/invoices/X-rays |
| `/staff/billing` | Staff | `BillingPage` | Manage invoices and cash payments | Invoices, visits, patients, doctors, payments |
| `/staff/doctors-staff` | Staff | `DoctorsStaffPage readOnly` | Read-only team profiles and schedules | Employee profiles, shifts, leave exceptions |
| `/staff/profile` | Staff | `SettingsPage` | Own profile, shifts, leave exceptions | Current user, employee profile, shifts, leave |
| `/staff/settings` | Staff | Redirect to `/staff/profile` | Alias | None beyond redirect |
| `/doctor/dashboard` | Doctor | `DoctorDashboardPage` | Own appointment queue and stats | Current doctor profile, own appointments, visits |
| `/doctor/appointments` | Doctor | `MyAppointmentsPage` | Own appointments; start/continue visit when checked-in/in-visit | Own appointments, patient summary, shifts, leave |
| `/doctor/patients` | Doctor | `DoctorPatientRecordsPage` | Patient clinical records read-only | Patient list and aggregates |
| `/doctor/active-visit` | Doctor | `ActiveVisitPage` | Active visit notes, X-ray upload, AI analysis, invoice handoff | Active appointment, visit, attachments, AI results/findings, invoice handoff |
| `/doctor/profile` | Doctor | `SettingsPage` | Own profile, shifts, leave exceptions, today's appointments | Current user, profile, shifts, leave, own appointments |
| `/doctor/my-appointments` | Doctor | Redirect to `/doctor/appointments` | Alias | None beyond redirect |
| `/doctor/patient-records` | Doctor | Redirect to `/doctor/patients` | Alias | None beyond redirect |
| `/doctor/settings` | Doctor | Redirect to `/doctor/profile` | Alias | None beyond redirect |
| `*` | Any | `NotFoundPage` | 404 fallback | None |

# 4. Role and Permission Map

Confirmed from frontend:

| Capability | Admin | Staff | Doctor | Source |
| --- | --- | --- | --- | --- |
| Route access enforcement | Exact role gate only | Exact role gate only | Exact role gate only | `src/App.tsx` |
| User management | Yes: add/edit, change role, activate/deactivate, reset password mock | No | No | `UsersPage.tsx` |
| Role/permission data | Mock `Permission` and `rolePermissions` exist, but backend v1 treats them as prototype data only | No editable permission UI | No editable permission UI | `mockUsers.ts`, `UsersPage.tsx` |
| Doctors/staff management | Yes, unless page prop `readOnly` | Read-only page exposed | Own profile only | `DoctorsStaffPage.tsx`, `SettingsPage.tsx` |
| Shifts/working hours | Admin can add/edit/delete shifts and toggle weekly shift leave | Staff read-only team schedule, own profile read-only | Own profile read-only | `DoctorsStaffPage.tsx`, `EditableShiftsEditor.tsx`, `GroupedShiftsTable.tsx` |
| Leave exceptions | Admin can add/edit/cancel | Read-only view | Read-only own/profile view | `DoctorsStaffPage.tsx`, `StaffProfileDrawer.tsx`, `SettingsPage.tsx` |
| Appointment creation | No; Admin route is read-only | Yes | No general appointment creation | `AppointmentsPage.tsx`, `AppointmentModal.tsx` |
| Appointment rescheduling | Queue visible read-only | Can reschedule `Needs Reschedule` appointments | No | `AppointmentsPage.tsx` |
| Appointment status changes | No | Yes | Doctor can move own checked-in appointment into active visit and can save status through modal callback on own routes | `AppointmentModal.tsx`, `MyAppointmentsPage.tsx` |
| Patient creation/editing | Read-only through shared page | Yes | Final v1 decision: Doctor can edit a patient only if that patient has an appointment, visit, or active visit with that Doctor; frontend entry points are currently inconsistent | `PatientsPage.tsx`, `DoctorPatientRecordsPage.tsx`, `MyAppointmentsPage.tsx` |
| Billing/payment | Admin route read-only | Can manage invoice payment workflow and process cash payments | No standalone/global Billing access; can enter treatment price, create invoice handoff, and view own-visit handoff status if shown | `BillingPage.tsx`, `InvoiceDetails.tsx`, `ActiveVisitPage.tsx` |
| Active visit | No | No | Yes | `ActiveVisitPage.tsx` |
| Visit notes | No direct page | Patient drawer can edit visit notes when `canEdit` true | Active visit can save draft, save notes, complete visit | `PatientProfileDrawer.tsx`, `ActiveVisitPage.tsx` |
| X-ray upload/delete | Patient drawer only if `canEdit` | Yes through patient drawer | Yes in active visit; inconsistent via appointments drawer canEdit | `PatientProfileDrawer.tsx`, `ActiveVisitPage.tsx` |
| AI analysis | No dedicated admin UI | Viewer available in editable patient drawer | Run/retry analysis in active visit, view AI review | `ActiveVisitPage.tsx`, `XrayViewer.tsx` |

Backend v1 decision: enforce simple role-based permissions server-side using `User.role = Admin | Staff | Doctor` plus object-level checks. Do not implement editable permission matrices, `RolePermission` management, dynamic permission editors, per-user permission overrides, request-access flows, or pending account requests in v1.

Frontend/backend alignment issues:

- `rolePermissions.Doctor` includes `appointments.book`, but backend v1 must keep general appointment creation Staff-only. Treat this as mock/prototype data only.
- `PatientProfileDrawer canEdit` is `true` when opened from `MyAppointmentsPage`, but read-only from `DoctorPatientRecordsPage` and `ActiveVisitPage`. Final backend v1 decision: Doctor can edit a patient only if the patient has an appointment, visit, or active visit with that Doctor.
- Admin sees appointment, patient, and billing routes, but page-level logic makes them read-only. Final backend v1 decision: Admin remains read-only for appointments, patients, billing, invoices/payments, and clinical-operational records.

# 5. Confirmed Frontend Entities and Types

Primary source: `src/types/models.ts`. Data source examples are in `src/data/mock*.ts`; adapter outputs are in `src/data/adapters.ts`.

| Frontend type/name | Fields | Source file | Notes |
| --- | --- | --- | --- |
| `Role` | `"Admin"`, `"Doctor"`, `"Staff"` | `src/types/models.ts` | Used for route gates and nav. |
| `UserStatus` | `"Active"`, `"Inactive"` | `src/types/models.ts` | User login requires active status. |
| `ProfileStatus` | `UserStatus` plus `"On Leave"` | `src/types/models.ts` | For doctor/staff profiles. |
| `Gender` | `"Female"`, `"Male"` | `src/types/models.ts` | UI label often says `Sex`. |
| `User` | `id: string`, `fullName: string`, `username: string`, `email: string`, `phone: string`, `role: Role`, `status: UserStatus`, `createdAt: string`, `mustChangePassword: boolean` | `src/types/models.ts`, `src/data/mockUsers.ts` | Login blocks inactive users and users with `mustChangePassword=true`. |
| `Permission` | `id: string`, `label: string`, `code: string` | `src/types/models.ts`, `src/data/mockUsers.ts` | Mock/prototype data only. Editable permissions are out of backend v1 scope. |
| `Patient` legacy | `Patient_ID`, `First_Name`, `Last_Name`, `National_ID_Or_Passport`, `Date_Of_Birth`, `Gender`, `Phone_Number`, `Medical_Conditions_History`, `Blood_Group`, `Insurance_Info`, `Emergency_Contact`, `Address`, `Created_At`, optional `email` | `src/types/models.ts`, `src/data/mockPatients.ts` | Legacy/mock shape. Adapted to `BackendPatient`. |
| `BackendPatient` | `patientId`, `firstName`, `lastName`, `nationalIdOrPassport`, `dateOfBirth`, `gender`, `phoneNumber`, `medicalConditionsHistory`, `bloodGroup`, `insuranceInfo`, `emergencyContact`, `address`, `createdAt`, optional `email` | `src/types/models.ts`, `src/data/adapters.ts` | Frontend-friendly camelCase DTO. `age` is calculated via `ageFromDate`. |
| `DoctorProfile` legacy | `Doctor_ID`, `User_ID`, `Full_Name`, `role: "Doctor"|"Staff"`, `Specialty`, `gender`, `Phone`, `Email`, `Status`, optional `avatarUrl` | `src/types/models.ts`, `src/data/mockDoctors.ts` | Name is doctor-specific but includes Staff profiles too. |
| `BackendStaffProfile` | `id`, `userId`, `fullName`, `role: "Doctor"|"Staff"`, optional `specialty`, `gender`, `email`, `phone`, `status`, optional `avatarUrl` | `src/types/models.ts`, `src/data/adapters.ts` | Represents both doctors and staff. |
| `DoctorWorkingHour` | `Working_Hour_ID`, `Doctor_ID`, `Day_Of_Week`, `Start_Time`, `End_Time`, `Is_On_Leave` | `src/types/models.ts`, `src/data/mockDoctors.ts` | Legacy derived from shifts. |
| `StaffShift` | `id`, `userId`, `staffOrDoctorId`, `dayOfWeek`, `shiftName`, `shiftIndex`, `startTime`, `endTime`, `isOnLeave` | `src/types/models.ts`, `src/data/mockDoctors.ts` | Weekly recurring shift row. |
| `BackendShift` | `id`, `staffOrDoctorId`, `dayOfWeek`, `shiftName`, `shiftIndex`, `startTime`, `endTime`, frontend `isOnLeave` | `src/types/models.ts`, `src/utils/shifts.ts` | Confirmed frontend fact: uses `isOnLeave`. Final backend v1 decision: prefer `WorkingShift.isActive`; one-time leave must use `AvailabilityException`. |
| `AppointmentStatus` | `"Scheduled"`, `"Arrived"`, `"Checked-in"`, `"In Visit"`, `"Completed"`, `"Cancelled"`, `"No-show"`, `"Postponed"`, `"Needs Reschedule"` | `src/types/models.ts` | Status transitions in `AppointmentModal`. |
| `Appointment` / `BackendAppointment` | `id`, `patientId`, `doctorId`, `visitType`, frontend `date`, frontend `time`, `durationMinutes`, frontend mock `due`, `status`, `notes` | `src/types/models.ts`, `src/data/mockAppointments.ts` | Confirmed frontend fact: uses date/time and `due`. Final backend v1 decision: store UTC `startAt`/`endAt`, derive display fields, and omit appointment `due`/`dueAmount`; Invoice/Payment own financial balance. |
| `AvailabilityException` / `BackendAvailabilityException` | `exceptionId`, `userId`, `userRole: "Doctor"|"Staff"`, frontend `startDateTime`, frontend `endDateTime`, `reason`, optional `note`, `status: "Active"|"Cancelled"`, `createdBy`, `createdAt` | `src/types/models.ts`, `src/pages/admin/DoctorsStaffPage.tsx` | Confirmed frontend fact: local date-time strings. Final backend v1 decision: store UTC `startAt`/`endAt`; temporary leave does not mutate weekly shifts. |
| `AppointmentChangeLog` / `BackendAppointmentChangeLog` | `logId`, `appointmentId`, `oldDateTime`, `newDateTime`, `oldDoctorId`, `newDoctorId`, `reason`, `changedBy`, `changedAt` | `src/types/models.ts`, `AppointmentsPage.tsx` | Created when Staff saves a reschedule. |
| `Visit` legacy | `id`, `patientId`, `doctorId`, `appointmentId`, `visitDate`, `status`, `Symptoms_Chief_Complaint`, `Clinical_Notes`, `Diagnosis_Notes`, `Treatment_Notes` | `src/types/models.ts`, `src/data/mockInvoices.ts` | Legacy note fields. |
| `BackendVisit` | `id`, `appointmentId`, `patientId`, `doctorId`, `visitDate`, `symptomsChiefComplaint`, `clinicalNotes`, `diagnosisNotes`, `treatmentNotes`, `status` | `src/types/models.ts`, `src/data/adapters.ts` | Active visit creates/falls back locally if missing. |
| `Attachment` legacy | `File_ID`, `File_Type`, `File_Path`, `Upload_Date`, `Visit_ID`, `Patient_ID`, `Doctor_ID` | `src/types/models.ts`, `src/data/mockAi.ts` | Legacy X-ray attachment. |
| `BackendAttachment` | `id`, `patientId`, `visitId`, `filePath`, `fileName`, `fileType`, `uploadedBy`, `uploadedAt` | `src/types/models.ts`, `src/data/adapters.ts` | Active visit stores file metadata only in mock state. |
| `AIResult` legacy | `Analysis_ID`, `File_ID`, `Result_Summary`, `Overall_Confidence`, `Processed_Date`, `Model_Version`, `Status`, `Overlay_File_Path` | `src/types/models.ts`, `src/data/mockAi.ts` | Legacy shape. |
| `BackendAIResult` | `analysisId`, `fileId`, `resultSummary`, `overallConfidence`, `processedDate`, `modelVersion`, `status`, `overlayFilePath` | `src/types/models.ts`, `src/data/adapters.ts` | AI result is support output, not clinical diagnosis. |
| `AIResultFinding` legacy | `Finding_ID`, `Analysis_ID`, `FDI_Tooth_ID`, `Disease_Label`, `Confidence_Score` | `src/types/models.ts`, `src/data/mockAi.ts` | Legacy finding shape. |
| `BackendAIResultFinding` | `findingId`, `analysisId`, `fdiToothId`, `diseaseLabel`, `confidenceScore` | `src/types/models.ts`, `src/data/adapters.ts` | No bbox/geometry fields are modeled. |
| `Invoice` | `id`, `visitId`, `patientId`, `doctorId`, `invoiceDate`, `totalAmount`, `status` | `src/types/models.ts`, `src/data/mockInvoices.ts` | Base invoice row. Paid/balance are calculated from payments. |
| `BackendInvoice` | `id`, `patientId`, `visitId`, `doctorId`, `invoiceDate`, `totalAmount`, optional `paidAmount`, optional `balance`, `status` | `src/types/models.ts`, `src/utils/mockClinicState.ts` | `toBackendInvoice` derives paid, balance, and status. |
| `Payment` legacy | `id`, `invoiceId`, `amountPaid`, `paymentDate`, `Payment_Method: "Cash"`, optional `notes` | `src/types/models.ts`, `src/data/mockInvoices.ts` | Legacy method field. |
| `BackendPayment` | `id`, `invoiceId`, `amountPaid`, `paymentMethod: "Cash"`, `paymentDate`, optional `notes` | `src/types/models.ts`, `src/data/adapters.ts` | Cash-only in current frontend. |

Calculated/display-only fields seen in the frontend:

- Patient age: calculated from `dateOfBirth` in `src/utils/format.ts`.
- Invoice `paidAmount`, `balance`, and recalculated `status`: calculated in `src/utils/mockClinicState.ts`.
- Available slots/doctor availability: calculated in `src/utils/availability.ts`.
- Affected appointment count for leave: calculated by `detectAffectedAppointments`.
- Appointment summaries/counts on dashboards: calculated client-side.

# 6. Status and Enum Catalog

| Enum | Values | Source file | Backend recommendation |
| --- | --- | --- | --- |
| `Role` | `Admin`, `Doctor`, `Staff` | `src/types/models.ts` | Store as constrained enum or lookup table. |
| `UserStatus` | `Active`, `Inactive` | `src/types/models.ts` | Enforce inactive users cannot authenticate. |
| `ProfileStatus` | `Active`, `Inactive`, `On Leave` | `src/types/models.ts` | Keep separate from temporary `AvailabilityException`; `On Leave` is profile status. |
| `Gender` | `Female`, `Male` | `src/types/models.ts` | Use `gender` API field; UI may label it `Sex`. |
| `AppointmentStatus` | `Scheduled`, `Arrived`, `Checked-in`, `In Visit`, `Completed`, `Cancelled`, `No-show`, `Postponed`, `Needs Reschedule` | `src/types/models.ts` | Enforce legal transitions server-side. |
| Appointment blocking statuses | `Scheduled`, `Arrived`, `Checked-in`, `In Visit`, `Needs Reschedule` | `src/utils/availability.ts` | Block same-doctor overlaps for these statuses. |
| Leave affected statuses | `Scheduled`, `Arrived`, `Checked-in`, `Needs Reschedule` | `src/utils/availability.ts` | Leave marks these as `Needs Reschedule`. |
| Visit status | `Active`, `Completed`, `Pending Notes` | `src/types/models.ts` | Treat active visit as doctor-owned object. |
| Invoice status | `Pending`, `Partially Paid`, `Paid`, `Cancelled` | `src/types/models.ts` | Compute from payments except `Cancelled`. |
| Payment method | `Cash` | `src/types/models.ts`, `PaymentModal.tsx` | Current frontend is Cash-only. |
| AI status | `Pending`, `Processing`, `Completed`, `Failed` | `src/types/models.ts` | Drive viewer states and retry behavior. |
| AI disease label | `Caries`, `Deep Caries`, `Impacted`, `Periapical Lesion` | `src/types/models.ts` | Store as support finding label, not diagnosis. |
| Leave exception status | `Active`, `Cancelled` | `src/types/models.ts` | Cancelled leave restores future availability only. |
| Leave reason | `Leave`, `Sick Leave`, `Personal`, `Training`, `Emergency`, `Other` | `src/types/models.ts`, `DoctorsStaffPage.tsx` | Store as enum plus optional note. |
| Reschedule reason | `Doctor on leave`, `Patient requested reschedule`, `Clinic schedule adjustment`, `Other` | `src/types/models.ts`, `AppointmentsPage.tsx` | Store in `AppointmentChangeLog`. |
| Visit type | `Initial Consultation`, `Routine Checkup`, `Treatment Continuation`, `Follow-up Visit`, `Emergency Visit`, `X-ray Review`, `Post-treatment Review`, `Cleaning Visit` | `AppointmentModal.tsx` | No Services table requested; treat as enum/string until product decides otherwise. |
| Blood group | `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-` | `PatientForm.tsx`, `PatientCreateModal.tsx` | Optional/nullable patient field with constrained values if provided. |
| Weekday | `Monday`, `Tuesday`, `Wednesday`, `Thursday`, `Friday`, `Saturday`, `Sunday` | `src/utils/shifts.ts` | Use constrained enum or integer weekday plus display label. |
| Password reset token UI state | `valid`, `expired`, `used`, `success` | `ResetPasswordPage.tsx` | Backend should expose token validity; frontend currently mocks via query state. |
| X-ray accepted types | `image/png`, `image/jpeg`, `application/dicom`; extensions `.png`, `.jpg`, `.jpeg`, `.dcm` | `ActiveVisitPage.tsx` | Validate MIME and extension server-side; max 10 MB in current UI. |

# 7. Mock Data and Adapter Layer

Confirmed mock data locations:

- `src/data/mockUsers.ts`: users plus mock/prototype permissions and role permission matrix. Editable RBAC is out of backend v1 scope.
- `src/data/mockSession.ts`: demo session roles and localStorage session key names.
- `src/data/mockPatients.ts`: legacy patient mock data.
- `src/data/mockDoctors.ts`: doctor/staff profiles, shifts, working-hour legacy projections.
- `src/data/mockAppointments.ts`: appointments, availability exceptions, appointment change logs.
- `src/data/mockInvoices.ts`: visits, invoices, payments.
- `src/data/mockAi.ts`: X-ray attachments, AI results, AI findings.

Confirmed persistence utilities:

- `src/utils/mockStorage.ts` provides generic `loadRows`, `saveRows`, `loadRecord`, and `saveRecord` wrappers around `window.localStorage`.
- `src/utils/mockClinicState.ts` persists users, role permissions, patients, staff profiles, shifts, visits, invoices, payments, attachments, AI results, and the active visit appointment ID.
- `src/utils/mockScheduleState.ts` persists appointments, availability exceptions, and appointment change logs.

LocalStorage keys observed:

| Key | Data |
| --- | --- |
| `dentalcare.demoLoginRole` | Current demo role selection |
| `dentalcare.demoRole` | Legacy demo key removed on startup |
| `dentalcare.mock.users.v1` | `User[]` |
| `dentalcare.mock.rolePermissions.v1` | `Record<Role, string[]>` |
| `dentalcare.mock.patients.v1` | `BackendPatient[]` |
| `dentalcare.mock.staffProfiles.v1` | `BackendStaffProfile[]` |
| `dentalcare.mock.shifts.v1` | `BackendShift[]` |
| `dentalcare.mock.visits.v1` | `BackendVisit[]` |
| `dentalcare.mock.invoices.v1` | base `Invoice[]` |
| `dentalcare.mock.payments.v1` | `BackendPayment[]` |
| `dentalcare.mock.attachments.v1` | `BackendAttachment[]` |
| `dentalcare.mock.aiResults.v1` | `BackendAIResult[]` |
| `dentalcare.mock.activeVisitAppointmentId.v1` | active appointment ID |
| `dentalcare.mock.appointments.v1` | `BackendAppointment[]` |
| `dentalcare.mock.availabilityExceptions.v1` | `BackendAvailabilityException[]` |
| `dentalcare.mock.appointmentChangeLogs.v1` | `BackendAppointmentChangeLog[]` |

Adapter layer:

- `src/data/adapters.ts` converts legacy/mock shapes into frontend-friendly camelCase DTOs.
- Raw legacy/mock entities use names like `Patient_ID`, `First_Name`, `National_ID_Or_Passport`, `Doctor_ID`, `File_ID`, `Analysis_ID`, and `Payment_Method`.
- Backend-facing types use camelCase, for example `patientId`, `firstName`, `nationalIdOrPassport`, `staffOrDoctorId`, `uploadedAt`, and `paymentMethod`.
- Most pages/components consume adapted camelCase data.

Backend recommendation:

- Prefer API responses that match the frontend camelCase DTOs (`BackendPatient`, `BackendAppointment`, `BackendInvoice`, etc.) unless the team intentionally chooses snake_case and updates/extends the adapter layer.
- Legacy names should not leak into new API responses unless a compatibility layer is deliberately retained.
- Keep calculated fields authoritative on the backend, even if included in DTOs for display.

Known limitation/risk:

- Some screens import static adapter outputs (`appointments`, `visits`, `invoices`) instead of localStorage-backed loaders, so mock updates may not appear everywhere. A real backend API should use a single source of truth and refetch/cache consistently.

# 8. Backend Model Plan

Backend recommendation: use normalized relational models compatible with Django + Django REST Framework. Do not add unsupported scope such as Request Access, Pending Account Requests, editable RBAC/permission matrices, per-user permission overrides, Services, Invoice_Items, Service Catalog, dashboard reports/charts, or required live-update/WebSocket models.

| Model | Confirmed or recommended | Fields and type recommendations | Relationships | Indexes/constraints/validation |
| --- | --- | --- | --- | --- |
| `User` | Confirmed from `User` | `id`, `fullName`, `username`, `email`, `phone`, `role`, `status`, `createdAt`, `mustChangePassword`, password hash fields | May have one `EmployeeProfile` for Doctor/Staff | Unique username/email. Inactive users cannot authenticate. Role in `Admin/Doctor/Staff`. |
| `Role` | Confirmed enum | `Admin`, `Staff`, `Doctor` through `User.role` | Stored on User | Final backend v1 uses simple role checks in code. No editable role-permission model is required. |
| `Permission` | Mock/prototype frontend data only | Not a required backend v1 model | None in v1 | Do not build editable permission matrix in backend v1. |
| `RolePermission` | Out of backend v1 scope | Not allowed as required v1 model | None in v1 | Do not build role-permission management endpoints/UI in v1. |
| `PasswordResetToken` | Backend recommendation from auth UI | `id`, `userId`, `tokenHash`, `expiresAt`, `usedAt`, `createdAt` | Belongs to User | Token single-use; expose expired/used/valid states. |
| `Patient` | Confirmed | `patientId`, `firstName`, `lastName`, `nationalIdOrPassport`, `dateOfBirth`, `gender`, `phoneNumber`, `email`, `medicalConditionsHistory`, `bloodGroup`, `insuranceInfo`, `emergencyContact`, `address`, `createdAt`, `createdBy`, `updatedAt`, `version` | Has appointments, visits, attachments, invoices | `nationalIdOrPassport` must be string/varchar, not integer. Age calculated from `dateOfBirth`. Date of birth cannot be future. Optional unique national ID/passport recommended. Stale updates rejected with 409. |
| `EmployeeProfile` | Backend recommendation replacing mixed `DoctorProfile`/`BackendStaffProfile` | `id`, `userId`, `fullName`, `role`, `specialty` or `position`, `gender`, `email`, `phone`, `status`, `avatarUrl`, timestamps, recommended `version` | One-to-one or nullable one-to-one with User; has shifts, leave exceptions, appointments if Doctor | Role must be Doctor/Staff. Use object permissions for own profile and schedule visibility. |
| `WorkingShift` / `WorkingHour` | Confirmed as `BackendShift` with backend rename | `id`, `employeeProfileId`, `dayOfWeek`, `shiftName`, `shiftIndex`, `startTime`, `endTime`, backend `isActive`, `updatedAt`, `version` | Belongs to EmployeeProfile | Recurring weekly availability only. `isActive=false` disables/closes row. `startTime < endTime` for active rows. No overlapping active shifts for same person/day. Do not use shift `isOnLeave` for one-time leave. Index `(employeeProfileId, dayOfWeek)`. |
| `AvailabilityException` | Confirmed | `exceptionId`, `employeeProfileId/userId`, `userRole`, UTC `startAt`, UTC `endAt`, `reason`, `note`, `status`, `createdBy`, `createdAt`, `updatedAt`, `version`, `cancelledAt`, `cancelledBy` | Belongs to EmployeeProfile; may affect appointments | `startAt < endAt`. Prevent overlapping active leave for same person unless policy changes. Leave does not mutate weekly shifts. Stale updates rejected with 409. |
| `Appointment` | Confirmed with frontend adjustment | `id`, `patientId`, `doctorId`, `visitType`, UTC `startAt`, UTC `endAt`, `durationMinutes`, `status`, `notes`, audit fields, `updatedAt`, `version` | Patient, Doctor profile; optional Visit | Staff-only creation. Backend v1 must not store/return `due` or `dueAmount`. Same doctor cannot overlap. Different doctors can share time if clinic capacity allows. Validate shifts, leave, clinic capacity, and duration. New Staff-created appointment defaults to `Scheduled`. Stale updates rejected with 409. |
| `AppointmentChangeLog` | Confirmed | `logId`, `appointmentId`, `oldDateTime`, `newDateTime`, `oldDoctorId`, `newDoctorId`, `reason`, `changedBy`, `changedAt` | Belongs to Appointment | Create on reschedule/status-sensitive changes. |
| `Visit` | Confirmed | `id`, `appointmentId`, `patientId`, `doctorId`, `visitDate`, `status`, `symptomsChiefComplaint`, `clinicalNotes`, `diagnosisNotes`, `treatmentNotes`, timestamps, `version` | Appointment, Patient, Doctor; has attachments; may have invoice | Doctor can access own visits. Status in `Active/Completed/Pending Notes`. Stale note updates rejected with 409. |
| `Attachment` | Confirmed | `id`, `patientId`, `visitId`, `filePath` or storage key, `fileName`, `fileType`, `uploadedBy`, `uploadedAt`, `fileSize`, optional checksum | Patient, Visit, uploader User/Profile; has AI results | Validate type and size. Current frontend max is 10 MB and supports PNG/JPEG/DICOM placeholder. |
| `AIResult` | Confirmed | `analysisId`, `fileId`, `resultSummary`, `overallConfidence`, `processedDate`, `modelVersion`, `status`, `overlayFilePath`, `createdBy` | Attachment; has findings | Status in `Pending/Processing/Completed/Failed`. AI output is educational/research support only. |
| `AIResultFinding` | Confirmed | `findingId`, `analysisId`, `fdiToothId`, `diseaseLabel`, `confidenceScore` | AIResult | Consider adding geometry only if real overlays require it; not confirmed by current frontend type. |
| `Invoice` | Confirmed | `id`, `visitId`, `patientId`, `doctorId`, `invoiceDate`, `totalAmount`, `status`, audit fields, `updatedAt`, `version` | Visit, Patient, Doctor; has payments | No invoice items/services in scope. Remaining balance is calculated, not trusted. Total editable only before payment exists and with audit reason. Cancelled invoices are read-only. |
| `Payment` | Confirmed | `id`, `invoiceId`, `amountPaid`, `paymentMethod`, `paymentDate`, `notes`, `processedBy`, `createdAt` | Invoice, Staff user | Cash only currently. Amount must be positive and not exceed remaining balance. Payments not allowed on cancelled invoices. |
| `ClinicSettings` | Backend v1 decision | `clinicTimezone` IANA name, `maxSimultaneousAppointments`, timestamps, recommended `version` | Singleton or clinic-scoped settings | Store scheduling source datetimes in UTC and use clinic timezone for display/conversion. Enforce clinic capacity across all doctors. |

Important backend modeling decisions:

- `nationalIdOrPassport` must be string/varchar, not integer.
- Age should be calculated from `dateOfBirth`, not stored as authoritative.
- Remaining balance should be calculated from invoice total and payments, not trusted from frontend.
- Leave exceptions must not mutate weekly shifts.
- Appointment conflicts must check same-doctor overlap first, then clinic simultaneous appointment capacity through `ClinicSettings.maxSimultaneousAppointments`.
- Appointment must not store or return financial `due`/`dueAmount` in backend v1.
- Backend scheduling should use timezone-aware datetimes and `ClinicSettings.clinicTimezone`.
- Payments must not be allowed on cancelled invoices.
- Cancelled invoices should be read-only unless explicitly restored by admin policy.
- X-ray/AI results are educational/research support only and must not become clinical diagnosis without product/legal review.

Optimistic locking decision:

- Important editable backend models include `updatedAt` and `version`.
- Apply at minimum to `Patient`, `Appointment`, `Visit`, `Invoice`, `WorkingShift`, and `AvailabilityException`.
- Recommended also for `EmployeeProfile` and `ClinicSettings`.
- Frontend sends the last known `version` when updating a record.
- Backend rejects stale updates with HTTP `409 Conflict` if stored `version` changed.
- Backend increments `version` and updates `updatedAt` on every successful update.
- Frontend should show: "This record was updated by someone else. Please refresh and try again."

# 9. API Endpoint Plan

Use camelCase request/response fields to match current frontend DTOs unless the frontend adapter layer is intentionally expanded.

## Auth

| Method | Endpoint | Role(s) | Request body | Response body | Validation/business rules |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/auth/login/` | Public | `{ usernameOrEmail, password }` | `{ accessToken, refreshToken?, user }` | Reject inactive users. If `mustChangePassword`, return explicit flag/state. |
| `POST` | `/api/auth/logout/` | Authenticated | `{ refreshToken? }` | `{ ok: true }` | Revoke token/session if using refresh tokens. |
| `POST` | `/api/auth/refresh/` | Authenticated/refresh | `{ refreshToken }` | `{ accessToken }` | Needed only for JWT refresh design. |
| `GET` | `/api/auth/me/` | Authenticated | None | `{ user, profile? }` | Source for `SessionContext` replacement. |
| `POST` | `/api/auth/forgot-password/` | Public | `{ email }` | `{ ok: true }` | Do not reveal whether email exists. |
| `GET` | `/api/auth/reset-password/{token}/` | Public | None | `{ state: "valid"|"expired"|"used" }` | Supports reset page states. |
| `POST` | `/api/auth/reset-password/` | Public | `{ token, newPassword, confirmPassword }` | `{ ok: true }` | Token must be valid, not used, not expired. |
| `POST` | `/api/auth/change-password/` | Authenticated | `{ currentPassword, newPassword, confirmPassword }` | `{ ok: true }` | Used from settings/profile if enabled later. |

## Users/RBAC

| Method | Endpoint | Role(s) | Request body | Response body | Validation/business rules |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/users/` | Admin | Query: `search`, `role`, `status` | `{ results: UserDTO[] }` | Admin only. |
| `POST` | `/api/users/` | Admin | `CreateUserRequest` | `UserDTO` | Required full name, username, email; unique username/email. |
| `GET` | `/api/users/{id}/` | Admin | None | `UserDTO` | Admin only. |
| `PATCH` | `/api/users/{id}/` | Admin | `UpdateUserRequest` | `UserDTO` | Can update role/status/mustChangePassword. |
| `POST` | `/api/users/{id}/activate/` | Admin | None | `UserDTO` | Sets status Active. |
| `POST` | `/api/users/{id}/deactivate/` | Admin | None | `UserDTO` | Sets status Inactive. |
| `POST` | `/api/users/{id}/reset-password/` | Admin | `{ sendSetupEmail?: boolean }` | `{ ok: true }` | Mock "send setup email" becomes real reset/setup flow. |
| `GET` | `/api/roles/` | Admin | None | `RoleDTO[]` | Optional fixed list only: `Admin`, `Staff`, `Doctor`. No editable matrix. |

Out of backend v1 scope: `GET /api/permissions/`, `PUT /api/roles/{role}/permissions/`, dynamic permission editors, per-user overrides, pending account requests, and request-access workflows.

## Patients

| Method | Endpoint | Role(s) | Request body | Response body | Validation/business rules |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/patients/` | Admin read, Staff manage, Doctor scoped patients | Query: `search`, `gender`, `bloodGroup` | `{ results: PatientDTO[] }` | Doctor sees only patients with an appointment, visit, or active visit with that Doctor. |
| `POST` | `/api/patients/` | Staff | `PatientDTO` without `patientId/createdAt` | `PatientDTO` | Required create fields as UI marks. |
| `GET` | `/api/patients/{patientId}/` | Admin read, Staff, Doctor object policy | None | `PatientProfileDTO` | Aggregates visits/appointments/invoices/attachments/AI. |
| `PATCH` | `/api/patients/{patientId}/` | Staff; Doctor scoped patients | Partial `PatientDTO` plus `version` | `PatientDTO` | Doctor can edit only scoped patients. Reject stale version with 409. Validate dateOfBirth, gender, bloodGroup, national ID/passport string. |
| `GET` | `/api/patients/{patientId}/visits/` | Staff, Doctor object policy | None | `VisitDTO[]` | Sort by visit date. |
| `GET` | `/api/patients/{patientId}/appointments/` | Staff, Doctor object policy | None | `AppointmentDTO[]` | Include status. |
| `GET` | `/api/patients/{patientId}/invoices/` | Staff, Admin read; Doctor only if tied to assigned/relevant patient view | None | `InvoiceDTO[]` | Doctor has no standalone/global Billing access and cannot process payments. Keep any patient-level invoice visibility read-only if exposed. |
| `GET` | `/api/patients/{patientId}/attachments/` | Staff, Doctor object policy | None | `AttachmentDTO[]` | Include AI result linkage or separate endpoint. |

## Doctors/Staff

| Method | Endpoint | Role(s) | Request body | Response body | Validation/business rules |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/staff-profiles/` | Admin, Staff read, Doctor own/read as needed | Query: `search`, `role`, `status` | `EmployeeProfileDTO[]` | Staff page is read-only for Staff role. |
| `POST` | `/api/staff-profiles/` | Admin | `EmployeeProfileDTO` plus shifts | `EmployeeProfileDTO` | Create Doctor/Staff profile and optionally user. |
| `GET` | `/api/staff-profiles/{id}/` | Admin, Staff read, Doctor own | None | `EmployeeProfileDTO` | Object-level rules for Doctor own profile. |
| `PATCH` | `/api/staff-profiles/{id}/` | Admin | Partial profile plus `version` | `EmployeeProfileDTO` | Validate role/status/gender. Reject stale version with 409 if versioned. |
| `GET` | `/api/staff-profiles/{id}/shifts/` | Admin, Staff read, Doctor own | None | `ShiftDTO[]` | Weekly schedule. |
| `POST` | `/api/staff-profiles/{id}/shifts/` | Admin | `ShiftDTO` | `ShiftDTO` | No overlap for same person/day. |
| `PUT` | `/api/staff-profiles/{id}/shifts/` | Admin | `{ shifts: ShiftDTO[], version? }` | `ShiftDTO[]` | Bulk replace from schedule editor. Backend prefers `isActive`; reject stale version with 409. |
| `DELETE` | `/api/shifts/{id}/` | Admin | None | `{ ok: true }` | Admin only. |
| `GET` | `/api/staff-profiles/{id}/leave-exceptions/` | Admin, Staff read, Doctor own | None | `AvailabilityExceptionDTO[]` | Include Active/Cancelled. |
| `POST` | `/api/leave-exceptions/` | Admin | `CreateLeaveExceptionRequest` | `AvailabilityExceptionDTO` plus affected count | Use UTC `startAt`/`endAt`. Lock person to profile context when UI opened from profile. |
| `PATCH` | `/api/leave-exceptions/{exceptionId}/` | Admin | `UpdateLeaveExceptionRequest` plus `version` | `AvailabilityExceptionDTO` plus affected count | Use UTC `startAt`/`endAt`. Reject stale version with 409. Re-evaluate affected appointments; do not auto-restore old queue items. |
| `POST` | `/api/leave-exceptions/{exceptionId}/cancel/` | Admin | Optional `{ note }` | `AvailabilityExceptionDTO` | Future availability restored; queue remains. |

## Appointments

| Method | Endpoint | Role(s) | Request body | Response body | Validation/business rules |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/appointments/` | Admin read, Staff, Doctor own | Query: `date`, `startDate`, `endDate`, `doctorId`, `status` | `AppointmentDTO[]` | Doctor only own unless policy says otherwise. |
| `POST` | `/api/appointments/` | Staff | `CreateAppointmentRequest` | `AppointmentDTO` | Staff-only. Default status Scheduled. Request must not accept status. Validate patient/doctor/UTC startAt/endAt/duration, shifts, leave, same-doctor conflict, and clinic capacity. |
| `GET` | `/api/appointments/{id}/` | Admin read, Staff, Doctor own | None | `AppointmentDTO` with change logs | Include patient/doctor refs or hydrate separately. |
| `PATCH` | `/api/appointments/{id}/` | Staff | `UpdateAppointmentRequest` plus `version` | `AppointmentDTO` | Validate availability, no same-doctor overlap, clinic capacity. Reject stale version with 409. |
| `POST` | `/api/appointments/{id}/status/` | Staff; Doctor limited start/continue | `{ status }` | `AppointmentDTO` | Enforce legal transitions. |
| `POST` | `/api/appointments/{id}/cancel/` | Staff | `{ reason? }` | `AppointmentDTO` | Sets status Cancelled. |
| `POST` | `/api/appointments/{id}/no-show/` | Staff | `{ note? }` | `AppointmentDTO` | Sets status No-show. |
| `POST` | `/api/appointments/{id}/check-in/` | Staff | None | `AppointmentDTO` | Scheduled/Arrived -> Checked-in if allowed. |
| `POST` | `/api/appointments/{id}/start-visit/` | Doctor own | `{ version }` | `{ appointment, visit }` | Doctor can start only own Checked-in appointment. Atomically creates/activates Visit and sets appointment In Visit. Reject stale version with 409. |
| `POST` | `/api/appointments/{id}/reschedule/` | Staff | `RescheduleAppointmentRequest` | `{ appointment, changeLog }` | Needs Reschedule -> Scheduled after valid slot. |
| `GET` | `/api/appointments/reschedule-queue/` | Admin read, Staff manage | Query optional | `AppointmentDTO[]` | Only status `Needs Reschedule`. |
| `GET` | `/api/appointments/{id}/change-logs/` | Admin read, Staff, Doctor own | None | `AppointmentChangeLogDTO[]` | Audit display. |
| `GET` | `/api/available-slots/` | Staff, Admin read | Query: `doctorId?`, `date`, `durationMinutes` | `AvailableSlotDTO[]` | Based on same-doctor overlap, shifts, leave, clinic simultaneous appointment capacity, and duration. |

## Visits

| Method | Endpoint | Role(s) | Request body | Response body | Validation/business rules |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/visits/start/` | Doctor own | `{ appointmentId }` | `VisitDTO` | Appointment must belong to doctor and be `Checked-in`. `In Visit` continuation uses active visit retrieval, not start. |
| `GET` | `/api/visits/active/` | Doctor | Optional query `appointmentId` | `VisitDTO` | Return own active visit or 404. |
| `GET` | `/api/visits/{id}/` | Staff read, Doctor own | None | `VisitDTO` | Object-level checks. |
| `PATCH` | `/api/visits/{id}/notes/` | Doctor own | `UpdateVisitNotesRequest` plus `version` | `VisitDTO` | Save draft or pending notes. Reject stale version with 409. |
| `POST` | `/api/visits/{id}/complete/` | Doctor own | `UpdateVisitNotesRequest` plus `version` | `{ visit, appointment }` | Atomically saves notes, sets visit Completed, and sets appointment Completed. Reject stale version with 409. |
| `GET` | `/api/visits/` | Staff/Admin read, Doctor own | Query `patientId`, `doctorId`, `status` | `VisitDTO[]` | Use for patient profile aggregate. |

## Billing

| Method | Endpoint | Role(s) | Request body | Response body | Validation/business rules |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/invoices/` | Admin read, Staff | Query: `search`, `status`, `date`, `invoiceId` | `InvoiceDTO[]` | Include calculated paid/balance. |
| `GET` | `/api/invoices/{id}/` | Admin read, Staff, patient-profile read policy | None | `InvoiceDTO` plus payments | Cancelled invoice still viewable. |
| `POST` | `/api/visits/{visitId}/invoice/` | Doctor handoff or Staff | `{ treatmentDescription?, totalAmount, internalNote? }` | `InvoiceDTO` | Final v1: Doctor enters treatment price/charge before invoice handoff. Payment stays Staff-only. |
| `PATCH` | `/api/invoices/{id}/` | Staff | `{ totalAmount, auditReason, version }` | `InvoiceDTO` | Total editable only before any payment exists, never after payment or Cancelled. Audit reason required. Reject stale version with 409. Backend calculates status after payments. |
| `POST` | `/api/invoices/{id}/cancel/` | Staff | `{ reason? }` | `InvoiceDTO` | Sets status Cancelled; future edits/payments disabled. |
| `GET` | `/api/invoices/{id}/payments/` | Staff, Admin read | None | `PaymentDTO[]` | Payment history. |
| `POST` | `/api/invoices/{id}/payments/` | Staff | `ProcessPaymentRequest` | `{ invoice, payment }` | Cash only; amount > 0 and <= remaining balance; not Cancelled. |
| `GET` | `/api/invoices/{id}/print/` | Staff, Admin read | None | printable/PDF/HTML | Placeholder matching print action. |
| `GET` | `/api/invoices/{id}/export/` | Staff, Admin read | None | PDF/file response | Frontend currently exports demo text despite label `Export PDF`. |

## X-rays/AI

| Method | Endpoint | Role(s) | Request body | Response body | Validation/business rules |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/visits/{visitId}/attachments/` | Doctor own; Staff if allowed | Multipart file | `AttachmentDTO` | Validate type and <= 10 MB unless policy changes. |
| `GET` | `/api/visits/{visitId}/attachments/` | Doctor own, Staff read | None | `AttachmentDTO[]` | Include URL fields suitable for viewer. |
| `DELETE` | `/api/attachments/{id}/` | Doctor own/uploader; Staff if allowed | None | `{ ok: true }` | Audit delete. |
| `POST` | `/api/attachments/{id}/ai-results/` | Doctor own | None or `{ modelVersion? }` | `AIResultDTO` | Starts/runs analysis. Mark as educational/research support. |
| `GET` | `/api/attachments/{id}/ai-result/` | Doctor own, Staff read | None | `AIResultDTO` | Include status. |
| `GET` | `/api/ai-results/{analysisId}/findings/` | Doctor own, Staff read | None | `AIResultFindingDTO[]` | FDI tooth IDs and labels. |
| `GET` | `/api/attachments/{id}/image/` | Authorized | None | file/redirect URL | Original image URL for viewer. |
| `GET` | `/api/ai-results/{analysisId}/overlay/` | Authorized | None | file/redirect URL | Overlay URL after completed analysis. |
| `POST` | `/api/ai-results/{analysisId}/retry/` | Doctor own | None | `AIResultDTO` | Supported by `XrayViewer` failed state. |

## Settings/Profile

| Method | Endpoint | Role(s) | Request body | Response body | Validation/business rules |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/profile/` | Authenticated | None | `{ user, employeeProfile?, shifts?, leaveExceptions?, todayAppointments? }` | Supports `SettingsPage`. |
| `PATCH` | `/api/profile/` | Authenticated if enabled | Partial contact/profile fields | `{ user, employeeProfile? }` | Current profile page is mostly read-only; decide edit policy. |
| `POST` | `/api/profile/change-password/` | Authenticated | `{ currentPassword, newPassword, confirmPassword }` | `{ ok: true }` | Current UI points users to reset flow. |

# 10. Request/Response DTOs

Use camelCase DTOs unless the frontend adapter layer is changed.

```ts
type Role = "Admin" | "Doctor" | "Staff";
type UserStatus = "Active" | "Inactive";
type ProfileStatus = "Active" | "Inactive" | "On Leave";
type Gender = "Female" | "Male";

interface LoginRequest {
  usernameOrEmail: string;
  password: string;
}

interface LoginResponse {
  accessToken: string;
  refreshToken?: string;
  user: UserDTO;
  mustChangePassword?: boolean;
}

interface UserDTO {
  id: string;
  fullName: string;
  username: string;
  email: string;
  phone: string;
  role: Role;
  status: UserStatus;
  createdAt: string;
  mustChangePassword: boolean;
}

interface PatientDTO {
  patientId: string;
  firstName: string;
  lastName: string;
  nationalIdOrPassport: string;
  dateOfBirth: string;
  gender: Gender;
  phoneNumber: string;
  medicalConditionsHistory: string;
  bloodGroup: string;
  insuranceInfo: string;
  emergencyContact: string;
  address: string;
  createdAt: string;
  updatedAt: string;
  version: number;
  email?: string;
  age?: number; // backend-calculated/display-only if included
}

interface PatientProfileDTO extends PatientDTO {
  visits: VisitDTO[];
  appointments: AppointmentDTO[];
  invoices: InvoiceDTO[];
  attachments: AttachmentDTO[];
}

interface EmployeeProfileDTO {
  id: string;
  userId: string;
  fullName: string;
  role: "Doctor" | "Staff";
  specialty?: string;
  gender: Gender;
  email: string;
  phone: string;
  status: ProfileStatus;
  avatarUrl?: string;
}

interface AppointmentDTO {
  id: string;
  patientId: string;
  doctorId: string;
  visitType: string;
  startAt: string; // UTC ISO datetime
  endAt: string; // UTC ISO datetime
  date?: string; // derived clinic-local display field
  time?: string; // derived clinic-local display field
  durationMinutes: number;
  status: AppointmentStatus;
  notes: string;
  updatedAt: string;
  version: number;
}

// Backend v1 intentionally omits appointment due/dueAmount.
// Financial balances belong only to InvoiceDTO and PaymentDTO.

interface CreateAppointmentRequest {
  patientId: string;
  doctorId: string;
  visitType: string;
  startAt: string;
  endAt: string;
  durationMinutes: number;
  notes?: string;
}

interface UpdateAppointmentRequest {
  patientId?: string;
  doctorId?: string;
  visitType?: string;
  startAt?: string;
  endAt?: string;
  durationMinutes?: number;
  notes?: string;
  version: number;
}

interface RescheduleAppointmentRequest {
  doctorId: string;
  startAt: string;
  endAt: string;
  durationMinutes: number;
  reason: "Doctor on leave" | "Patient requested reschedule" | "Clinic schedule adjustment" | "Other";
  notes?: string;
  version: number;
}

interface AvailableSlotDTO {
  date: string;
  time: string;
  durationMinutes: number;
  availableDoctorIds: string[];
  clinicCapacityRemaining?: number;
}

interface AvailabilityExceptionDTO {
  exceptionId: string;
  userId: string;
  userRole: "Doctor" | "Staff";
  startAt: string; // UTC ISO datetime
  endAt: string; // UTC ISO datetime
  reason: "Leave" | "Sick Leave" | "Personal" | "Training" | "Emergency" | "Other";
  note?: string;
  status: "Active" | "Cancelled";
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  version: number;
  affectedAppointmentCount?: number;
}

interface CreateLeaveExceptionRequest {
  userId: string;
  startAt: string;
  endAt: string;
  reason: AvailabilityExceptionDTO["reason"];
  note?: string;
}

interface UpdateLeaveExceptionRequest {
  startAt?: string;
  endAt?: string;
  reason?: AvailabilityExceptionDTO["reason"];
  note?: string;
  status?: AvailabilityExceptionDTO["status"];
  version: number;
}

interface ShiftDTO {
  id: string;
  staffOrDoctorId: string;
  dayOfWeek: string;
  shiftName: string;
  shiftIndex: number;
  startTime: string;
  endTime: string;
  isActive: boolean;
  updatedAt: string;
  version: number;
}

// Confirmed frontend fact: current frontend uses isOnLeave.
// Final backend v1 decision: prefer isActive. Adapter can map later.
// One-time leave must use AvailabilityExceptionDTO instead.

interface VisitDTO {
  id: string;
  appointmentId: string;
  patientId: string;
  doctorId: string;
  visitDate: string;
  symptomsChiefComplaint: string;
  clinicalNotes: string;
  diagnosisNotes: string;
  treatmentNotes: string;
  status: "Active" | "Completed" | "Pending Notes";
  updatedAt: string;
  version: number;
}

interface UpdateVisitNotesRequest {
  symptomsChiefComplaint: string;
  clinicalNotes: string;
  diagnosisNotes: string;
  treatmentNotes: string;
  status?: VisitDTO["status"];
  version: number;
}

interface InvoiceDTO {
  id: string;
  patientId: string;
  visitId: string;
  doctorId: string;
  invoiceDate: string;
  totalAmount: number;
  paidAmount: number;
  balance: number;
  status: "Pending" | "Partially Paid" | "Paid" | "Cancelled";
  updatedAt: string;
  version: number;
}

interface PaymentDTO {
  id: string;
  invoiceId: string;
  amountPaid: number;
  paymentMethod: "Cash";
  paymentDate: string;
  notes?: string;
}

interface ProcessPaymentRequest {
  amountPaid: number;
  paymentMethod: "Cash";
  paymentDate: string;
  notes?: string;
  version: number;
}

interface UpdateInvoiceTotalRequest {
  totalAmount: number;
  auditReason: string;
  version: number;
}

interface AttachmentDTO {
  id: string;
  patientId: string;
  visitId: string;
  filePath: string;
  fileName: string;
  fileType: string;
  uploadedBy: string;
  uploadedAt: string;
  originalUrl?: string;
}

interface AIResultDTO {
  analysisId: string;
  fileId: string;
  resultSummary: string;
  overallConfidence: number;
  processedDate: string;
  modelVersion: string;
  status: "Pending" | "Processing" | "Completed" | "Failed";
  overlayFilePath: string;
  overlayUrl?: string;
}

interface AIResultFindingDTO {
  findingId: string;
  analysisId: string;
  fdiToothId: string;
  diseaseLabel: "Caries" | "Deep Caries" | "Impacted" | "Periapical Lesion";
  confidenceScore: number;
}

interface ClinicSettingsDTO {
  clinicTimezone: string; // IANA timezone, e.g. Asia/Damascus
  maxSimultaneousAppointments: number;
  updatedAt: string;
  version: number;
}
```

# 11. Workflow Contracts

## Appointment creation

Confirmed from frontend:

- Staff-only in UI (`currentUser.role === "Staff"`).
- Form does not expose status for new appointments.
- New appointments default to `Scheduled`.
- Patient, Doctor, Visit Type, Date, Time, Duration, and Notes are captured.
- Duration must be at least 15 minutes.
- Doctor availability checks include weekly shifts, active leave exceptions, and existing appointments.
- Same-doctor overlap is blocked.
- Different doctors can be available at the same time.

Backend contract:

- Validate patient and doctor exist.
- Doctor must be active and have an active shift covering the full appointment interval.
- Active leave exception overlapping the interval blocks booking.
- Existing appointments with blocking statuses block the same doctor only.
- Enforce `ClinicSettings.maxSimultaneousAppointments` across all doctors.
- Store source appointment datetimes as UTC `startAt`/`endAt`; use IANA `ClinicSettings.clinicTimezone` for scheduling authority and derived display fields.
- Do not allow Admin or Doctor to create general appointments in backend v1.
- Do not accept or return appointment financial `due`/`dueAmount` in backend v1.
- Reject stale appointment updates with HTTP `409 Conflict` when `version` has changed.

## Available slots

Confirmed from frontend:

- `getAvailableDoctorsForSlot` computes active doctors for date/time/duration.
- `blockingAppointmentStatuses` are `Scheduled`, `Arrived`, `Checked-in`, `In Visit`, `Needs Reschedule`.
- Cancelled, No-show, Completed, and Postponed are not blocking in current availability logic.

Backend contract:

- Build available slots from doctor shifts.
- Subtract active leave exceptions.
- Subtract blocking appointments for the same doctor.
- Subtract or mark unavailable when clinic simultaneous appointment capacity is reached.
- Respect appointment duration.
- Return available doctor IDs/names for the slot.
- Use UTC `startAt`/`endAt` plus clinic timezone conversion for conflict logic.

## Leave exceptions

Confirmed from frontend:

- Admin can add/edit/cancel leave exceptions.
- The Person field in the modal is read-only/locked to the selected profile context.
- Active Doctor leave overlapping affected appointment statuses marks appointments `Needs Reschedule`.
- Staff leave updates team availability only and does not mark patient appointments.
- Leave does not modify weekly shifts.
- `WorkingShift` is recurring weekly availability; `AvailabilityException` is temporary leave/block.
- Do not use `WorkingShift.isOnLeave` for one-time leave.
- Canceling leave restores future availability only; it does not restore `Needs Reschedule` appointments.
- In-visit appointment overlap blocks saving a doctor leave exception.
- Overlapping active leave exceptions for the same person are blocked.

Backend contract:

- Validate `startDateTime < endDateTime`.
- Prevent overlapping active leave for same person unless explicitly allowed.
- For Doctor leave, mark overlapping future/current affected appointments as `Needs Reschedule`, ignoring Completed, Cancelled, and No-show. Frontend marking currently excludes Postponed via `leaveAffectedStatuses`.
- Do not auto-reschedule.
- Do not blindly restore queue items when leave is edited/cancelled.
- Audit create/edit/cancel.
- Store leave source datetimes as UTC `startAt`/`endAt`.
- Reject stale leave updates with HTTP `409 Conflict` when `version` has changed.

## Reschedule queue

Confirmed from frontend:

- Queue shows only `Needs Reschedule`.
- Admin can view queue but cannot reschedule.
- Staff can choose new doctor/date/time/duration/reason and notes.
- Save sets appointment status back to `Scheduled`.
- Save creates `AppointmentChangeLog`.

Backend contract:

- Validate appointment is `Needs Reschedule` or otherwise explicitly allowed by policy.
- Validate new doctor slot.
- Update appointment to `Scheduled`.
- Create immutable change log with old/new doctor and date-time.

## Visit workflow

Confirmed from frontend:

- Doctor starts/continues visits from own checked-in/in-visit appointments.
- Starting a checked-in appointment changes it to `In Visit`.
- Active visit page can save draft (`Active`), save notes (`Pending Notes`), and complete visit (`Completed`).
- Completing a visit also sets the appointment to `Completed`.
- Active visit can create/send an invoice handoff. Final backend v1 requires Doctor-entered treatment price/charge before handoff.

Backend contract:

- Doctor can only start/retrieve/update own active visits.
- Doctor can start a visit only from a `Checked-in` appointment.
- Staff/reception handles `Scheduled -> Arrived` and `Arrived -> Checked-in`.
- Doctor handles `Checked-in -> In Visit` and `In Visit -> Completed`.
- Backend should prevent more than one active visit per doctor.
- Starting visit atomically creates/activates Visit and changes Appointment to `In Visit`.
- Completing visit atomically saves notes, sets Visit to `Completed`, and sets Appointment to `Completed`.
- Doctor can edit a patient only if the patient has an appointment, visit, or active visit with that Doctor. Staff/Admin clinical visit note editing is not included in backend v1.
- Reject stale visit/appointment updates with HTTP `409 Conflict` when `version` has changed.

## Doctor treatment price / invoice handoff

Final backend v1 decision:

- Active Visit Billing/Closure must support treatment description or billing note, treatment price/total charge, optional internal note, and send-to-billing/create-invoice action.
- Doctor enters treatment price/charge before creating invoice handoff.
- Backend creates a Pending invoice with `patientId`, `doctorId`, `visitId`, `totalAmount`, `invoiceDate/createdAt`, and `createdBy/submittedBy`.
- Doctor cannot process payment.
- Doctor can view invoice/handoff status for their own visit if shown in patient/visit context.
- Doctor cannot access standalone/global Billing, process payments, edit payments, cancel invoices, manage full clinic billing, or see full payment history unless intentionally exposed read-only for their own visit.
- Staff processes cash payment later in Billing.

## Billing/payment

Confirmed from frontend:

- Invoice links to visit, patient, and doctor.
- Remaining balance is displayed.
- `PaymentModal` is not rendered for Cancelled invoices.
- `recordMockPayment` ignores Cancelled invoices.
- Payment amount must be positive and not exceed remaining balance.
- Payment method is read-only Cash.
- Cancelled invoice cannot be edited or paid.
- Print Invoice and Export PDF remain available for Cancelled invoices.
- Invoice Details shows: `This invoice has been cancelled and cannot be modified.`

Backend contract:

- Invoice `paidAmount`, `balance`, and payment-derived status must be calculated server-side.
- Payment statuses:
  - no payment -> `Pending`
  - partial payment -> `Partially Paid`
  - full payment -> `Paid`
  - cancelled -> `Cancelled`
- Reject payments and edits for Cancelled invoices.
- Invoice total can be edited only before any payment exists.
- Invoice total cannot be edited after partial/full payment.
- Invoice total cannot be edited if invoice is Cancelled.
- If invoice total is edited before payment, backend requires an audit reason and stores who changed it and when.
- Reject total amount below paid amount, though this should be impossible when edits are blocked after payment.
- Reject stale invoice updates with HTTP `409 Conflict` when `version` has changed.
- Keep print/export available for Cancelled invoices.

## X-ray/AI

Confirmed from frontend:

- X-ray upload stores metadata in mock state.
- Accepted types: PNG, JPG/JPEG, DICOM placeholder; active visit enforces max 10 MB.
- AI analysis creates/updates `AIResult`.
- AI findings are displayed in `AiFindingsTable`.
- Viewer needs original/base layer information and overlay path/URL.
- Failed analysis can be retried.
- UI disclaimer says AI analysis is assistive educational/research output and must be reviewed by doctor.

Backend contract:

- Store uploaded file securely and return authorized URL/storage reference.
- Create AIResult with `Pending/Processing/Completed/Failed`.
- Store findings separately.
- Provide overlay/original URLs when authorized.
- Log AI run/retry and model version.
- Do not treat AI labels as clinical diagnosis.

# 12. Backend-Calculated Fields

Backend should calculate or authoritatively derive:

- Patient age from `dateOfBirth`.
- Invoice `paidAmount`.
- Invoice `balance`.
- Invoice status after payment.
- Appointment availability.
- Available slots.
- Appointment conflict existence.
- Clinic simultaneous appointment capacity.
- Leave affected appointment count.
- Whether leave marks appointments `Needs Reschedule`.
- Current doctor/staff on duty.
- Dashboard counts.
- AI processed date/status/model version when generated server-side.
- Appointment and leave timezone normalization from `ClinicSettings.clinicTimezone`.
- `createdAt` and `updatedAt`.
- `createdBy`, `changedBy`, `uploadedBy`, `processedBy`, and similar audit fields from authenticated user.
- IDs for all persistent records.

Frontend should not be trusted for these values even when DTOs include them for display.

# 13. Validation and Constraints

Patient:

- Required on create in UI: first name, last name, national ID/passport, date of birth, phone number, emergency contact, address, insurance info, medical conditions history.
- `gender` must be `Male` or `Female`.
- `bloodGroup` should be one of `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-` if supplied.
- `dateOfBirth` cannot be in the future.
- `nationalIdOrPassport` should be stored as string/varchar.
- Unique `nationalIdOrPassport` is recommended, subject to product decision.
- Updates send `version`; stale patient updates return HTTP `409 Conflict`.

Users/RBAC:

- Username/email required and unique.
- Inactive users cannot log in.
- `mustChangePassword` should force password setup/reset flow.
- Backend-side RBAC is required.
- Backend v1 uses simple `User.role = Admin | Staff | Doctor`; editable permission matrices and `RolePermission` management are out of scope.

Appointments:

- Staff-only creation.
- Appointment start/end must be valid.
- Backend stores source appointment times as UTC `startAt`/`endAt`.
- `ClinicSettings.clinicTimezone` must be used for scheduling authority and display conversion.
- Duration must be at least 15 minutes because UI enforces `min=15`.
- Same doctor no overlapping blocking appointment.
- Multiple doctors same time allowed.
- Clinic simultaneous appointment capacity must be enforced through `ClinicSettings.maxSimultaneousAppointments`.
- Appointment must fit within active weekly shift.
- Active leave exception blocks appointment.
- Backend v1 appointment responses must not include financial `due`/`dueAmount`.
- Status transitions must be enforced backend-side.
- Appointment and leave scheduling should use timezone-aware backend datetimes.
- Doctor can start visit only from a Checked-in appointment.
- Updates send `version`; stale appointment updates return HTTP `409 Conflict`.

Shifts:

- `startTime < endTime` for active rows.
- No overlapping shifts for same person/day.
- `dayOfWeek` must be a valid weekday.
- `isOnLeave` on a shift is weekly schedule state, not a temporary leave exception.
- One-time leave must use `AvailabilityException`.
- Backend should prefer `WorkingShift.isActive`; `isActive=false` disables/closes the recurring row.
- Updates send `version`; stale shift updates return HTTP `409 Conflict`.

Leave exceptions:

- `startDateTime < endDateTime`.
- No overlapping active leave for same person unless explicitly allowed.
- Doctor leave cannot overlap an appointment currently `In Visit`.
- Doctor leave marks affected appointments `Needs Reschedule` according to policy.
- Staff leave does not mark patient appointments in current frontend.
- Backend stores leave source times as UTC `startAt`/`endAt`.
- Updates send `version`; stale leave updates return HTTP `409 Conflict`.

Billing:

- Payment amount > 0.
- Payment amount <= remaining balance.
- Payment method currently Cash only.
- No payments on Cancelled invoice.
- No invoice total edits on Cancelled invoice.
- Invoice total can be edited only before any payment exists.
- Invoice total edits require an audit reason and audit actor/timestamp.
- Invoice total cannot be edited after partial/full payment.
- Invoice total cannot be lower than already paid amount, though edit-after-payment is blocked.
- Updates send `version`; stale invoice updates return HTTP `409 Conflict`.

X-rays/AI:

- Validate file type and extension.
- Validate file size; current UI max is 10 MB.
- Validate attachment belongs to visit/patient/doctor context.
- AI run/retry only for authorized users.
- AI result and findings must be labeled support/research output, not diagnosis.

# 14. Security and Authorization Notes

Authentication recommendation:

- Use Django auth with DRF session authentication or JWT access/refresh tokens. If this is a SPA served separately, JWT or secure cookie session both need CSRF/CORS design.
- Replace `SessionContext` demo role switching with `/api/auth/login/`, `/api/auth/me/`, and logout/refresh endpoints.

Authorization requirements:

- Enforce RBAC backend-side. Frontend `RoleGate` is not security.
- Enforce object-level permissions:
  - Doctor can access own appointments and visits.
  - Doctor can access and edit a patient only when that patient has an appointment, visit, or active visit with that Doctor.
- Staff can manage operational appointments, patients, and billing.
- Doctor can edit individual assigned/relevant patient demographics like Staff.
- Admin can manage users/staff/schedules but is read-only for appointments, patients, billing, invoices/payments, and clinical-operational records in backend v1.
- Do not implement per-user permission overrides.
- Do not implement editable `RolePermission` management in backend v1.

Audit fields recommended for sensitive actions:

- Appointment status change.
- Appointment reschedule.
- Leave creation/edit/cancel.
- Payment processing.
- Invoice cancellation.
- Invoice edit.
- X-ray upload/delete.
- AI analysis run/retry.
- User activation/deactivation.
- Password reset/setup.

Data/file security:

- X-ray files and overlays should be private, authorized media, not public static assets.
- File URLs should be short-lived signed URLs or authenticated endpoints.
- AI results should include model version and processing timestamp.
- Logs should avoid storing raw passwords/tokens.
- Use optimistic locking on important editable records. Stale updates should return HTTP `409 Conflict`, and frontend should show a refresh/retry message.

# 15. Frontend/Backend Mismatches and Decisions Needed

Final backend v1 decisions already made:

- `rolePermissions.Doctor` includes `appointments.book`, but backend v1 keeps general appointment creation Staff-only. Treat `Permission` and `rolePermissions` as mock/prototype data only.
- Doctor patient demographic editing is final: Doctor can edit a patient only when that patient has an appointment, visit, or active visit with that Doctor. The frontend currently has inconsistent `canEdit` entry points that should be aligned later.
- Admin remains read-only for appointments, patients, billing, invoices/payments, and clinical-operational records.
- Editable RBAC, permission matrices, role-permission endpoints, per-user permission overrides, pending account requests, and request-access workflows are out of backend v1 scope.
- Appointment financial `due`/`dueAmount` is out of backend v1. Invoice/Payment are the only source of financial balance.
- Doctor invoice handoff must include doctor-entered treatment price/charge before creating a Pending invoice. Doctor can see own-visit handoff status if shown, but cannot access global Billing, process payments, edit payments, cancel invoices, or manage clinic billing.
- Invoice total edits are Staff-only, allowed only before payment, require audit reason, and are blocked after payment or cancellation.
- WorkingShift is recurring weekly availability; AvailabilityException is temporary leave/block. Backend should prefer `WorkingShift.isActive`; do not use frontend shift `isOnLeave` for one-time leave.
- Backend v1 requires `ClinicSettings.clinicTimezone` as an IANA timezone and `ClinicSettings.maxSimultaneousAppointments`.
- Important editable models require `updatedAt` and `version` optimistic locking with 409 Conflict on stale updates.
- Live updates/WebSockets are deferred and not required for backend v1.

Remaining frontend/backend alignment issues:

- Patient field naming uses `gender` in DTO but UI labels it `Sex`. Keep API as `gender` unless product chooses otherwise.
- Doctor/staff profile type naming is inconsistent: `DoctorProfile` and `Doctor_ID` are used for both Doctors and Staff. Backend should use a neutral employee/profile model name.
- Staff mock profile `DOC-004` has role `Staff`, showing IDs are mock-only and not semantically reliable.
- Current frontend mock appointment data includes `due`; backend v1 must not keep or return this field.
- Confirmed frontend fact: appointments and leave currently use local date/time strings. Final backend v1 decision: store UTC `startAt`/`endAt`, convert with IANA clinic timezone, and return derived display fields if needed.
- Visit types are hardcoded strings. The scope explicitly says no Services table or Service Catalog, so keep string/enum unless product changes scope.
- Patient profile billing uses imported static `invoices` from adapters, while Billing page uses localStorage-backed `loadMockInvoices`. Backend should eliminate this inconsistency with one data source.
- Patient list "Last Visit" and "Next Appointment" use static adapter `visits`/`appointments` in some pages, not localStorage updates. Backend should provide consistent aggregate fields or queries.
- `adaptAttachment` maps legacy `File_Path` to both `filePath` and `fileName`; backend should return real `fileName` separately.
- AI overlay drawing in `XrayViewer` is static SVG; `AIResultFinding` has no geometry fields. Backend v1 should keep overlay path plus finding list only unless a later product decision adds geometry.
- `Export PDF` currently creates a frontend text file (`Blob` with text/plain) despite the label. Backend should provide a real PDF/export endpoint if required.
- Many mock dates are hardcoded around `2026-02-09` and `2026-03-10`. Backend should use real dates, timezone-aware datetimes, and clinic timezone policy.
- Password reset/setup is mocked. Backend must implement real token lifecycle and email delivery.
- `mustChangePassword` blocks mock login and tells user to use reset flow. Backend should decide if password setup and reset share the same endpoint or have separate flows.
- Leave Person field is read-only in the modal. If global add-leave without profile context is ever needed, frontend will need a selector; do not add it unless requested.
- `AppointmentChangeLog.changedBy` is a string full name in mock data, while backend should store authenticated user ID and optionally return display name.
- `AvailabilityException.createdBy` is a user ID. Keep audit fields consistent across models.
- Active visit can create a new visit locally if no visit exists. Backend should make visit creation explicit and idempotent on start.
- Current Active Visit handoff uses existing appointment due/fallback amount. Backend v1 should require Doctor-entered treatment price/charge.
- Confirmed frontend fact: Staff can currently edit invoice total in the modal while frontend validation only prevents total below paid. Final backend v1 decision: invoice total can be edited only before payment exists, with audit reason.
- Confirmed frontend fact: no version conflict handling exists. Final backend v1 decision: stale updates return 409 and frontend should refresh/retry.

Known limitation/risk:

- No real API client exists yet.
- No backend error/loading states are wired beyond local validation messages.
- Frontend currently models local date/time strings only; backend v1 must store UTC `startAt`/`endAt` and derive display values from the clinic IANA timezone.
- No pagination is modeled in current data tables.
- No medical diagnosis/legal workflow exists for AI results.
- `git status` could not validate source control state in this folder.

# 16. Recommended Backend Implementation Order

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

# 17. Backend Test Plan

Role access:

- Admin can access user/staff/schedule management endpoints.
- Staff can access appointment/patient/billing management endpoints.
- Doctor can access own appointment/visit/profile endpoints.
- Doctor cannot create general appointments.
- Admin cannot mutate clinical/operational records if read-only policy remains.
- Inactive user cannot log in.

Appointment creation and availability:

- Staff can create appointment with valid patient, active doctor, valid slot.
- Admin and Doctor creation requests are rejected.
- Same doctor overlapping appointment is rejected.
- Different doctors can be booked at same date/time.
- Clinic simultaneous appointment capacity is enforced.
- Cancelled/No-show/Completed/Postponed appointments do not block availability if policy stays aligned with frontend.
- Appointment outside shift is rejected.
- Appointment during active leave is rejected.
- Appointment response does not include financial due/dueAmount in backend v1.
- Appointment stores UTC `startAt`/`endAt`; display date/time is derived with clinic timezone.
- Stale appointment updates with old `version` return 409 Conflict.

Leave and reschedule:

- Active doctor leave overlapping Scheduled/Arrived/Checked-in/Needs Reschedule appointments marks them `Needs Reschedule`.
- Completed, Cancelled, and No-show appointments are ignored.
- Staff leave does not mark patient appointments.
- Leave overlapping an `In Visit` appointment is rejected.
- Cancelling leave does not auto-restore `Needs Reschedule`.
- Reschedule queue returns only `Needs Reschedule`.
- Staff reschedule validates new slot, sets status `Scheduled`, and creates change log.
- Admin can view but not manage queue if read-only policy remains.

Visit workflow:

- Doctor starts only own Checked-in appointment and receives an active visit.
- Doctor cannot start an Arrived appointment.
- Starting visit changes appointment to `In Visit`.
- Starting visit atomically creates/activates Visit and changes Appointment to `In Visit`.
- Doctor cannot start another doctor's visit.
- Backend prevents more than one active visit per doctor.
- Saving notes updates visit status correctly.
- Completing visit atomically saves notes, sets visit and appointment to `Completed`.
- Stale visit updates with old `version` return 409 Conflict.
- Doctor can edit patient demographics only when the patient has an appointment, visit, or active visit with that Doctor.
- Doctor cannot browse/edit unrelated clinic patients.

Billing/payment:

- Invoice paid amount is sum of payments.
- Balance is `totalAmount - paidAmount`, never trusted from frontend.
- Doctor can submit invoice handoff with treatment price/charge from Active Visit.
- Doctor can view own-visit invoice/handoff status if shown in context.
- Doctor cannot process payment.
- Doctor cannot access standalone/global Billing, edit payments, cancel invoices, or manage full clinic billing.
- No payment -> `Pending`.
- Partial payment -> `Partially Paid`.
- Full payment -> `Paid`.
- Cancelled invoice stays `Cancelled`.
- Invoice total can be edited only before payment exists and requires audit reason.
- Invoice total cannot be edited after partial/full payment.
- Payment amount <= 0 is rejected.
- Payment amount above balance is rejected.
- Payment on Cancelled invoice is rejected.
- Editing Cancelled invoice is rejected.
- Print/export endpoint remains available for Cancelled invoice.
- Stale invoice updates with old `version` return 409 Conflict.

Patient profile aggregation:

- Patient profile returns patient details, visits, appointments, invoices, attachments, and AI results.
- Age calculation matches date of birth.
- National ID/passport remains string.
- Doctor object-level patient access is limited to patients with an appointment, visit, or active visit with that Doctor.
- Stale patient updates with old `version` return 409 Conflict.

Shifts, leave, and clinic settings:

- Backend uses `WorkingShift.isActive`; `isActive=false` disables/closes recurring availability.
- Temporary leave uses `AvailabilityException`, not shift `isOnLeave`.
- Creating leave does not mutate recurring shifts.
- Leave stores UTC `startAt`/`endAt`.
- Stale WorkingShift or AvailabilityException updates with old `version` return 409 Conflict.
- Clinic timezone is required and must be an IANA timezone name.
- Scheduling uses UTC backend datetimes plus clinic timezone conversion.
- Stale ClinicSettings updates with old `version` return 409 Conflict if versioned.

X-ray/AI:

- Upload rejects unsupported type.
- Upload rejects files above max size.
- Attachment is linked to visit/patient/uploader.
- AI run creates Pending/Processing/Completed/Failed result lifecycle.
- AI result retrieval includes model version, status, processed date, overlay path/URL.
- Findings retrieval returns FDI tooth IDs, labels, confidence scores.
- Failed analysis retry updates or creates a new result according to policy.

# 18. Final Validation Report

Files/directories inspected:

- `package.json`
- `vite.config.ts`
- `vitest.config.ts`
- `playwright.config.ts`
- `tsconfig.json`
- `tsconfig.app.json`
- `src/App.tsx`
- `src/routes.tsx`
- `src/navigation/navConfig.ts`
- `src/context/SessionContext.tsx`
- `src/types/models.ts`
- `src/data/adapters.ts`
- `src/data/mockAi.ts`
- `src/data/mockAppointments.ts`
- `src/data/mockDoctors.ts`
- `src/data/mockInvoices.ts`
- `src/data/mockPatients.ts`
- `src/data/mockSession.ts`
- `src/data/mockUsers.ts`
- `src/utils/mockClinicState.ts`
- `src/utils/mockScheduleState.ts`
- `src/utils/mockStorage.ts`
- `src/utils/availability.ts`
- `src/utils/shifts.ts`
- `src/utils/statusStyles.ts`
- `src/utils/format.ts`
- `src/pages/admin/AdminDashboardPage.tsx`
- `src/pages/admin/DoctorsStaffPage.tsx`
- `src/pages/admin/UsersPage.tsx`
- `src/pages/auth/LoginPage.tsx`
- `src/pages/auth/ForgotPasswordPage.tsx`
- `src/pages/auth/ResetPasswordPage.tsx`
- `src/pages/doctor/ActiveVisitPage.tsx`
- `src/pages/doctor/DoctorDashboardPage.tsx`
- `src/pages/doctor/DoctorPatientRecordsPage.tsx`
- `src/pages/doctor/MyAppointmentsPage.tsx`
- `src/pages/shared/SettingsPage.tsx`
- `src/pages/staff/AppointmentsPage.tsx`
- `src/pages/staff/BillingPage.tsx`
- `src/pages/staff/PatientsPage.tsx`
- `src/pages/staff/StaffDashboardPage.tsx`
- `src/components/appointments/AppointmentCalendar.tsx`
- `src/components/appointments/AppointmentModal.tsx`
- `src/components/billing/InvoiceDetails.tsx`
- `src/components/billing/PaymentModal.tsx`
- `src/components/patients/PatientCreateModal.tsx`
- `src/components/patients/PatientForm.tsx`
- `src/components/patients/PatientProfileDrawer.tsx`
- `src/components/staff/EditableShiftsEditor.tsx`
- `src/components/staff/GroupedShiftsTable.tsx`
- `src/components/staff/StaffProfileDrawer.tsx`
- `src/components/ai/AiFindingsTable.tsx`
- `src/components/ai/XrayViewer.tsx`
- `src/components/ui/*`
- `src/components/layout/*`
- `src/components/tables/DataTable.tsx`

Commands run:

| Command | Result |
| --- | --- |
| `Get-ChildItem -Force` | Passed; root structure inspected. |
| `Get-ChildItem -Path src -Force` | Passed; top-level `src` structure inspected. |
| `Get-ChildItem -Path src -Recurse -File` | Passed; source files enumerated. |
| `npm.cmd run typecheck` | Passed with exit code 0. |
| `npm.cmd run build` | Passed with exit code 0. Vite reported `1670 modules transformed` and generated `dist`. |
| `npm.cmd run lint` | Not run; no `lint` script exists in `package.json`. |
| `git status --short` | Failed: `fatal: not a git repository (or any of the parent directories): .git`. |

Markdown-only revision on 2026-07-02:

- Updated this handoff for backend v1 scope decisions.
- Created `BACKEND_V1_SOURCE_OF_TRUTH.md`.
- Applied final correction pass: Checked-in-only visit start, optimistic locking, Doctor patient scope, Doctor billing visibility, invoice total edit policy, `WorkingShift.isActive`, and UTC/IANA timezone policy.
- No frontend source code was changed.
- `npm run typecheck` and `npm run build` were not rerun for this revision because only Markdown planning files changed.

Git worktree status:

- Not a valid Git worktree from the command line in `D:\pearlix`, despite a `.git` directory appearing in the root listing.

Inspection limitations:

- This handoff is based on static inspection of the frontend repository and required build/typecheck commands.
- No backend code or API schemas were present.
- No product owner clarification was requested during the original inspection; final backend v1 decisions are now centralized in `BACKEND_V1_SOURCE_OF_TRUTH.md`.
- No frontend behavior, UI, or business logic was intentionally changed. The Markdown planning artifacts are this handoff and `BACKEND_V1_SOURCE_OF_TRUTH.md`.
