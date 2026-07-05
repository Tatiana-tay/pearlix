import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Mail, Phone, Plus, Search, Stethoscope, UserCheck, UserX, Users } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { EditableShiftsEditor } from "../../components/staff/EditableShiftsEditor";
import { StaffProfileDrawer } from "../../components/staff/StaffProfileDrawer";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { FilterPopover } from "../../components/ui/FilterPopover";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { StatCard } from "../../components/ui/StatCard";
import { Tabs } from "../../components/ui/Tabs";
import { Textarea } from "../../components/ui/Textarea";
import { TimeInput } from "../../components/ui/TimeInput";
import { useCurrentUser } from "../../context/SessionContext";
import { getPatientById, getShiftsForStaffProfile, getStaffProfileById, staffProfiles as initialStaffProfiles } from "../../data/adapters";
import type { AvailabilityException, BackendAppointment, BackendAvailabilityException, BackendShift, BackendStaffProfile, Gender, ProfileStatus } from "../../types/models";
import { appointmentEnd, appointmentStart, detectAffectedAppointments, hasOverlappingException, intervalsOverlap, toDateTime, toLocalDateTime } from "../../utils/availability";
import { fullPatientName, initials } from "../../utils/format";
import {
  loadMockAppointments,
  loadMockAvailabilityExceptions,
  saveMockAppointments,
  saveMockAvailabilityExceptions,
} from "../../utils/mockScheduleState";
import { loadMockStaffProfiles, loadMockShifts, saveMockStaffProfiles, saveMockShifts } from "../../utils/mockClinicState";
import { createShift, getShiftValidationMessage, sortShifts } from "../../utils/shifts";
import { appointmentStatusTone, userStatusTone } from "../../utils/statusStyles";

interface DoctorsStaffPageProps {
  readOnly?: boolean;
}

interface StaffFormState {
  fullName: string;
  email: string;
  phone: string;
  role: BackendStaffProfile["role"];
  gender: Gender;
  specialty: string;
  status: ProfileStatus;
}

const leaveReasons: AvailabilityException["reason"][] = ["Leave", "Sick Leave", "Personal", "Training", "Emergency", "Other"];

