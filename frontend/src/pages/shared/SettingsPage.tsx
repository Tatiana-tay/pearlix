import { PageHeader } from "../../components/layout/PageHeader";
import { GroupedShiftsTable } from "../../components/staff/GroupedShiftsTable";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { useCurrentUser } from "../../context/SessionContext";
import { getShiftsForStaffProfile, staffProfiles } from "../../data/adapters";
import { initials, prettyDate } from "../../utils/format";
import { loadMockAppointments, loadMockAvailabilityExceptions } from "../../utils/mockScheduleState";
import { appointmentStatusTone, userStatusTone } from "../../utils/statusStyles";

export function SettingsPage() {
  const currentUser = useCurrentUser();
  const isAdmin = currentUser.role === "Admin";
  const profile = staffProfiles.find((item) => item.userId === currentUser.id);
  const shifts = profile ? getShiftsForStaffProfile(profile.id) : [];
  const appointments = loadMockAppointments();
  const availabilityExceptions = loadMockAvailabilityExceptions();
  const profileExceptions = profile
    ? availabilityExceptions.filter((exception) => exception.userId === profile.id)
    : [];
  const todayAppointments = profile
    ? appointments.filter((appointment) => appointment.doctorId === profile.id && appointment.date === "2026-02-09")
    : [];

  return (
    <div className="page-shell">
      <PageHeader
        title={isAdmin ? "Settings" : "Profile"}
        subtitle={isAdmin ? "Manage clinic system preferences and view your account." : "View your clinic account and schedule information."}
      />
      {!isAdmin ? (
        <div className="profile-page-grid">
          <Card className="stack profile-info-card">
            <div className="profile-avatar-block">
              <span className="avatar large">{initials(currentUser.fullName.replace("Dr. ", ""))}</span>
            </div>
            <h2 className="card-title">Profile Information</h2>
            <dl className="detail-list">
              <div><dt>Full name</dt><dd>{currentUser.fullName}</dd></div>
              <div><dt>Username</dt><dd>{currentUser.username}</dd></div>
              <div><dt>Email</dt><dd>{currentUser.email}</dd></div>
              <div><dt>Phone</dt><dd>{currentUser.phone}</dd></div>
              <div><dt>Role</dt><dd>{currentUser.role}</dd></div>
              <div><dt>Status</dt><dd><Badge tone={userStatusTone[currentUser.status]}>{currentUser.status}</Badge></dd></div>
              <div><dt>Created At</dt><dd>{prettyDate(currentUser.createdAt)}</dd></div>
              <div>
                <dt>{currentUser.role === "Doctor" ? "Specialty" : "Position"}</dt>
                <dd>{profile?.specialty ?? "Reception / Staff"}</dd>
              </div>
            </dl>
            <p className="tiny">Password changes are handled through the password reset flow.</p>
          </Card>

          <div className="profile-schedule-column">
            <Card className="stack working-hours-card">
              <h2 className="card-title">Working Hours / Shifts</h2>
              <GroupedShiftsTable shifts={shifts} />
            </Card>

            {profile && (
              <Card className="stack leave-exceptions-card">
                <h2 className="card-title">Leave Exceptions</h2>
                <div className="profile-leave-list">
                  {profileExceptions.map((exception) => (
                    <article className="soft-panel profile-leave-card" key={exception.exceptionId}>
                      <div>
                        <span className="tiny">Date / Time</span>
                        <strong>{exception.startDateTime.replace("T", " ")}</strong>
                        <span className="tiny">to {exception.endDateTime.replace("T", " ")}</span>
                      </div>
                      <div>
                        <span className="tiny">Reason</span>
                        <strong>{exception.reason}</strong>
                      </div>
                      <Badge tone={exception.status === "Active" ? "warning" : "muted"}>{exception.status}</Badge>
                    </article>
                  ))}
                </div>
                {profileExceptions.length === 0 && <div className="empty-inline">No leave exceptions recorded for your profile.</div>}
              </Card>
            )}

            {profile && profile.role === "Doctor" && (
              <Card className="stack">
                <h2 className="card-title">Today's Appointments</h2>
                <div className="summary-list">
                  <span>Total <strong>{todayAppointments.length}</strong></span>
                  <span>Scheduled <strong>{todayAppointments.filter((appointment) => appointment.status === "Scheduled").length}</strong></span>
                  <span>In Visit <strong>{todayAppointments.filter((appointment) => appointment.status === "In Visit").length}</strong></span>
                  <span>Completed <strong>{todayAppointments.filter((appointment) => appointment.status === "Completed").length}</strong></span>
                  <span>Needs Reschedule <strong>{todayAppointments.filter((appointment) => appointment.status === "Needs Reschedule").length}</strong></span>
                </div>
                <div className="stack">
                  {todayAppointments.map((appointment) => (
                    <div className="soft-panel between" key={appointment.id}>
                      <div>
                        <strong>{appointment.time}</strong>
                        <div className="tiny">{appointment.visitType}</div>
                      </div>
                      <Badge tone={appointmentStatusTone[appointment.status]}>{appointment.status}</Badge>
                    </div>
                  ))}
                  {todayAppointments.length === 0 && <div className="empty-inline">No appointments assigned today.</div>}
                </div>
              </Card>
            )}
          </div>
        </div>
      ) : (
      <div className="grid grid-2">
        <Card className="stack profile-info-card">
          <div className="profile-avatar-block">
            <span className="avatar large">{initials(currentUser.fullName.replace("Dr. ", ""))}</span>
          </div>
          <h2 className="card-title">Profile Information</h2>
          <dl className="detail-list">
            <div><dt>Full name</dt><dd>{currentUser.fullName}</dd></div>
            <div><dt>Username</dt><dd>{currentUser.username}</dd></div>
            <div><dt>Email</dt><dd>{currentUser.email}</dd></div>
            <div><dt>Phone</dt><dd>{currentUser.phone}</dd></div>
            <div><dt>Role</dt><dd>{currentUser.role}</dd></div>
            <div><dt>Status</dt><dd><Badge tone={userStatusTone[currentUser.status]}>{currentUser.status}</Badge></dd></div>
            <div><dt>Created At</dt><dd>{prettyDate(currentUser.createdAt)}</dd></div>
            {!isAdmin && (
              <div>
                <dt>{currentUser.role === "Doctor" ? "Specialty" : "Position"}</dt>
                <dd>{profile?.specialty ?? "Reception / Staff"}</dd>
              </div>
            )}
          </dl>
          <p className="tiny">Password changes are handled through the password reset flow.</p>
        </Card>

        <Card className="stack">
          <h2 className="card-title">Clinic/System Preferences</h2>
          <Input label="Clinic name" defaultValue="DentalCare Clinic" />
          <Select label="Default appointment duration" options={["15 minutes", "30 minutes", "45 minutes", "60 minutes"]} defaultValue="30 minutes" />
          <Button className="self-start">Save Settings</Button>
        </Card>
      </div>
      )}
    </div>
  );
}
