import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AppointmentModal } from "../../components/appointments/AppointmentModal";
import { PageHeader } from "../../components/layout/PageHeader";
import { PatientProfileDrawer } from "../../components/patients/PatientProfileDrawer";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { FilterPopover } from "../../components/ui/FilterPopover";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { useSession } from "../../context/SessionContext";
import { getPatientById, patients } from "../../data/adapters";
import { routes } from "../../routes";
import type { AppointmentStatus, BackendAppointment, BackendPatient } from "../../types/models";
import { fullPatientName } from "../../utils/format";
import { getMockStaffProfileForUser, loadMockPatients, loadMockShifts, loadMockStaffProfiles, saveActiveVisitAppointmentId } from "../../utils/mockClinicState";
import { loadMockAppointments, loadMockAvailabilityExceptions, saveMockAppointments } from "../../utils/mockScheduleState";
import { appointmentStatusTone } from "../../utils/statusStyles";

export function MyAppointmentsPage() {
  const navigate = useNavigate();
  const { currentUser } = useSession();
  const [selectedAppointment, setSelectedAppointment] = useState<BackendAppointment | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [visitTypeFilter, setVisitTypeFilter] = useState("All");
  const [selectedPatient, setSelectedPatient] = useState<BackendPatient | null>(null);
  const [allAppointments, setAllAppointments] = useState<BackendAppointment[]>(loadMockAppointments);
  const patientRows = useMemo(loadMockPatients, []);
  const staffProfiles = useMemo(loadMockStaffProfiles, []);
  const shifts = useMemo(loadMockShifts, []);
  const doctorProfile = getMockStaffProfileForUser(currentUser, staffProfiles);
  const appointments = allAppointments.filter((appointment) => appointment.doctorId === doctorProfile?.id);
  const visitTypes = useMemo(() => ["All", ...Array.from(new Set(appointments.map((appointment) => appointment.visitType)))], [appointments]);

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

  const saveAppointmentStatus = (appointment: BackendAppointment, status: AppointmentStatus) => {
    const updatedAppointment = { ...appointment, status };
    const nextAppointments = allAppointments.map((item) => item.id === appointment.id ? updatedAppointment : item);
    setAllAppointments(nextAppointments);
    saveMockAppointments(nextAppointments);
    setSelectedAppointment((current) => current?.id === appointment.id ? updatedAppointment : current);
  };

  const openActiveVisit = (appointment: BackendAppointment) => {
    saveActiveVisitAppointmentId(appointment.id);
    if (appointment.status === "Checked-in") {
      saveAppointmentStatus(appointment, "In Visit");
    }
    navigate(routes.doctor.activeVisit);
  };

  return (
    <div className="page-shell">
      <PageHeader title="My Appointments" subtitle="Doctor-focused appointment schedule." />
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
                const patient = patientRows.find((item) => item.patientId === appointment.patientId) ?? patients.find((item) => item.patientId === appointment.patientId);
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
                    <td>{patient ? fullPatientName(patient) : appointment.patientId}</td>
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
        </div>
      </Card>
      <AppointmentModal
        appointment={selectedAppointment}
        mode="view"
        appointments={allAppointments}
        patientOptions={patientRows}
        staffOptions={staffProfiles}
        shifts={shifts}
        availabilityExceptions={loadMockAvailabilityExceptions()}
        open={Boolean(selectedAppointment)}
        onClose={() => setSelectedAppointment(null)}
        onStatusChange={saveAppointmentStatus}
      />
      <PatientProfileDrawer open={Boolean(selectedPatient)} onClose={() => setSelectedPatient(null)} patient={selectedPatient} canEdit />
    </div>
  );
}
