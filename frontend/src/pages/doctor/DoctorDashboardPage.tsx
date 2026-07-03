import { useState } from "react";
import { Activity, CalendarCheck, CheckCircle2, ClipboardList } from "lucide-react";
import { AppointmentModal } from "../../components/appointments/AppointmentModal";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { StatCard } from "../../components/ui/StatCard";
import { useSession } from "../../context/SessionContext";
import { getPatientById } from "../../data/adapters";
import type { AppointmentStatus, BackendAppointment } from "../../types/models";
import { fullPatientName } from "../../utils/format";
import { getMockStaffProfileForUser, loadMockShifts, loadMockStaffProfiles, loadMockVisits } from "../../utils/mockClinicState";
import { loadMockAppointments, loadMockAvailabilityExceptions, saveMockAppointments } from "../../utils/mockScheduleState";
import { appointmentStatusTone } from "../../utils/statusStyles";

type AppointmentFilter = "Upcoming" | "Active" | "Completed" | "Cancelled / No-show";

export function DoctorDashboardPage() {
  const { currentUser } = useSession();
  const [appointmentFilter, setAppointmentFilter] = useState<AppointmentFilter>("Upcoming");
  const [selectedAppointment, setSelectedAppointment] = useState<BackendAppointment | null>(null);
  const [appointments, setAppointments] = useState<BackendAppointment[]>(loadMockAppointments);
  const staffProfiles = loadMockStaffProfiles();
  const doctorProfile = getMockStaffProfileForUser(currentUser, staffProfiles);
  const visits = loadMockVisits();
  const today = new Date().toISOString().slice(0, 10);
  const doctorAppointments = doctorProfile ? appointments.filter((appointment) => appointment.doctorId === doctorProfile.id) : [];
  const todayAppointments = doctorAppointments.filter((appointment) => appointment.date === today);
  const visibleAppointments = doctorAppointments.filter((appointment) => matchesAppointmentFilter(appointment, appointmentFilter));

  const saveAppointmentStatus = (appointment: BackendAppointment, status: AppointmentStatus) => {
    const updatedAppointment = { ...appointment, status };
    const nextAppointments = appointments.map((item) => item.id === appointment.id ? updatedAppointment : item);
    setAppointments(nextAppointments);
    saveMockAppointments(nextAppointments);
    setSelectedAppointment((current) => current?.id === appointment.id ? updatedAppointment : current);
  };

  return (
    <div className="page-shell">
      <PageHeader
        title="Dashboard"
        subtitle={`Welcome back, ${doctorProfile?.fullName ?? currentUser.fullName} - ${doctorProfile?.specialty ?? "Dental care"} - ${new Intl.DateTimeFormat("en-US", { weekday: "long", month: "short", day: "numeric", year: "numeric" }).format(new Date(`${today}T00:00:00`))}`}
      />
      <div className="grid grid-4">
        <StatCard label="Today's Appointments" value={todayAppointments.length} icon={<CalendarCheck size={22} />} />
        <StatCard label="Active Visits" value={visits.filter((visit) => visit.doctorId === doctorProfile?.id && visit.status === "Active").length} icon={<Activity size={22} />} />
        <StatCard label="Completed Today" value={todayAppointments.filter((appointment) => appointment.status === "Completed").length} icon={<CheckCircle2 size={22} />} />
        <StatCard label="Unclosed Visits / Pending Notes" value={visits.filter((visit) => visit.doctorId === doctorProfile?.id && visit.status === "Pending Notes").length} icon={<ClipboardList size={22} />} />
      </div>
      <Card>
        <div className="between mb-16">
          <h2 className="card-title">My Appointment Queue</h2>
          <SegmentedControl<AppointmentFilter> options={["Upcoming", "Active", "Completed", "Cancelled / No-show"]} value={appointmentFilter} onChange={setAppointmentFilter} />
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Patient</th>
                <th>Visit Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {visibleAppointments.map((appointment) => {
                const patient = getPatientById(appointment.patientId);
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
                    <td>{appointment.time}</td>
                    <td>{patient ? fullPatientName(patient) : appointment.patientId}</td>
                    <td>{appointment.visitType}</td>
                    <td><Badge tone={appointmentStatusTone[appointment.status]}>{appointment.status}</Badge></td>
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
        appointments={appointments}
        staffOptions={staffProfiles}
        shifts={loadMockShifts()}
        availabilityExceptions={loadMockAvailabilityExceptions()}
        open={Boolean(selectedAppointment)}
        onClose={() => setSelectedAppointment(null)}
        onStatusChange={saveAppointmentStatus}
      />
    </div>
  );
}

function matchesAppointmentFilter(appointment: BackendAppointment, filter: AppointmentFilter) {
  if (filter === "Upcoming") return ["Scheduled", "Arrived", "Checked-in", "Needs Reschedule"].includes(appointment.status);
  if (filter === "Active") return appointment.status === "In Visit";
  if (filter === "Completed") return appointment.status === "Completed";
  return ["Cancelled", "No-show"].includes(appointment.status);
}