export function DoctorsStaffPage({ readOnly = false }: DoctorsStaffPageProps) {
  const currentUser = useCurrentUser();
  const [profiles, setProfiles] = useState<BackendStaffProfile[]>(loadMockStaffProfiles);
  const [shiftRows, setShiftRows] = useState<BackendShift[]>(loadMockShifts);
  const [appointmentRows, setAppointmentRows] = useState<BackendAppointment[]>(loadMockAppointments);
  const [availabilityExceptionRows, setAvailabilityExceptionRows] = useState<BackendAvailabilityException[]>(loadMockAvailabilityExceptions);
  const [scheduleStaff, setScheduleStaff] = useState<BackendStaffProfile | null>(null);
  const [profileStaff, setProfileStaff] = useState<BackendStaffProfile | null>(null);
  const [leaveStaff, setLeaveStaff] = useState<BackendStaffProfile | null>(null);
  const [editingLeaveException, setEditingLeaveException] = useState<BackendAvailabilityException | null>(null);
  const [affectedException, setAffectedException] = useState<BackendAvailabilityException | null>(null);
  const [leaveNotice, setLeaveNotice] = useState<{ message: string; exception: BackendAvailabilityException | null } | null>(null);
  const [addStaffOpen, setAddStaffOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");

  const today = "2026-02-09";
  const todayName = new Intl.DateTimeFormat("en-US", { weekday: "long" }).format(new Date(`${today}T00:00:00`));
  const activeToday = profiles.filter((profile) =>
    profile.status === "Active" &&
    shiftRows.some((shift) => shift.staffOrDoctorId === profile.id && shift.dayOfWeek === todayName && !shift.isOnLeave) &&
    !availabilityExceptionRows.some((exception) =>
      exception.userId === profile.id &&
      exception.status === "Active" &&
      intervalsOverlap(`${today}T00:00`, `${today}T23:59`, exception.startDateTime, exception.endDateTime),
    ),
  ).length;
  const onLeave = profiles.filter((doctor) => doctor.status === "On Leave").length;
  const doctorsCount = profiles.filter((profile) => profile.role === "Doctor").length;
  const filteredStaff = useMemo(() => {
    const normalized = query.toLowerCase();
    return profiles.filter((doctor) => {
      const role = doctor.role;
      const text = `${doctor.fullName} ${doctor.email} ${doctor.phone} ${doctor.specialty}`.toLowerCase();
      const matchesRole = roleFilter === "All" || roleFilter === role;
      const matchesStatus = statusFilter === "All" || doctor.status === statusFilter;
      return text.includes(normalized) && matchesRole && matchesStatus;
    });
  }, [profiles, query, roleFilter, statusFilter]);
  const activeFilters = (roleFilter !== "All" ? 1 : 0) + (statusFilter !== "All" ? 1 : 0);

  const saveProfile = (updatedProfile: BackendStaffProfile) => {
    setProfiles((current) => {
      const nextProfiles = current.map((profile) => profile.id === updatedProfile.id ? updatedProfile : profile);
      saveMockStaffProfiles(nextProfiles);
      return nextProfiles;
    });
    setProfileStaff(updatedProfile);
    setScheduleStaff((current) => current?.id === updatedProfile.id ? updatedProfile : current);
  };

  const saveShifts = (staffId: string, shifts: BackendShift[]) => {
    const normalized = sortShifts(shifts).map((shift, index) => ({ ...shift, staffOrDoctorId: staffId, shiftIndex: index + 1 }));
    setShiftRows((current) => {
      const nextShifts = [...current.filter((shift) => shift.staffOrDoctorId !== staffId), ...normalized];
      saveMockShifts(nextShifts);
      return nextShifts;
    });
  };

  const addStaffMember = (profile: BackendStaffProfile, shifts: BackendShift[]) => {
    setProfiles((current) => {
      const nextProfiles = [...current, profile];
      saveMockStaffProfiles(nextProfiles);
      return nextProfiles;
    });
    setShiftRows((current) => {
      const nextShifts = [...current, ...shifts];
      saveMockShifts(nextShifts);
      return nextShifts;
    });
    setProfileStaff(profile);
    setAddStaffOpen(false);
  };

  const saveLeaveException = (exception: BackendAvailabilityException) => {
    const affectedAppointments = detectAffectedAppointments(exception, appointmentRows);
    const affectedIds = new Set(affectedAppointments.map((appointment) => appointment.id));
    const isEditing = availabilityExceptionRows.some((item) => item.exceptionId === exception.exceptionId);
    const nextExceptions = isEditing
      ? availabilityExceptionRows.map((item) => item.exceptionId === exception.exceptionId ? exception : item)
      : [...availabilityExceptionRows, exception];
    const nextAppointments = appointmentRows.map((appointment) => {
      if (!affectedIds.has(appointment.id)) return appointment;
      return {
        ...appointment,
        status: "Needs Reschedule" as const,
        notes: appointment.notes.includes("Doctor unavailable due to leave")
          ? appointment.notes
          : `${appointment.notes}${appointment.notes ? " " : ""}Doctor unavailable due to leave.`,
      };
    });

    setAvailabilityExceptionRows(nextExceptions);
    setAppointmentRows(nextAppointments);
    saveMockAvailabilityExceptions(nextExceptions);
    saveMockAppointments(nextAppointments);
    setLeaveStaff(null);
    setEditingLeaveException(null);
    setAffectedException(exception);
    setLeaveNotice({
      message: affectedAppointments.length > 0
        ? `Leave ${isEditing ? "updated" : "saved"}. ${affectedAppointments.length} appointments were marked as Needs Reschedule.`
        : `Leave ${isEditing ? "updated" : "saved"}. No appointments affected.`,
      exception,
    });
  };

  const cancelLeaveException = (exceptionId: string) => {
    const nextExceptions = availabilityExceptionRows.map((exception) =>
      exception.exceptionId === exceptionId ? { ...exception, status: "Cancelled" as const } : exception,
    );
    setAvailabilityExceptionRows(nextExceptions);
    saveMockAvailabilityExceptions(nextExceptions);
    setLeaveNotice({
      message: "Leave cancelled. Future availability is restored, but any Needs Reschedule appointments remain for Staff review.",
      exception: nextExceptions.find((exception) => exception.exceptionId === exceptionId) ?? null,
    });
  };

  const getProfileShifts = (staffId: string) =>
    shiftRows.filter((shift) => shift.staffOrDoctorId === staffId);

  return (
    <div className="page-shell">
      <PageHeader
        title="Doctors & Staff"
        subtitle={readOnly ? "View clinic team profiles and schedules." : "Manage clinic staff and schedules."}
        actions={!readOnly && <Button icon={<Plus size={18} />} onClick={() => setAddStaffOpen(true)}>Add Staff Member</Button>}
      />
      {leaveNotice && (
        <div className="notice-card between">
          <span>{leaveNotice.message}</span>
          {leaveNotice.exception && (
            <Button variant="secondary" onClick={() => setAffectedException(leaveNotice.exception)}>View affected appointments</Button>
          )}
        </div>
      )}
      <div className="grid grid-4">
        <StatCard label="Total Staff" value={profiles.length} icon={<Users size={22} />} />
        <StatCard label="Doctors" value={doctorsCount} icon={<Stethoscope size={22} />} />
        <StatCard label="Active Today" value={activeToday} icon={<UserCheck size={22} />} />
        <StatCard label="On Leave" value={onLeave} icon={<UserX size={22} />} />
      </div>
      <Card>
        <div className="filter-card">
          <Input icon={<Search size={18} />} placeholder="Search staff by name, email, phone, or specialty..." value={query} onChange={(event) => setQuery(event.target.value)} />
          <FilterPopover activeCount={activeFilters}>
            <div className="filter-popover-content">
              <Select label="Role" options={["All", "Doctor", "Staff"]} value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)} />
              <Select label="Status" options={["All", "Active", "Inactive", "On Leave"]} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} />
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setRoleFilter("All");
                  setStatusFilter("All");
                }}
              >
                Clear filters
              </Button>
            </div>
          </FilterPopover>
        </div>
      </Card>
      <div className="grid grid-2">
        {filteredStaff.map((doctor) => {
          const patientsToday = appointmentRows.filter((appointment) => appointment.doctorId === doctor.id && appointment.date === "2026-02-09").length;
          const mondayShifts = getProfileShifts(doctor.id).filter((shift) => shift.dayOfWeek === "Monday" && !shift.isOnLeave);
          const role = doctor.role === "Doctor" ? "Dentist" : doctor.specialty ?? "Clinic Staff";
          return (
            <Card
              className="staff-card clickable"
              key={doctor.id}
              role="button"
              tabIndex={0}
              onClick={() => setProfileStaff(doctor)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setProfileStaff(doctor);
                }
              }}
            >
              <div className="row staff-card-head">
                <span className="avatar large staff-avatar">{initials(doctor.fullName.replace("Dr. ", ""))}</span>
                <div>
                  <h2>{doctor.fullName}</h2>
                  <div className="row">
                    <Badge tone={doctor.role === "Doctor" ? "teal" : "primary"}>{role}</Badge>
                    <Badge tone="muted">{doctor.specialty}</Badge>
                  </div>
                </div>
              </div>
              <div className="staff-lines">
                <span><Mail size={18} /> {doctor.email}</span>
                <span><Phone size={18} /> {doctor.phone}</span>
                <span><CalendarDays size={18} /> Mon, {mondayShifts.length ? mondayShifts.map((shift) => `${shift.startTime}-${shift.endTime}`).join(", ") : "On leave"}</span>
              </div>
              <div className="divider" />
              <div className="row">
                <div><div className="tiny">Status</div><Badge tone={userStatusTone[doctor.status]}>{doctor.status}</Badge></div>
                <div><div className="tiny">Appointments Today</div><strong>{patientsToday}</strong></div>
              </div>
            </Card>
          );
        })}
      </div>
      <StaffProfileDrawer
        staff={profileStaff}
        open={Boolean(profileStaff)}
        onClose={() => setProfileStaff(null)}
        onEditWorkingHours={(staff) => setScheduleStaff(staff)}
        readOnly={readOnly}
        shifts={profileStaff ? getProfileShifts(profileStaff.id) : []}
        appointments={appointmentRows}
        availabilityExceptions={availabilityExceptionRows}
        onSaveProfile={saveProfile}
        onSaveShifts={saveShifts}
        onAddLeave={!readOnly ? setLeaveStaff : undefined}
        onEditLeave={!readOnly ? setEditingLeaveException : undefined}
        onCancelLeave={!readOnly ? cancelLeaveException : undefined}
        onViewAffectedAppointments={setAffectedException}
      />
      {!readOnly && (
        <WorkingHoursModal
          doctor={scheduleStaff}
          shifts={scheduleStaff ? getProfileShifts(scheduleStaff.id) : []}
          onClose={() => setScheduleStaff(null)}
          onSave={(staffId, shifts) => {
            saveShifts(staffId, shifts);
            setScheduleStaff(null);
          }}
        />
      )}
      {!readOnly && <AddStaffMemberModal open={addStaffOpen} onClose={() => setAddStaffOpen(false)} onCreate={addStaffMember} />}
      {!readOnly && (
        <LeaveExceptionModal
          staff={leaveStaff}
          exception={editingLeaveException}
          profiles={profiles}
          appointments={appointmentRows}
          exceptions={availabilityExceptionRows}
          createdBy={currentUser.id}
          onClose={() => {
            setLeaveStaff(null);
            setEditingLeaveException(null);
          }}
          onSave={saveLeaveException}
        />
      )}
      <AffectedAppointmentsModal
        exception={affectedException}
        appointments={appointmentRows}
        onClose={() => setAffectedException(null)}
      />
    </div>
  );
}

