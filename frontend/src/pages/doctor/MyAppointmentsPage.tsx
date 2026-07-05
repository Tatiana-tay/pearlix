import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { adaptAppointmentDTO, listAppointments } from "../../api/appointments";
import { getCurrentEmployeeProfile, adaptEmployeeProfileDTO } from "../../api/employeeProfiles";
import { isApiError } from "../../api/errors";
import { adaptVisitWorkflowResponse, startVisit } from "../../api/visits";
import { AppointmentModal } from "../../components/appointments/AppointmentModal";
import { PageHeader } from "../../components/layout/PageHeader";
import { PatientProfileDrawer } from "../../components/patients/PatientProfileDrawer";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { FilterPopover } from "../../components/ui/FilterPopover";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { useCurrentUser, useSession } from "../../context/SessionContext";
import { getPatientById } from "../../data/adapters";
import { routes } from "../../routes";
import type { BackendAppointment, BackendPatient, BackendStaffProfile } from "../../types/models";
import { fullPatientName } from "../../utils/format";
import { saveActiveVisitAppointmentId } from "../../utils/mockClinicState";
import { appointmentStatusTone } from "../../utils/statusStyles";

export function MyAppointmentsPage() {
  const navigate = useNavigate();
  const currentUser = useCurrentUser();
  const { accessToken, clearSession } = useSession();
  const [selectedAppointment, setSelectedAppointment] = useState<BackendAppointment | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [visitTypeFilter, setVisitTypeFilter] = useState("All");
  const [selectedPatient, setSelectedPatient] = useState<BackendPatient | null>(null);
  const [appointments, setAppointments] = useState<BackendAppointment[]>([]);
  const [doctorProfile, setDoctorProfile] = useState<BackendStaffProfile | null>(null);
  const [loadingAppointments, setLoadingAppointments] = useState(true);
  const [pageError, setPageError] = useState("");
  const patientRows = useMemo<BackendPatient[]>(() => [], []);
  const staffProfiles = useMemo(() => doctorProfile ? [doctorProfile] : [], [doctorProfile]);
  const visitTypes = useMemo(() => ["All", ...Array.from(new Set(appointments.map((appointment) => appointment.visitType)))], [appointments]);

  useEffect(() => {
    if (!accessToken) {
      setLoadingAppointments(false);
      setPageError("Sign in again to view your appointments.");
      return;
    }

    let cancelled = false;
    setLoadingAppointments(true);
    setPageError("");

    Promise.all([
      listAppointments({ accessToken }),
      getCurrentEmployeeProfile({ accessToken }),
    ])
      .then(([appointmentResults, profile]) => {
        if (cancelled) return;
        const adaptedProfile = adaptEmployeeProfileDTO(profile);
        setDoctorProfile(adaptedProfile);
        setAppointments(appointmentResults.map(adaptAppointmentDTO));
        setPageError("");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        handleAuthError(error, clearSession);
        setPageError(toAppointmentErrorMessage(error, "Unable to load your appointments."));
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingAppointments(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, clearSession]);

  const filteredAppointments = useMemo(() => {
    const normalized = query.toLowerCase();
    return appointments.filter((appointment) => {
      const patient = patientRows.find((item) => item.patientId === appointment.patientId) ?? getPatientById(appointment.patientId);
      const text = `${patient ? fullPatientName(patient) : appointment.patientId} ${appointment.visitType} ${appointment.date} ${appointment.time}`.toLowerCase();
      const matchesStatus = statusFilter === "All" || appointment.status === statusFilter;
      const matchesVisitType = visitTypeFilter === "All" || appointment.visitType === visitTypeFilter;
      return text.includes(normalized) && matchesStatus && matchesVisitType;
    });
  }, [appointments, patientRows, query, statusFilter, visitTypeFilter]);

  const activeFilters = (statusFilter !== "All" ? 1 : 0) + (visitTypeFilter !== "All" ? 1 : 0);

  const openActiveVisit = (appointment: BackendAppointment) => {
    saveActiveVisitAppointmentId(appointment.id);
    navigate(routes.doctor.activeVisit);
  };

  const startBackendVisit = async (appointment: BackendAppointment) => {
    if (!accessToken) {
      throw new Error("Sign in again to start visits.");
    }
    if (typeof appointment.version !== "number") {
      throw new Error("Missing appointment version. Refresh appointments and try again.");
    }
    try {
      const { appointment: updatedAppointment } = adaptVisitWorkflowResponse(await startVisit(appointment.id, appointment.version, { accessToken }));
      setAppointments((current) => current.map((item) => item.id === updatedAppointment.id ? updatedAppointment : item));
      setSelectedAppointment(updatedAppointment);
      saveActiveVisitAppointmentId(updatedAppointment.id);
      return updatedAppointment;
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toAppointmentErrorMessage(error, "Unable to start visit."));
    }
  };

  return (
    <div className="page-shell">
      <PageHeader title="My Appointments" subtitle="Doctor-focused appointment schedule." />
      {pageError && <div className="alert-card">{pageError}</div>}
      <Card>
        <div className="filter-card">
          <Input icon={<Search size={18} />} placeholder="Search appointments by patient, visit type, date, or time..." value={query} onChange={(event) => setQuery(event.target.value)} />
          <FilterPopover activeCount={activeFilters}>
            <div className="filter-popover-content">
              <Select label="Status" options={["All", "Scheduled", "Arrived", "Checked-in", "In Visit", "Completed", "Cancelled", "No-show", "Postponed", "Needs Reschedule"]} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} />
              <Select label="Visit type" options={visitTypes} value={visitTypeFilter} onChange={(event) => setVisitTypeFilter(event.target.value)} />
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setStatusFilter("All");
                  setVisitTypeFilter("All");
                }}
              >
                Clear filters
              </Button>
            </div>
          </FilterPopover>
        </div>
      </Card>
      <Card>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Patient</th>
                <th>Visit Type</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredAppointments.map((appointment) => {
                const patient = patientRows.find((item) => item.patientId === appointment.patientId);
                const canOpenVisit = appointment.status === "Checked-in" || appointment.status === "In Visit";
                return (
                  <tr
                    key={appointment.id}
                    className="clickable"
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedAppointment(appointment)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedAppointment(appointment);
                      }
                    }}
                  >
                    <td>{appointment.date} - {appointment.time}</td>
                    <td>{appointment.patientName || (patient ? fullPatientName(patient) : appointment.patientId)}</td>
                    <td>{appointment.visitType}</td>
                    <td><Badge tone={appointmentStatusTone[appointment.status]}>{appointment.status}</Badge></td>
                    <td>
                      <div className="table-actions">
                        <Button
                          variant="ghost"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedPatient(patient ?? null);
                          }}
                        >
                          Open Patient Profile
                        </Button>
                        <Button
                          variant="ghost"
                          type="button"
                          disabled={!canOpenVisit}
                          onClick={(event) => {
                            event.stopPropagation();
                            openActiveVisit(appointment);
                          }}
                        >
                          {appointment.status === "In Visit" ? "Continue Visit" : "Start Visit"}
                        </Button>
                        <Button
                          variant="secondary"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedAppointment(appointment);
                          }}
                        >
                          View Details
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {loadingAppointments && <div className="empty-inline">Loading appointments...</div>}
          {!loadingAppointments && filteredAppointments.length === 0 && <div className="empty-inline">No appointments found.</div>}
        </div>
      </Card>
      <AppointmentModal
        appointment={selectedAppointment}
        mode="view"
        appointments={appointments}
        patientOptions={patientRows}
        staffOptions={staffProfiles}
        open={Boolean(selectedAppointment)}
        onClose={() => setSelectedAppointment(null)}
        onStartVisit={startBackendVisit}
      />
      <PatientProfileDrawer open={Boolean(selectedPatient)} onClose={() => setSelectedPatient(null)} patient={selectedPatient} canEdit />
    </div>
  );
}

function handleAuthError(error: unknown, clearSession: (message?: string) => void) {
  if (isApiError(error) && error.status === 401) {
    clearSession("Your session has expired. Please sign in again.");
  }
}

function toAppointmentErrorMessage(error: unknown, fallback: string) {
  if (isApiError(error)) {
    if (error.status === 409) {
      return "This visit was updated elsewhere. Please refresh and try again.";
    }
    return error.message || fallback;
  }
  if (error instanceof TypeError) {
    return "Cannot reach the backend. Make sure the backend server is running and try again.";
  }
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}
