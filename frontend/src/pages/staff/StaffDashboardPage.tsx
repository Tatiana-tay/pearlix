import { CalendarCheck, CalendarPlus, CreditCard, Stethoscope, UserPlus, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { StatCard } from "../../components/ui/StatCard";
import { getPatientById, getShiftsForStaffProfile, staffProfiles } from "../../data/adapters";
import { mockInvoices } from "../../data/mockInvoices";
import { routes } from "../../routes";
import { intervalsOverlap, toDateTime } from "../../utils/availability";
import { currency, fullPatientName } from "../../utils/format";
import { loadMockAppointments, loadMockAvailabilityExceptions } from "../../utils/mockScheduleState";
import { appointmentStatusTone } from "../../utils/statusStyles";

export function StaffDashboardPage() {
  const appointments = loadMockAppointments();
  const availabilityExceptions = loadMockAvailabilityExceptions();
  const today = "2026-02-09";
  const todayAppointments = appointments.filter((appointment) => appointment.date === today);
  const checkedIn = todayAppointments.filter((appointment) => appointment.status === "Checked-in").length;
  const pendingAmount = mockInvoices.filter((invoice) => invoice.status !== "Paid").reduce((sum, invoice) => sum + invoice.totalAmount, 0);
  const upcomingCheckIns = todayAppointments
    .filter((appointment) => appointment.status !== "Completed" && appointment.status !== "Cancelled")
    .sort((a, b) => a.time.localeCompare(b.time))
    .slice(0, 3);
  const mondayDuty = staffProfiles
    .map((profile) => ({
      profile,
      shifts: getShiftsForStaffProfile(profile.id).filter((item) => item.dayOfWeek === "Monday" && !item.isOnLeave),
      onTemporaryLeave: availabilityExceptions.some((exception) =>
        exception.userId === profile.id &&
        exception.status === "Active" &&
        intervalsOverlap(toDateTime(today, "00:00"), toDateTime(today, "23:59"), exception.startDateTime, exception.endDateTime),
      ),
    }))
    .filter((item) => item.profile.status === "Active" && item.shifts.length > 0 && !item.onTemporaryLeave);

  return (
    <div className="page-shell">
      <PageHeader title="Reception Dashboard" subtitle="Today's clinic operations." />
      <div className="grid grid-4">
        <StatCard label="Today's Appointments" value={todayAppointments.length} icon={<CalendarPlus size={22} />} />
        <StatCard label="Checked-in Patients" value={checkedIn} icon={<Users size={22} />} />
        <StatCard label="Pending Payments" value={currency(pendingAmount)} icon={<CreditCard size={22} />} />
        <StatCard label="Team on Duty" value={mondayDuty.length} icon={<Stethoscope size={22} />} />
      </div>
      <div className="grid grid-2">
        <Card>
          <h2 className="card-title">Doctors/Staff on Duty</h2>
          <div className="stack mt-16">
            {mondayDuty.map(({ profile: doctor, shifts }) => {
              return (
                <div className="soft-panel between" key={doctor.id}>
                  <div>
                    <strong>{doctor.fullName}</strong>
                    <div className="tiny">{doctor.specialty}</div>
                  </div>
                  <span>{shifts.map((shift) => `${shift.startTime}-${shift.endTime}`).join(", ")}</span>
                </div>
              );
            })}
          </div>
        </Card>
        <Card>
          <h2 className="card-title">Upcoming Check-ins</h2>
          <div className="stack mt-16">
            {upcomingCheckIns.map((appointment) => {
              const patient = getPatientById(appointment.patientId);
              return (
                <div className="soft-panel compact-row" key={appointment.id}>
                  <div>
                    <strong>{appointment.time} - {patient ? fullPatientName(patient) : appointment.patientId}</strong>
                    <div className="tiny">{appointment.visitType}</div>
                  </div>
                  <Badge tone={appointmentStatusTone[appointment.status]}>{appointment.status}</Badge>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
      <Card>
        <div className="between">
          <div>
            <h2 className="card-title">Quick Actions</h2>
            <p className="tiny">Fast links for the front desk flow.</p>
          </div>
          <Link to={routes.staff.appointments}><Button icon={<CalendarCheck size={17} />}>Open Calendar</Button></Link>
        </div>
        <div className="quick-action-grid mt-16">
          <Link to={routes.staff.appointments} className="quick-action-tile">
            <CalendarPlus size={20} />
            <span>New Appointment</span>
          </Link>
          <Link to={routes.staff.patients} className="quick-action-tile">
            <UserPlus size={20} />
            <span>Add Patient</span>
          </Link>
          <Link to={routes.staff.billing} className="quick-action-tile">
            <CreditCard size={20} />
            <span>Process Payment</span>
          </Link>
          <Link to={routes.staff.patients} className="quick-action-tile">
            <Users size={20} />
            <span>Find Patient</span>
          </Link>
        </div>
      </Card>
    </div>
  );
}
