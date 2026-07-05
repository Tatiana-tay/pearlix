import { useState } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { XrayViewer } from "../components/ai/XrayViewer";
import { InvoiceDetails } from "../components/billing/InvoiceDetails";
import { PaymentModal } from "../components/billing/PaymentModal";
import { PatientProfileDrawer, defaultPatient } from "../components/patients/PatientProfileDrawer";
import { GroupedShiftsTable } from "../components/staff/GroupedShiftsTable";
import { StaffProfileDrawer } from "../components/staff/StaffProfileDrawer";
import { DataTable, type DataColumn } from "../components/tables/DataTable";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { authAccessTokenStorageKey, authRefreshTokenStorageKey, authUserStorageKey, SessionProvider, useSession } from "../context/SessionContext";
import { navConfig } from "../navigation/navConfig";
import { UsersPage } from "../pages/admin/UsersPage";
import { SettingsPage } from "../pages/shared/SettingsPage";
import { routes } from "../routes";
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

describe("mock persistence and billing calculations", () => {
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

  it("places staff profile leave exceptions under the schedule column", () => {
    seedAuthSession();

    render(
      <MemoryRouter>
        <SessionProvider validateStoredSession={false}>
          <SettingsPage />
        </SessionProvider>
      </MemoryRouter>,
    );

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
