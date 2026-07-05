import { useState } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { XrayViewer } from "../components/ai/XrayViewer";
import { InvoiceDetails } from "../components/billing/InvoiceDetails";
import { PaymentModal } from "../components/billing/PaymentModal";
import { PatientCreateModal } from "../components/patients/PatientCreateModal";
import { PatientProfileDrawer, defaultPatient } from "../components/patients/PatientProfileDrawer";
import { GroupedShiftsTable } from "../components/staff/GroupedShiftsTable";
import { StaffProfileDrawer } from "../components/staff/StaffProfileDrawer";
import { DataTable, type DataColumn } from "../components/tables/DataTable";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { authAccessTokenStorageKey, authRefreshTokenStorageKey, authUserStorageKey, SessionProvider, useSession } from "../context/SessionContext";
import { navConfig } from "../navigation/navConfig";
import { UsersPage } from "../pages/admin/UsersPage";
import { ActiveVisitPage } from "../pages/doctor/ActiveVisitPage";
import { MyAppointmentsPage } from "../pages/doctor/MyAppointmentsPage";
import { AppointmentsPage } from "../pages/staff/AppointmentsPage";
import { PatientsPage } from "../pages/staff/PatientsPage";
import { SettingsPage } from "../pages/shared/SettingsPage";
import { routes } from "../routes";
import { adaptAppointmentDTO, toAppointmentPayload, toAppointmentStatusPayload } from "../api/appointments";
import { adaptAvailabilityExceptionDTO, toAvailabilityExceptionPayload } from "../api/availabilityExceptions";
import { adaptWorkingShiftDTO, toWorkingShiftPayload } from "../api/workingShifts";
import { adaptVisitDTO, toVisitNotesPayload } from "../api/visits";
import type { BackendAIResult, BackendAppointment, BackendAvailabilityException, BackendInvoice, BackendPatient, BackendShift, BackendStaffProfile, User } from "../types/models";
import { addMinutes, intervalsOverlap, isDoctorAvailableForInterval, toDateTime } from "../utils/availability";
import { ageFromDate } from "../utils/format";
import { calculateInvoiceStatus, loadMockPatients, saveMockPatients } from "../utils/mockClinicState";

beforeEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

const testStaffUser: User = {
  id: "USR-002",
  fullName: "Olivia Frontdesk",
  username: "olivia.frontdesk",
  email: "staff@example.com",
  phone: "(555) 010-1000",
  role: "Staff",
  status: "Active",
  createdAt: "2026-01-01T00:00:00Z",
  mustChangePassword: false,
};

function seedAuthSession(user: User = testStaffUser) {
  window.localStorage.setItem(authAccessTokenStorageKey, "test-access-token");
  window.localStorage.setItem(authRefreshTokenStorageKey, "test-refresh-token");
  window.localStorage.setItem(authUserStorageKey, JSON.stringify(user));
}

function AuthProbe() {
  const { authError, authStatus, currentUser, login, logout } = useSession();
  const [message, setMessage] = useState("");

  return (
    <div>
      <span data-testid="auth-status">{authStatus}</span>
      <span data-testid="auth-user">{currentUser?.fullName ?? "No user"}</span>
      <span data-testid="auth-error">{authError || message}</span>
      <button
        type="button"
        onClick={() => {
          void login({ username: "staff@example.com", password: "Staff123!" }).catch((error: unknown) => {
            setMessage(error instanceof Error ? error.message : "Login failed.");
          });
        }}
      >
        Backend login
      </button>
      <button type="button" onClick={() => { void logout(); }}>Logout</button>
    </div>
  );
}

describe("backend auth session", () => {
  it("stores backend tokens and user after login, then clears them on logout", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/auth/login/")) {
        return new Response(JSON.stringify({
          access: "access-token",
          refresh: "refresh-token",
          accessToken: "access-token",
          refreshToken: "refresh-token",
          mustChangePassword: false,
          user: { ...testStaffUser, id: 2 },
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/auth/logout/")) {
        return new Response(JSON.stringify({ ok: true }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      return new Response(JSON.stringify({ detail: "Not found." }), { headers: { "Content-Type": "application/json" }, status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <SessionProvider validateStoredSession={false}>
        <AuthProbe />
      </SessionProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Backend login" }));
    await screen.findByText("Olivia Frontdesk");

    expect(window.localStorage.getItem(authAccessTokenStorageKey)).toBe("access-token");
    expect(window.localStorage.getItem(authRefreshTokenStorageKey)).toBe("refresh-token");
    expect(JSON.parse(window.localStorage.getItem(authUserStorageKey) ?? "{}").id).toBe("2");
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/auth/login/"), expect.any(Object));

    await user.click(screen.getByRole("button", { name: "Logout" }));
    await screen.findByText("No user");

    expect(window.localStorage.getItem(authAccessTokenStorageKey)).toBeNull();
    expect(window.localStorage.getItem(authRefreshTokenStorageKey)).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/auth/logout/"), expect.any(Object));
  });

  it("clears stored auth state when /auth/me rejects the token", async () => {
    seedAuthSession();
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ detail: "Authentication is required." }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      }),
    ));

    render(
      <SessionProvider>
        <AuthProbe />
      </SessionProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("auth-status")).toHaveTextContent("unauthenticated"));

    expect(screen.getByTestId("auth-error")).toHaveTextContent("Authentication is required.");
    expect(window.localStorage.getItem(authAccessTokenStorageKey)).toBeNull();
    expect(window.localStorage.getItem(authUserStorageKey)).toBeNull();
  });
});

