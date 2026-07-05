import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { AppLayout } from "./components/layout/AppLayout";
import { useSession } from "./context/SessionContext";
import { roleHome } from "./navigation/navConfig";
import { AdminDashboardPage } from "./pages/admin/AdminDashboardPage";
import { DoctorsStaffPage } from "./pages/admin/DoctorsStaffPage";
import { UsersPage } from "./pages/admin/UsersPage";
import { LoginPage } from "./pages/auth/LoginPage";
import { ForgotPasswordPage } from "./pages/auth/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/auth/ResetPasswordPage";
import { ActiveVisitPage } from "./pages/doctor/ActiveVisitPage";
import { DoctorDashboardPage } from "./pages/doctor/DoctorDashboardPage";
import { DoctorPatientRecordsPage } from "./pages/doctor/DoctorPatientRecordsPage";
import { MyAppointmentsPage } from "./pages/doctor/MyAppointmentsPage";
import { AppointmentsPage } from "./pages/staff/AppointmentsPage";
import { BillingPage } from "./pages/staff/BillingPage";
import { PatientsPage } from "./pages/staff/PatientsPage";
import { StaffDashboardPage } from "./pages/staff/StaffDashboardPage";
import { NotFoundPage } from "./pages/shared/NotFoundPage";
import { PermissionDeniedPage } from "./pages/shared/PermissionDeniedPage";
import { SettingsPage } from "./pages/shared/SettingsPage";
import { routes } from "./routes";
import type { Role } from "./types/models";

function RoleGate({ role, children }: { role: Role; children: ReactNode }) {
  const { authStatus, currentUser } = useSession();
  const location = useLocation();

  if (authStatus === "loading") {
    return <SessionLoadingPage />;
  }
  if (!currentUser) {
    return <Navigate to={routes.auth.login} replace state={{ from: location.pathname }} />;
  }

  return currentUser.role === role ? children : <PermissionDeniedPage />;
}

function HomeRedirect() {
  const { authStatus, currentUser } = useSession();

  if (authStatus === "loading") {
    return <SessionLoadingPage />;
  }
  return currentUser ? <Navigate to={roleHome[currentUser.role]} replace /> : <Navigate to={routes.auth.login} replace />;
}

function LoginRoute() {
  const { authStatus, currentUser } = useSession();

  if (authStatus === "loading") {
    return <SessionLoadingPage />;
  }
  return currentUser ? <Navigate to={roleHome[currentUser.role]} replace /> : <LoginPage />;
}

function SessionLoadingPage() {
  return (
    <main className="auth-page">
      <section className="auth-card stack" aria-live="polite">
        <strong>DentalCare</strong>
        <p className="page-subtitle">Checking your session...</p>
      </section>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      <Route element={<RoleGate role="Admin"><AppLayout role="Admin" /></RoleGate>}>
        <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
        <Route path="/admin/users" element={<UsersPage />} />
        <Route path="/admin/doctors-staff" element={<DoctorsStaffPage />} />
        <Route path="/admin/appointments" element={<AppointmentsPage />} />
        <Route path="/admin/patients" element={<PatientsPage />} />
        <Route path="/admin/billing" element={<BillingPage />} />
        <Route path="/admin/settings" element={<SettingsPage />} />
      </Route>

      <Route element={<RoleGate role="Staff"><AppLayout role="Staff" /></RoleGate>}>
        <Route path="/staff/dashboard" element={<StaffDashboardPage />} />
        <Route path="/staff/appointments" element={<AppointmentsPage />} />
        <Route path="/staff/patients" element={<PatientsPage />} />
        <Route path="/staff/billing" element={<BillingPage />} />
        <Route path="/staff/doctors-staff" element={<DoctorsStaffPage readOnly />} />
        <Route path="/staff/profile" element={<SettingsPage />} />
        <Route path="/staff/settings" element={<Navigate to={routes.staff.profile} replace />} />
      </Route>

      <Route element={<RoleGate role="Doctor"><AppLayout role="Doctor" /></RoleGate>}>
        <Route path="/doctor/dashboard" element={<DoctorDashboardPage />} />
        <Route path="/doctor/appointments" element={<MyAppointmentsPage />} />
        <Route path="/doctor/patients" element={<DoctorPatientRecordsPage />} />
        <Route path="/doctor/active-visit" element={<ActiveVisitPage />} />
        <Route path="/doctor/profile" element={<SettingsPage />} />
        <Route path="/doctor/my-appointments" element={<Navigate to={routes.doctor.appointments} replace />} />
        <Route path="/doctor/patient-records" element={<Navigate to={routes.doctor.patients} replace />} />
        <Route path="/doctor/settings" element={<Navigate to={routes.doctor.profile} replace />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