function LeaveExceptionModal({
  staff,
  exception,
  profiles,
  appointments,
  exceptions,
  createdBy,
  onClose,
  onSave,
}: {
  staff: BackendStaffProfile | null;
  exception: BackendAvailabilityException | null;
  profiles: BackendStaffProfile[];
  appointments: BackendAppointment[];
  exceptions: BackendAvailabilityException[];
  createdBy: string;
  onClose: () => void;
  onSave: (exception: BackendAvailabilityException) => void;
}) {
  const [personId, setPersonId] = useState(staff?.id ?? profiles[0]?.id ?? "");
  const [startDate, setStartDate] = useState("2026-03-10");
  const [startTime, setStartTime] = useState("09:00");
  const [endDate, setEndDate] = useState("2026-03-10");
  const [endTime, setEndTime] = useState("13:00");
  const [reason, setReason] = useState<AvailabilityException["reason"]>("Leave");
  const [status, setStatus] = useState<AvailabilityException["status"]>("Active");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (exception) {
      setPersonId(exception.userId);
      setStartDate(exception.startDateTime.slice(0, 10));
      setStartTime(exception.startDateTime.slice(11, 16));
      setEndDate(exception.endDateTime.slice(0, 10));
      setEndTime(exception.endDateTime.slice(11, 16));
      setReason(exception.reason);
      setStatus(exception.status);
      setNote(exception.note ?? "");
      return;
    }

    if (staff) {
      setPersonId(staff.id);
      setStartDate("2026-03-10");
      setStartTime("09:00");
      setEndDate("2026-03-10");
      setEndTime("13:00");
      setReason("Leave");
      setStatus("Active");
      setNote("");
    }
  }, [exception, staff]);

  const selectedPerson = profiles.find((profile) => profile.id === personId) ?? staff;
  const startDateTime = toDateTime(startDate, startTime);
  const endDateTime = toDateTime(endDate, endTime);
  const rangeValid = new Date(startDateTime).getTime() < new Date(endDateTime).getTime();
  const isEditing = Boolean(exception);
  const draftException: BackendAvailabilityException | null = selectedPerson
    ? {
      exceptionId: exception?.exceptionId ?? "DRAFT",
      userId: selectedPerson.id,
      userRole: selectedPerson.role,
      startDateTime,
      endDateTime,
      reason,
      note: note.trim() || undefined,
      status,
      createdBy: exception?.createdBy ?? createdBy,
      createdAt: exception?.createdAt ?? toLocalDateTime(new Date()),
    }
    : null;
  const activeDraft = draftException?.status === "Active";
  const overlappingException = Boolean(draftException && activeDraft && rangeValid && hasOverlappingException(draftException, exceptions));
  const inVisitConflict = Boolean(
    selectedPerson?.role === "Doctor" &&
      activeDraft &&
      rangeValid &&
      appointments.some((appointment) =>
        appointment.doctorId === selectedPerson.id &&
        appointment.status === "In Visit" &&
        intervalsOverlap(appointmentStart(appointment), appointmentEnd(appointment), startDateTime, endDateTime),
      ),
  );
  const affectedAppointments = draftException && rangeValid ? detectAffectedAppointments(draftException, appointments) : [];
  const canSave = Boolean(selectedPerson && rangeValid && !overlappingException && !inVisitConflict);

  const save = () => {
    if (!draftException || !canSave) return;
    onSave({
      ...draftException,
      exceptionId: exception?.exceptionId ?? `EXC-${Date.now()}`,
      createdAt: exception?.createdAt ?? toLocalDateTime(new Date()),
    });
  };

  return (
    <Modal
      title={isEditing ? "Edit Leave Exception" : "Add Leave Exception"}
      subtitle={selectedPerson?.fullName}
      open={Boolean(staff || exception)}
      onClose={onClose}
      width={860}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={!canSave} onClick={save}>Save Leave</Button>
        </>
      }
    >
      <div className="stack">
        <div className="field-grid">
          <div className="form-field">
            <span>Person</span>
            <div className="input-like">{selectedPerson?.fullName ?? "Selected profile"}</div>
          </div>
          <Select label="Reason" options={leaveReasons} value={reason} onChange={(event) => setReason(event.target.value as AvailabilityException["reason"])} />
          <Input label="Start date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          <TimeInput label="Start time" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
          <Input label="End date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          <TimeInput label="End time" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
          {isEditing && <Select label="Status" options={["Active", "Cancelled"]} value={status} onChange={(event) => setStatus(event.target.value as AvailabilityException["status"])} />}
        </div>
        <Textarea label="Optional note" value={note} onChange={(event) => setNote(event.target.value)} />
        {!rangeValid && <div className="alert-card">Start date and time must be before end date and time.</div>}
        {overlappingException && <div className="alert-card">This leave overlaps an existing active leave exception for the same person.</div>}
        {inVisitConflict && <div className="alert-card">This leave overlaps an appointment that is currently In Visit. Finish the visit or choose a different range.</div>}
        {selectedPerson?.role === "Staff" && (
          <div className="notice-card">Staff leave updates team availability only. It will not mark patient appointments as Needs Reschedule in this mock data model.</div>
        )}
        <div className="soft-panel">
          <div className="between">
            <h3 className="card-title">Affected Appointment Preview</h3>
            <Badge tone={affectedAppointments.length ? "orange" : "muted"}>{affectedAppointments.length} affected</Badge>
          </div>
          <p className="tiny mt-16">
            {affectedAppointments.length > 0
              ? `This leave affects ${affectedAppointments.length} scheduled appointments.`
              : "No scheduled appointments are affected by this leave range."}
          </p>
          {affectedAppointments.length > 0 && (
            <div className="table-wrap mt-16">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date / Time</th>
                    <th>Patient</th>
                    <th>Doctor</th>
                    <th>Visit Type</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {affectedAppointments.map((appointment) => {
                    const patient = getPatientById(appointment.patientId);
                    const doctor = getStaffProfileById(appointment.doctorId);
                    return (
                      <tr key={appointment.id}>
                        <td>{appointment.date} at {appointment.time}</td>
                        <td>{patient ? fullPatientName(patient) : appointment.patientId}</td>
                        <td>{doctor?.fullName ?? appointment.doctorId}</td>
                        <td>{appointment.visitType}</td>
                        <td><Badge tone={appointmentStatusTone[appointment.status]}>{appointment.status}</Badge></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

function AffectedAppointmentsModal({
  exception,
  appointments,
  onClose,
}: {
  exception: BackendAvailabilityException | null;
  appointments: BackendAppointment[];
  onClose: () => void;
}) {
  const affectedAppointments = exception ? getAffectedAppointmentsForDisplay(exception, appointments) : [];
  const person = getStaffProfileById(exception?.userId);

  return (
    <Modal
      title="Affected Appointments"
      subtitle={person ? `${person.fullName} - ${exception?.startDateTime.replace("T", " ")} to ${exception?.endDateTime.replace("T", " ")}` : undefined}
      open={Boolean(exception)}
      onClose={onClose}
      width={860}
      footer={<Button variant="secondary" onClick={onClose}>Close</Button>}
    >
      <div className="stack">
        <div className="notice-card">
          Canceling leave restores future availability only. It does not automatically restore appointments already marked Needs Reschedule.
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Date / Time</th>
                <th>Patient</th>
                <th>Doctor</th>
                <th>Visit Type</th>
                <th>Status</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {affectedAppointments.map((appointment) => {
                const patient = getPatientById(appointment.patientId);
                const doctor = getStaffProfileById(appointment.doctorId);
                return (
                  <tr key={appointment.id}>
                    <td>{appointment.date} at {appointment.time}</td>
                    <td>{patient ? fullPatientName(patient) : appointment.patientId}</td>
                    <td>{doctor?.fullName ?? appointment.doctorId}</td>
                    <td>{appointment.visitType}</td>
                    <td><Badge tone={appointmentStatusTone[appointment.status]}>{appointment.status}</Badge></td>
                    <td>{appointment.notes}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {affectedAppointments.length === 0 && <div className="empty-inline">No appointments overlap this leave exception.</div>}
      </div>
    </Modal>
  );
}

function getAffectedAppointmentsForDisplay(exception: BackendAvailabilityException, appointments: BackendAppointment[]) {
  if (exception.userRole !== "Doctor") return [];
  return appointments.filter((appointment) =>
    appointment.doctorId === exception.userId &&
    !["Completed", "Cancelled", "No-show"].includes(appointment.status) &&
    intervalsOverlap(appointmentStart(appointment), appointmentEnd(appointment), exception.startDateTime, exception.endDateTime),
  );
}

function AddStaffMemberModal({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (profile: BackendStaffProfile, shifts: BackendShift[]) => void;
}) {
  const [activeTab, setActiveTab] = useState("general");
  const [form, setForm] = useState<StaffFormState>({
    fullName: "Dr. Maya Rivera",
    email: "maya.rivera@dentalcare.local",
    phone: "(555) 000-0000",
    role: "Doctor",
    gender: "Female",
    specialty: "General Dentistry",
    status: "Active",
  });
  const [tempId, setTempId] = useState("NEW-STAFF");
  const [shifts, setShifts] = useState<BackendShift[]>([]);

  useEffect(() => {
    if (open) {
      const nextTempId = `NEW-${Date.now()}`;
      setTempId(nextTempId);
      setActiveTab("general");
      setForm({
        fullName: "",
        email: "",
        phone: "",
        role: "Doctor",
        gender: "Female",
        specialty: "",
        status: "Active",
      });
      setShifts([createShift(nextTempId, [], "Monday")]);
    }
  }, [open]);

  const updateForm = (field: keyof StaffFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const validationMessage = getShiftValidationMessage(shifts);
  const canSave = form.fullName.trim() && form.email.trim() && form.phone.trim() && !validationMessage;

  const save = () => {
    if (!canSave) return;
    const id = `${form.role === "Doctor" ? "DOC" : "STF"}-${Date.now().toString().slice(-6)}`;
    const profile: BackendStaffProfile = {
      id,
      userId: `USR-${Date.now().toString().slice(-6)}`,
      fullName: form.fullName.trim(),
      role: form.role,
      specialty: form.role === "Doctor" ? form.specialty : form.specialty || "Clinic Staff",
      gender: form.gender,
      email: form.email.trim(),
      phone: form.phone.trim(),
      status: form.status,
    };
    const normalizedShifts = sortShifts(shifts).map((shift, index) => ({
      ...shift,
      id: shift.id.replace(tempId, id),
      staffOrDoctorId: id,
      shiftIndex: index + 1,
    }));
    onCreate(profile, normalizedShifts);
  };

  const tabs = [
    {
      id: "general",
      label: "General",
      content: (
        <div className="field-grid">
          <Input label="Full name" value={form.fullName} onChange={(event) => updateForm("fullName", event.target.value)} />
          <Input label="Email" type="email" value={form.email} onChange={(event) => updateForm("email", event.target.value)} />
          <Input label="Phone" value={form.phone} onChange={(event) => updateForm("phone", event.target.value)} />
          <Select label="Gender" options={["Male", "Female"]} value={form.gender} onChange={(event) => updateForm("gender", event.target.value as Gender)} />
          <Select label="Role" options={["Doctor", "Staff"]} value={form.role} onChange={(event) => updateForm("role", event.target.value as BackendStaffProfile["role"])} />
          <Select label="Status" options={["Active", "Inactive", "On Leave"]} value={form.status} onChange={(event) => updateForm("status", event.target.value as ProfileStatus)} />
          <Input className="span-2" label={form.role === "Doctor" ? "Specialization" : "Position"} value={form.specialty} onChange={(event) => updateForm("specialty", event.target.value)} />
        </div>
      ),
    },
    {
      id: "hours",
      label: "Schedule",
      content: (
        <div className="stack">
          <EditableShiftsEditor rows={shifts} staffOrDoctorId={tempId} onRowsChange={setShifts} />
          {validationMessage && <div className="alert-card">{validationMessage}</div>}
        </div>
      ),
    },
  ];

  return (
    <Modal
      title="Add Staff Member"
      subtitle="Creates local mock staff details for this prototype only."
      open={open}
      onClose={onClose}
      width={960}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={!canSave} onClick={save}>Save Staff Member</Button>
        </>
      }
    >
      <Tabs tabs={tabs} activeId={activeTab} onChange={setActiveTab} />
    </Modal>
  );
}

function WorkingHoursModal({
  doctor,
  shifts,
  onClose,
  onSave,
}: {
  doctor: BackendStaffProfile | null;
  shifts: BackendShift[];
  onClose: () => void;
  onSave: (staffId: string, shifts: BackendShift[]) => void;
}) {
  const [rows, setRows] = useState<BackendShift[]>([]);

  useEffect(() => {
    setRows(shifts);
  }, [doctor?.id, shifts]);

  const validationMessage = getShiftValidationMessage(rows);

  return (
    <Modal
      title="Edit Working Hours / Shifts"
      subtitle={doctor?.fullName}
      open={Boolean(doctor)}
      onClose={onClose}
      width={960}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={Boolean(validationMessage)} onClick={() => doctor && onSave(doctor.id, rows)}>Save Schedule</Button>
        </>
      }
    >
      {doctor && (
        <div className="stack">
          <EditableShiftsEditor rows={rows} staffOrDoctorId={doctor.id} onRowsChange={setRows} />
          {validationMessage && <div className="alert-card">{validationMessage}</div>}
        </div>
      )}
    </Modal>
  );
}