describe("shared UI primitives", () => {
  it("defaults Button to type button", () => {
    render(<Button>Save</Button>);

    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("type", "button");
  });

  it("closes Modal by accessible close button, Escape, and backdrop", () => {
    const onClose = vi.fn();
    const { rerender, container } = render(
      <Modal title="Patient Details" open onClose={onClose}>
        Modal body
      </Modal>,
    );

    expect(screen.getByRole("dialog", { name: "Patient Details" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close modal" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    rerender(
      <Modal title="Patient Details" open onClose={onClose}>
        Modal body
      </Modal>,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);

    rerender(
      <Modal title="Patient Details" open onClose={onClose}>
        Modal body
      </Modal>,
    );
    fireEvent.mouseDown(container.querySelector(".overlay") as HTMLElement);
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("activates DataTable rows with mouse, Enter, and Space", () => {
    const onRowClick = vi.fn();
    const rows = [{ id: "P-1", name: "John Anderson" }];
    const columns: DataColumn<(typeof rows)[number]>[] = [{ header: "Name", cell: (row) => row.name }];

    render(<DataTable columns={columns} rows={rows} getRowKey={(row) => row.id} onRowClick={onRowClick} />);

    const row = screen.getByRole("button", { name: /john anderson/i });
    fireEvent.click(row);
    fireEvent.keyDown(row, { key: "Enter" });
    fireEvent.keyDown(row, { key: " " });

    expect(onRowClick).toHaveBeenCalledTimes(3);
    expect(onRowClick).toHaveBeenLastCalledWith(rows[0]);
  });
});

describe("appointment scheduling logic", () => {
  const mondayShift: BackendShift = {
    id: "SHIFT-1",
    staffOrDoctorId: "DOC-1",
    dayOfWeek: "Monday",
    shiftName: "Morning",
    shiftIndex: 1,
    startTime: "09:00",
    endTime: "13:00",
    isOnLeave: false,
  };

  const existingAppointment: BackendAppointment = {
    id: "APT-1",
    patientId: "PT-1",
    doctorId: "DOC-1",
    visitType: "Routine Checkup",
    date: "2026-02-09",
    time: "10:00",
    durationMinutes: 60,
    due: 0,
    status: "Scheduled",
    notes: "",
  };

  it("detects overlapping appointments for the same doctor", () => {
    const proposedStart = toDateTime("2026-02-09", "10:30");
    const proposedEnd = addMinutes(proposedStart, 30);

    expect(intervalsOverlap(proposedStart, proposedEnd, toDateTime(existingAppointment.date, existingAppointment.time), addMinutes(toDateTime(existingAppointment.date, existingAppointment.time), existingAppointment.durationMinutes))).toBe(true);
  });

  it("blocks leave windows and outside-working-hours slots", () => {
    expect(isDoctorAvailableForInterval({
      doctorId: "DOC-1",
      date: "2026-02-09",
      time: "11:30",
      durationMinutes: 30,
      appointments: [],
      shifts: [mondayShift],
      exceptions: [],
      dayOfWeek: "Monday",
    })).toBe(true);

    expect(isDoctorAvailableForInterval({
      doctorId: "DOC-1",
      date: "2026-02-09",
      time: "13:30",
      durationMinutes: 30,
      appointments: [],
      shifts: [mondayShift],
      exceptions: [],
      dayOfWeek: "Monday",
    })).toBe(false);

    expect(isDoctorAvailableForInterval({
      doctorId: "DOC-1",
      date: "2026-02-09",
      time: "11:30",
      durationMinutes: 30,
      appointments: [],
      shifts: [mondayShift],
      exceptions: [{
        exceptionId: "EXC-1",
        userId: "DOC-1",
        userRole: "Doctor",
        startDateTime: "2026-02-09T11:00",
        endDateTime: "2026-02-09T12:00",
        reason: "Leave",
        status: "Active",
        createdBy: "USR-1",
        createdAt: "2026-02-01T09:00",
      }],
      dayOfWeek: "Monday",
    })).toBe(false);
  });
});

describe("appointments API integration", () => {
  it("maps backend appointment DTOs and omits financial fields from payloads", () => {
    const appointment = adaptAppointmentDTO({
      id: 42,
      patientId: 11,
      patientName: "Backend Patient",
      doctorProfileId: 7,
      doctorName: "Dr. Backend",
      startAt: "2026-02-09T07:00:00Z",
      endAt: "2026-02-09T07:30:00Z",
      durationMinutes: 30,
      visitType: "Routine Checkup",
      status: "Scheduled",
      notes: "Bring x-rays",
      version: 3,
    });

    expect(appointment.patientId).toBe("11");
    expect(appointment.doctorId).toBe("7");
    expect(appointment.doctorProfileId).toBe("7");
    expect(appointment.patientName).toBe("Backend Patient");
    expect(appointment.version).toBe(3);

    const payload = toAppointmentPayload({
      ...appointment,
      date: "2026-02-09",
      time: "09:00",
      durationMinutes: 30,
    });

    expect(payload).toEqual(expect.objectContaining({
      patientId: "11",
      doctorProfileId: "7",
      durationMinutes: 30,
      visitType: "Routine Checkup",
    }));
    expect(payload.startAt).toMatch(/Z$/);
    expect(payload.endAt).toMatch(/Z$/);
    expect(payload).not.toHaveProperty("due");
    expect(payload).not.toHaveProperty("dueAmount");
    expect(payload).not.toHaveProperty("payment");
  });

  it("sends appointment version for workflow status updates", () => {
    const payload = toAppointmentStatusPayload({
      id: "42",
      patientId: "11",
      doctorId: "7",
      date: "2026-02-09",
      time: "09:00",
      durationMinutes: 30,
      visitType: "Routine Checkup",
      status: "Scheduled",
      notes: "",
      version: 3,
    }, "Arrived");

    expect(payload).toEqual({ version: 3 });
  });

  it("creates a backend appointment and shows it immediately without refetching the list", async () => {
    const user = userEvent.setup();
    seedAuthSession();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/appointments/") && method === "GET") {
        return new Response(JSON.stringify({ results: [] }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/patients/")) {
        return new Response(JSON.stringify({
          results: [{ id: 11, patientId: 11, firstName: "Backend", lastName: "Patient", fullName: "Backend Patient", gender: "Male", phoneNumber: "0999999999", version: 1 }],
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/employee-profiles/")) {
        return new Response(JSON.stringify({
          results: [{ id: 7, userId: 70, fullName: "Dr. Backend", email: "doctor@example.com", role: "Doctor", status: "Active", specialty: "General Dentistry", gender: "Female", phone: "0999999998", version: 1 }],
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/working-shifts/")) {
        return new Response(JSON.stringify({
          results: [{ id: 3, employeeProfileId: 7, fullName: "Dr. Backend", role: "Doctor", dayOfWeek: "Monday", startTime: "08:00", endTime: "17:00", isActive: true, version: 1 }],
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/availability-exceptions/")) {
        return new Response(JSON.stringify({ results: [] }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/appointments/") && method === "POST") {
        const body = JSON.parse(String(init?.body));
        expect(body).toEqual(expect.objectContaining({ patientId: "11", doctorProfileId: "7" }));
        expect(body).not.toHaveProperty("due");
        return new Response(JSON.stringify({
          id: 42,
          patientId: 11,
          patientName: "Backend Patient",
          doctorProfileId: 7,
          doctorName: "Dr. Backend",
          startAt: body.startAt,
          endAt: body.endAt,
          durationMinutes: 30,
          visitType: "Routine Checkup",
          status: "Scheduled",
          notes: "",
          version: 1,
        }), { headers: { "Content-Type": "application/json" }, status: 201 });
      }
      return new Response(JSON.stringify({ detail: "Not found." }), { headers: { "Content-Type": "application/json" }, status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <AppointmentsPage />
        </SessionProvider>
      </MemoryRouter>,
    );

    await screen.findByRole("button", { name: "New Appointment" });
    await user.click(screen.getByRole("button", { name: "New Appointment" }));
    fireEvent.change(screen.getByLabelText("Patient"), { target: { value: "Backend Patient" } });
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Backend Patient")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([input, init]) => String(input).endsWith("/api/appointments/") && ((init as RequestInit | undefined)?.method ?? "GET") === "GET")).toHaveLength(1);
  });

  it("shows backend appointment validation errors readably", async () => {
    const user = userEvent.setup();
    seedAuthSession();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/appointments/") && method === "GET") {
        return new Response(JSON.stringify({ results: [] }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/patients/")) {
        return new Response(JSON.stringify({ results: [{ id: 11, patientId: 11, firstName: "Backend", lastName: "Patient", fullName: "Backend Patient", gender: "Male", phoneNumber: "0999999999", version: 1 }] }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/employee-profiles/")) {
        return new Response(JSON.stringify({ results: [{ id: 7, userId: 70, fullName: "Dr. Backend", email: "doctor@example.com", role: "Doctor", status: "Active", specialty: "General Dentistry", gender: "Female", phone: "0999999998", version: 1 }] }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/working-shifts/")) {
        return new Response(JSON.stringify({ results: [{ id: 3, employeeProfileId: 7, dayOfWeek: "Monday", startTime: "08:00", endTime: "17:00", isActive: true, version: 1 }] }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/availability-exceptions/")) {
        return new Response(JSON.stringify({ results: [] }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/appointments/") && method === "POST") {
        return new Response(JSON.stringify({ startAt: ["Outside working shift."] }), { headers: { "Content-Type": "application/json" }, status: 400 });
      }
      return new Response(JSON.stringify({ detail: "Not found." }), { headers: { "Content-Type": "application/json" }, status: 404 });
    }));

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <AppointmentsPage />
        </SessionProvider>
      </MemoryRouter>,
    );

    await screen.findByRole("button", { name: "New Appointment" });
    await user.click(screen.getByRole("button", { name: "New Appointment" }));
    fireEvent.change(screen.getByLabelText("Patient"), { target: { value: "Backend Patient" } });
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("startAt: Outside working shift.")).toBeInTheDocument();
  });

  it("loads doctor appointments from the backend as read-only", async () => {
    seedAuthSession({ ...testStaffUser, role: "Doctor", email: "doctor@example.com", fullName: "Dr. Backend" });
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/appointments/")) {
        return new Response(JSON.stringify({
          results: [{
            id: 42,
            patientId: 11,
            patientName: "Backend Patient",
            doctorProfileId: 7,
            doctorName: "Dr. Backend",
            startAt: "2026-02-09T07:00:00Z",
            endAt: "2026-02-09T07:30:00Z",
            durationMinutes: 30,
            visitType: "Routine Checkup",
            status: "Scheduled",
            notes: "",
            version: 1,
          }],
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/employee-profiles/me/")) {
        return new Response(JSON.stringify({ id: 7, userId: 70, fullName: "Dr. Backend", email: "doctor@example.com", role: "Doctor", status: "Active", specialty: "General Dentistry", gender: "Female", phone: "0999999998", version: 1 }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      return new Response(JSON.stringify({ detail: "Not found." }), { headers: { "Content-Type": "application/json" }, status: 404 });
    }));

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <MyAppointmentsPage />
        </SessionProvider>
      </MemoryRouter>,
    );

    await screen.findByText("Backend Patient");
    fireEvent.click(screen.getByRole("button", { name: /backend patient/i }));
    expect(await screen.findByRole("dialog", { name: "Appointment Details" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });
});

describe("visit lifecycle API integration", () => {
  it("maps backend visit DTOs and omits billing and AI fields from note payloads", () => {
    const visit = adaptVisitDTO({
      id: 8,
      appointmentId: 42,
      patientId: 11,
      patientName: "Backend Patient",
      doctorProfileId: 7,
      doctorName: "Dr. Backend",
      status: "Active",
      subjectiveNotes: "Subjective",
      objectiveNotes: "Objective",
      assessmentNotes: "Assessment",
      planNotes: "Plan",
      generalNotes: "General",
      startedAt: "2026-02-09T07:00:00Z",
      version: 4,
    });

    expect(visit.appointmentId).toBe("42");
    expect(visit.patientName).toBe("Backend Patient");
    expect(visit.doctorProfileId).toBe("7");
    expect(visit.version).toBe(4);

    const payload = toVisitNotesPayload(visit);
    expect(payload).toEqual(expect.objectContaining({
      subjectiveNotes: "Subjective",
      objectiveNotes: "Objective",
      assessmentNotes: "Assessment",
      planNotes: "Plan",
      generalNotes: "General",
      version: 4,
    }));
    expect(payload).not.toHaveProperty("due");
    expect(payload).not.toHaveProperty("payment");
    expect(payload).not.toHaveProperty("invoice");
    expect(payload).not.toHaveProperty("finalDiagnosis");
    expect(payload).not.toHaveProperty("treatmentPlan");
  });

  it("loads active visit from backend and saves notes with version", async () => {
    const user = userEvent.setup();
    seedAuthSession({ ...testStaffUser, role: "Doctor", email: "doctor@example.com", fullName: "Dr. Backend" });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/visits/active/")) {
        return new Response(JSON.stringify({
          id: 8,
          appointmentId: 42,
          patientId: 11,
          patientName: "Backend Patient",
          doctorProfileId: 7,
          doctorName: "Dr. Backend",
          status: "Active",
          subjectiveNotes: "",
          objectiveNotes: "",
          assessmentNotes: "",
          planNotes: "",
          generalNotes: "",
          startedAt: "2026-02-09T07:00:00Z",
          version: 4,
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/visits/8/") && method === "PATCH") {
        const body = JSON.parse(String(init?.body));
        expect(body).toEqual(expect.objectContaining({ subjectiveNotes: "Tooth pain", version: 4 }));
        expect(body).not.toHaveProperty("invoice");
        return new Response(JSON.stringify({
          id: 8,
          appointmentId: 42,
          patientId: 11,
          patientName: "Backend Patient",
          doctorProfileId: 7,
          doctorName: "Dr. Backend",
          status: "Active",
          subjectiveNotes: "Tooth pain",
          objectiveNotes: "",
          assessmentNotes: "",
          planNotes: "",
          generalNotes: "",
          startedAt: "2026-02-09T07:00:00Z",
          version: 5,
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      return new Response(JSON.stringify({ detail: "Not found." }), { headers: { "Content-Type": "application/json" }, status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <ActiveVisitPage />
        </SessionProvider>
      </MemoryRouter>,
    );

    await screen.findByText("Backend Patient");
    await user.type(screen.getByLabelText("Subjective Notes"), "Tooth pain");
    await user.click(screen.getByRole("button", { name: "Save notes" }));
    expect(await screen.findByText("Visit notes saved.")).toBeInTheDocument();
  });

  it("shows empty active visit state when backend has no active visit", async () => {
    seedAuthSession({ ...testStaffUser, role: "Doctor", email: "doctor@example.com", fullName: "Dr. Backend" });
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ detail: "No active visit." }), {
        headers: { "Content-Type": "application/json" },
        status: 404,
      }),
    ));

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <ActiveVisitPage />
        </SessionProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("No active visit. Start a checked-in appointment from My Appointments.")).toBeInTheDocument();
  });

  it("completes an active visit using the backend endpoint", async () => {
    const user = userEvent.setup();
    seedAuthSession({ ...testStaffUser, role: "Doctor", email: "doctor@example.com", fullName: "Dr. Backend" });
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/visits/active/")) {
        return new Response(JSON.stringify({
          id: 8,
          appointmentId: 42,
          patientId: 11,
          patientName: "Backend Patient",
          doctorProfileId: 7,
          doctorName: "Dr. Backend",
          status: "Active",
          subjectiveNotes: "",
          objectiveNotes: "",
          assessmentNotes: "",
          planNotes: "",
          generalNotes: "",
          startedAt: "2026-02-09T07:00:00Z",
          version: 4,
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/visits/8/complete/")) {
        expect(JSON.parse(String(init?.body))).toEqual(expect.objectContaining({ version: 4 }));
        return new Response(JSON.stringify({
          visit: {
            id: 8,
            appointmentId: 42,
            patientId: 11,
            patientName: "Backend Patient",
            doctorProfileId: 7,
            doctorName: "Dr. Backend",
            status: "Completed",
            subjectiveNotes: "",
            objectiveNotes: "",
            assessmentNotes: "",
            planNotes: "",
            generalNotes: "",
            startedAt: "2026-02-09T07:00:00Z",
            completedAt: "2026-02-09T07:30:00Z",
            version: 5,
          },
          appointment: {
            id: 42,
            patientId: 11,
            patientName: "Backend Patient",
            doctorProfileId: 7,
            doctorName: "Dr. Backend",
            startAt: "2026-02-09T07:00:00Z",
            endAt: "2026-02-09T07:30:00Z",
            durationMinutes: 30,
            visitType: "Routine Checkup",
            status: "Completed",
            notes: "",
            version: 6,
          },
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      return new Response(JSON.stringify({ detail: "Not found." }), { headers: { "Content-Type": "application/json" }, status: 404 });
    }));

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <ActiveVisitPage />
        </SessionProvider>
      </MemoryRouter>,
    );

    await screen.findByText("Backend Patient");
    await user.click(screen.getByRole("button", { name: "Complete visit" }));
    expect(await screen.findByText("Visit completed.")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });
});

describe("working shifts and leave API adapters", () => {
  it("maps backend working shifts to UI rows with version and active state", () => {
    const shift = adaptWorkingShiftDTO({
      id: 10,
      employeeProfileId: 4,
      fullName: "Dr. Shift Test",
      role: "Doctor",
      dayOfWeek: "Monday",
      startTime: "09:00",
      endTime: "13:00",
      isActive: true,
      version: 2,
    }, 1);

    expect(shift.staffOrDoctorId).toBe("4");
    expect(shift.employeeProfileId).toBe("4");
    expect(shift.employeeName).toBe("Dr. Shift Test");
    expect(shift.isActive).toBe(true);
    expect(shift.isOnLeave).toBe(false);
    expect(shift.version).toBe(2);
  });

  it("sends isActive to the working shifts API instead of isOnLeave", () => {
    const payload = toWorkingShiftPayload({
      id: "10",
      staffOrDoctorId: "4",
      employeeProfileId: "4",
      dayOfWeek: "Monday",
      shiftName: "Morning",
      shiftIndex: 1,
      startTime: "09:00",
      endTime: "13:00",
      isActive: false,
      isOnLeave: true,
    });

    expect(payload).toEqual(expect.objectContaining({ employeeProfileId: "4", isActive: false }));
    expect(payload).not.toHaveProperty("isOnLeave");
  });

  it("maps backend leave exceptions to UI rows with version and timestamps", () => {
    const exception = adaptAvailabilityExceptionDTO({
      id: 12,
      employeeProfileId: 4,
      fullName: "Dr. Leave Test",
      role: "Doctor",
      startAt: "2026-03-10T07:00:00Z",
      endAt: "2026-03-10T11:00:00Z",
      reason: "Leave",
      note: "",
      status: "Active",
      version: 3,
    });

    expect(exception.exceptionId).toBe("12");
    expect(exception.userId).toBe("4");
    expect(exception.employeeProfileId).toBe("4");
    expect(exception.startDateTime).toBe("2026-03-10T07:00:00Z");
    expect(exception.endDateTime).toBe("2026-03-10T11:00:00Z");
    expect(exception.version).toBe(3);
  });

  it("keeps leave reason required while omitting blank optional notes", () => {
    const payload = toAvailabilityExceptionPayload({
      exceptionId: "12",
      userId: "4",
      employeeProfileId: "4",
      userRole: "Doctor",
      startDateTime: "2026-03-10T09:00",
      endDateTime: "2026-03-10T13:00",
      reason: "Leave",
      note: "   ",
      status: "Active",
      createdBy: "1",
      createdAt: "2026-03-01T09:00",
    });

    expect(payload.reason).toBe("Leave");
    expect(payload).not.toHaveProperty("note");
    expect(payload.startAt).toMatch(/Z$/);
  });
});

describe("mock persistence and billing calculations", () => {
  it("sends optional patient email when creating a backend patient", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();

    render(<PatientCreateModal open onClose={vi.fn()} onCreate={onCreate} />);

    await user.type(screen.getByLabelText("First Name"), "Email");
    await user.type(screen.getByLabelText("Last Name"), "Patient");
    await user.type(screen.getByLabelText("National ID / Passport"), "NID-EMAIL");
    fireEvent.change(screen.getByLabelText("Date of Birth"), { target: { value: "1990-01-01" } });
    await user.type(screen.getByLabelText("Phone Number"), "0999999999");
    await user.type(screen.getByLabelText("Email"), "email.patient@example.com");
    await user.type(screen.getByLabelText("Emergency Contact"), "Emergency 0999999998");
    await user.type(screen.getByLabelText("Address"), "123 Email Street");
    await user.type(screen.getByLabelText("Insurance Info"), "Policy EMAIL");
    await user.type(screen.getByLabelText("Medical Conditions History"), "None");
    await user.click(screen.getByRole("button", { name: "Create Patient" }));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({
        email: "email.patient@example.com",
        gender: "Male",
      }));
    });
    expect(onCreate.mock.calls[0][0]).not.toHaveProperty("sex");
  });

  it("allows backend-optional patient fields to remain blank without sending literal null", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();

    render(<PatientCreateModal open onClose={vi.fn()} onCreate={onCreate} />);

    await user.type(screen.getByLabelText("First Name"), "Blank");
    await user.type(screen.getByLabelText("Last Name"), "Optional");
    await user.type(screen.getByLabelText("National ID / Passport"), "NID-BLANK");
    fireEvent.change(screen.getByLabelText("Date of Birth"), { target: { value: "1990-01-01" } });
    await user.type(screen.getByLabelText("Phone Number"), "0999999999");
    await user.click(screen.getByRole("button", { name: "Create Patient" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalled());
    const payload = onCreate.mock.calls[0][0];
    expect(payload).toEqual(expect.objectContaining({
      address: "",
      bloodGroup: "",
      emergencyContact: "",
      insuranceInfo: "",
      medicalConditionsHistory: "",
    }));
    expect(JSON.stringify(payload)).not.toContain("null");
  });

  it("renders backend patient list results without showing a backend reachability error", async () => {
    seedAuthSession();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/patients/")) {
        return new Response(JSON.stringify({
          results: [
            {
              id: 11,
              patientId: 11,
              firstName: "Boom",
              lastName: "Ph",
              fullName: "Boom Ph",
              gender: "Male",
              dateOfBirth: "2002-07-02",
              age: 24,
              phoneNumber: "0999999999",
              version: 1,
            },
          ],
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      return new Response(JSON.stringify({ detail: "Not found." }), { headers: { "Content-Type": "application/json" }, status: 404 });
    }));

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <PatientsPage />
        </SessionProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Boom Ph")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "All Patients (1)" })).toBeInTheDocument();
    expect(screen.queryByText("Cannot reach the backend. Make sure the backend server is running and try again.")).not.toBeInTheDocument();
  });

  it("places a newly created backend patient at the top and uses response fields immediately", async () => {
    const user = userEvent.setup();
    seedAuthSession();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/patients/") && method === "GET") {
        return new Response(JSON.stringify({
          results: [
            {
              id: 11,
              patientId: 11,
              firstName: "Existing",
              lastName: "Patient",
              fullName: "Existing Patient",
              gender: "Male",
              dateOfBirth: "1990-01-01",
              age: 36,
              phoneNumber: "0111111111",
              version: 1,
            },
          ],
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/patients/") && method === "POST") {
        return new Response(JSON.stringify({
          id: 22,
          patientId: 22,
          firstName: "Newest",
          lastName: "Patient",
          fullName: "Newest Patient",
          gender: "Female",
          dateOfBirth: "2002-07-02",
          age: 24,
          phoneNumber: "0222222222",
          email: "newest.patient@example.com",
          nationalIdOrPassport: "NID-NEWEST",
          version: 7,
        }), { headers: { "Content-Type": "application/json" }, status: 201 });
      }
      if (url.endsWith("/api/patients/22/") && method === "PATCH") {
        expect(JSON.parse(String(init?.body))).toEqual(expect.objectContaining({ version: 7 }));
        return new Response(JSON.stringify({
          id: 22,
          patientId: 22,
          firstName: "Newest",
          lastName: "Patient",
          fullName: "Newest Patient",
          gender: "Female",
          dateOfBirth: "2002-07-02",
          age: 24,
          phoneNumber: "0222222222",
          email: "newest.patient@example.com",
          nationalIdOrPassport: "NID-NEWEST",
          version: 8,
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      return new Response(JSON.stringify({ detail: "Not found." }), { headers: { "Content-Type": "application/json" }, status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <PatientsPage />
        </SessionProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Existing Patient")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add Patient" }));
    await user.type(screen.getByLabelText("First Name"), "Newest");
    await user.type(screen.getByLabelText("Last Name"), "Patient");
    await user.type(screen.getByLabelText("National ID / Passport"), "NID-NEWEST");
    fireEvent.change(screen.getByLabelText("Date of Birth"), { target: { value: "2002-07-02" } });
    fireEvent.change(screen.getByLabelText("Sex"), { target: { value: "Female" } });
    await user.type(screen.getByLabelText("Phone Number"), "0222222222");
    await user.type(screen.getByLabelText("Email"), "newest.patient@example.com");
    await user.click(screen.getByRole("button", { name: "Create Patient" }));

    await screen.findByRole("heading", { name: "All Patients (2)" });
    const rows = Array.from(document.querySelectorAll(".data-table tbody tr"));
    expect(rows[0].textContent).toContain("Newest Patient");
    expect(rows[0].textContent).toContain("24 years");
    expect(rows[1].textContent).toContain("Existing Patient");
    expect(screen.queryByText("Cannot reach the backend. Make sure the backend server is running and try again.")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([input, init]) => String(input).endsWith("/api/patients/") && ((init as RequestInit | undefined)?.method ?? "GET") === "GET")).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Save Changes" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/patients/22/"), expect.objectContaining({ method: "PATCH" })));
  });

  it("saves and reloads patient create/edit data from localStorage", () => {
    const patient: BackendPatient = {
      patientId: "PT-LOCAL",
      firstName: "Local",
      lastName: "Patient",
      nationalIdOrPassport: "NID-LOCAL",
      dateOfBirth: "1990-01-01",
      gender: "Female",
      phoneNumber: "(555) 000-1111",
      medicalConditionsHistory: "None",
      bloodGroup: "O+",
      insuranceInfo: "Demo",
      emergencyContact: "(555) 000-2222",
      address: "123 Test Street",
      createdAt: "2026-02-09",
      email: "local.patient@example.com",
    };

    saveMockPatients([patient]);

    expect(loadMockPatients()).toEqual([patient]);
  });

  it("calculates invoice status from paid amount", () => {
    expect(calculateInvoiceStatus(100, 0)).toBe("Pending");
    expect(calculateInvoiceStatus(100, 25)).toBe("Partially Paid");
    expect(calculateInvoiceStatus(100, 100)).toBe("Paid");
    expect(calculateInvoiceStatus(100, 100, true)).toBe("Cancelled");
  });

  it("calculates age against the supplied reference date", () => {
    expect(ageFromDate("1990-07-01", new Date("2026-06-30T00:00:00"))).toBe(35);
    expect(ageFromDate("1990-06-30", new Date("2026-06-30T00:00:00"))).toBe(36);
  });
});

describe("payment modal", () => {
  const invoice: BackendInvoice = {
    id: "INV-TEST",
    visitId: "VIS-1",
    patientId: "PT-1044",
    doctorId: "DOC-1",
    invoiceDate: "2026-02-09",
    totalAmount: 100,
    paidAmount: 0,
    balance: 100,
    status: "Pending",
  };
  const cancelledInvoice: BackendInvoice = {
    ...invoice,
    id: "INV-CANCELLED",
    paidAmount: 25,
    balance: 75,
    status: "Cancelled",
  };

  it("uses cash-only payment and blocks overpayment before saving", async () => {
    const user = userEvent.setup();
    const onPaymentSaved = vi.fn();
    render(<PaymentModal invoice={invoice} open onClose={vi.fn()} onPaymentSaved={onPaymentSaved} />);

    expect(screen.getByLabelText("Payment Method")).toHaveValue("Cash");
    expect(screen.queryByRole("option", { name: "Card" })).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Amount to pay"), "101");
    await user.click(screen.getByRole("button", { name: "Confirm Payment" }));
    expect(screen.getByText("Enter a positive amount that does not exceed the remaining balance.")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Amount to pay"));
    await user.type(screen.getByLabelText("Amount to pay"), "100");
    await user.click(screen.getByRole("button", { name: "Confirm Payment" }));

    expect(onPaymentSaved).toHaveBeenCalledWith(expect.objectContaining({
      id: "INV-TEST",
      status: "Paid",
      balance: 0,
    }));
  });

  it("does not open for a cancelled invoice", () => {
    render(<PaymentModal invoice={cancelledInvoice} open onClose={vi.fn()} onPaymentSaved={vi.fn()} />);

    expect(screen.queryByRole("dialog", { name: "Process Payment" })).not.toBeInTheDocument();
  });
});

describe("invoice details cancelled state", () => {
  const cancelledInvoice: BackendInvoice = {
    id: "INV-CANCELLED",
    visitId: "VIS-1",
    patientId: "PT-1044",
    doctorId: "DOC-1",
    invoiceDate: "2026-02-09",
    totalAmount: 100,
    paidAmount: 25,
    balance: 75,
    status: "Cancelled",
  };

  it("locks cancelled invoices while keeping print and export available", () => {
    const onProcessPayment = vi.fn();
    const onSave = vi.fn();

    render(
      <InvoiceDetails
        invoice={cancelledInvoice}
        open
        onClose={vi.fn()}
        onProcessPayment={onProcessPayment}
        onSave={onSave}
        canEditInvoice
        canProcessPayment
      />,
    );

    expect(screen.getByText("This invoice has been cancelled and cannot be modified.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Print Invoice" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Export PDF" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Process Payment" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel Invoice" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Already Cancelled" })).toBeDisabled();
    expect(screen.queryByLabelText("Total amount")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Status")).not.toBeInTheDocument();
    expect(screen.getByText("Remaining")).toBeInTheDocument();
    expect(onProcessPayment).not.toHaveBeenCalled();
    expect(onSave).not.toHaveBeenCalled();
  });
});

describe("admin navigation and users", () => {
  it("removes Roles & Permissions from admin navigation and routes", () => {
    expect(navConfig.Admin.map((item) => item.label)).not.toContain("Roles & Permissions");
    expect("rolesPermissions" in routes.admin).toBe(false);
  });

  it("keeps users table row-click editing without an actions column", async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    expect(screen.queryByRole("columnheader", { name: "Actions" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /dr\. sarah wilson/i }));

    const dialog = screen.getByRole("dialog", { name: "Edit User" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByLabelText("Role")).toBeInTheDocument();
  });
});

describe("detail drawer layout", () => {
  const staff: BackendStaffProfile = {
    id: "DOC-LAYOUT",
    userId: "USR-LAYOUT",
    fullName: "Dr. Layout Tester",
    role: "Doctor",
    specialty: "General Dentistry",
    gender: "Female",
    email: "layout@example.com",
    phone: "(555) 010-2020",
    status: "Active",
  };
  const shifts: BackendShift[] = [
    {
      id: "SHIFT-MON-MORNING",
      staffOrDoctorId: staff.id,
      dayOfWeek: "Monday",
      shiftName: "Morning",
      shiftIndex: 1,
      startTime: "08:30",
      endTime: "13:00",
      isOnLeave: false,
    },
    {
      id: "SHIFT-TUE-EVENING",
      staffOrDoctorId: staff.id,
      dayOfWeek: "Tuesday",
      shiftName: "Evening",
      shiftIndex: 2,
      startTime: "14:00",
      endTime: "17:00",
      isOnLeave: false,
    },
  ];
  const leave: BackendAvailabilityException = {
    exceptionId: "LEAVE-LAYOUT",
    userId: staff.id,
    userRole: "Doctor",
    startDateTime: "2026-02-09T09:00",
    endDateTime: "2026-02-09T12:00",
    reason: "Training",
    note: "Long leave note stays wrapped inside the detail panel.",
    status: "Active",
    createdBy: "USR-1",
    createdAt: "2026-02-01T09:00",
  };

  it("renders the staff schedule as a day-by-shift matrix", () => {
    render(<GroupedShiftsTable shifts={shifts} />);

    expect(screen.getByRole("table")).toHaveClass("schedule-matrix");
    expect(screen.getByRole("columnheader", { name: "Mon" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Sun" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Monday" })).not.toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "Morning" })).toBeInTheDocument();
    expect(screen.getByText("08:30-13:00")).toBeInTheDocument();
    expect(screen.getAllByText("Off").length).toBeGreaterThan(0);
  });

  it("uses the wide shared staff detail drawer with compact tabs and contained leave content", async () => {
    const user = userEvent.setup();
    seedAuthSession();
    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <StaffProfileDrawer
            staff={staff}
            open
            onClose={vi.fn()}
            onEditWorkingHours={vi.fn()}
            shifts={shifts}
            appointments={[]}
            availabilityExceptions={[leave]}
          />
        </SessionProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("dialog", { name: "Doctor/Staff Profile" })).toBeInTheDocument();
    expect(document.querySelector(".detail-layout.staff-profile-drawer")).toBeInTheDocument();
    ["General", "Schedule", "Leave", "Appointments", "Notes"].forEach((label) => {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Schedule" }));
    expect(screen.getByRole("table")).toHaveClass("schedule-matrix");

    await user.click(screen.getByRole("button", { name: "Leave" }));
    expect(screen.getByText("Training")).toBeInTheDocument();
    expect(screen.getByText("Long leave note stays wrapped inside the detail panel.")).toBeInTheDocument();
    expect(screen.getByText("0 affected")).toBeInTheDocument();
  });

  it("uses the same wide detail drawer pattern for patient records", () => {
    seedAuthSession();
    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <PatientProfileDrawer patient={defaultPatient} open onClose={vi.fn()} />
        </SessionProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("dialog", { name: "Patient Details" })).toBeInTheDocument();
    expect(document.querySelector(".detail-layout.patient-drawer")).toBeInTheDocument();
    ["General", "History", "X-rays", "Billing", "Appointments"].forEach((label) => {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    });
  });

  it("places staff profile leave exceptions under the schedule column", async () => {
    seedAuthSession();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/employee-profiles/me/")) {
        return new Response(JSON.stringify({
          id: "DOC-001",
          userId: testStaffUser.id,
          username: testStaffUser.username,
          fullName: testStaffUser.fullName,
          email: testStaffUser.email,
          role: "Staff",
          status: "Active",
          specialty: "Reception / Staff",
          gender: "Female",
          phone: testStaffUser.phone,
          avatarUrl: "",
          version: 1,
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/working-shifts/")) {
        return new Response(JSON.stringify({
          results: [{
            id: "SHIFT-001",
            employeeProfileId: "DOC-001",
            dayOfWeek: "Monday",
            startTime: "09:00",
            endTime: "13:00",
            isActive: true,
            version: 1,
          }],
        }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      if (url.endsWith("/api/availability-exceptions/")) {
        return new Response(JSON.stringify({ results: [] }), { headers: { "Content-Type": "application/json" }, status: 200 });
      }
      return new Response(JSON.stringify({ detail: "Not found." }), { headers: { "Content-Type": "application/json" }, status: 404 });
    }));

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <SettingsPage />
        </SessionProvider>
      </MemoryRouter>,
    );

    await screen.findByText("Leave Exceptions");

    const profileGrid = document.querySelector(".profile-page-grid");
    const scheduleColumn = document.querySelector(".profile-schedule-column");
    const workingHoursCard = document.querySelector(".working-hours-card");
    const leaveCard = document.querySelector(".leave-exceptions-card");

    expect(profileGrid).toBeInTheDocument();
    expect(scheduleColumn).toContainElement(workingHoursCard as HTMLElement);
    expect(scheduleColumn).toContainElement(leaveCard as HTMLElement);
    expect(workingHoursCard?.compareDocumentPosition(leaveCard as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByRole("columnheader", { name: "Mon" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Sun" })).toBeInTheDocument();
  });
});

describe("XrayViewer", () => {
  const result: BackendAIResult = {
    analysisId: "AI-TEST",
    fileId: "FILE-TEST",
    resultSummary: "Completed",
    overallConfidence: 0.82,
    processedDate: "2026-02-09",
    modelVersion: "DentalVision-R 0.8",
    status: "Completed",
    overlayFilePath: "mock-overlay://test.png",
  };

  it("renders overlay toggle and zoom controls", async () => {
    const user = userEvent.setup();
    const { container } = render(<XrayViewer result={result} findings={[]} />);

    expect(screen.getByText("AI analysis is assistive educational/research output and must be reviewed by the doctor.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(container.querySelector(".xray-canvas")).toHaveStyle({ transform: "scale(1.1)" });

    const toggle = screen.getByRole("button", { name: "Show AI overlay" });
    await user.click(toggle);
    expect(container.querySelector(".xray-overlay")).not.toHaveClass("visible");
  });

  it("wires retry for failed analysis", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    render(<XrayViewer result={{ ...result, status: "Failed", overlayFilePath: "" }} findings={[]} onRetryAnalysis={retry} />);

    await user.click(screen.getByRole("button", { name: "Retry analysis" }));

    expect(retry).toHaveBeenCalledTimes(1);
  });
});
