import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Clock, Mail, Pencil, Phone, Plus, Save } from "lucide-react";
import { getPatientById, getShiftsForStaffProfile } from "../../data/adapters";
import type { BackendAppointment, BackendAvailabilityException, BackendShift, BackendStaffProfile, Gender, ProfileStatus } from "../../types/models";
import { detectAffectedAppointments } from "../../utils/availability";
import { fullPatientName, initials } from "../../utils/format";
import { getShiftValidationMessage, sortShifts } from "../../utils/shifts";
import { appointmentStatusTone, userStatusTone } from "../../utils/statusStyles";
import { AppointmentModal } from "../appointments/AppointmentModal";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Drawer } from "../ui/Drawer";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Tabs } from "../ui/Tabs";
import { Textarea } from "../ui/Textarea";
import { EditableShiftsEditor } from "./EditableShiftsEditor";
import { GroupedShiftsTable } from "./GroupedShiftsTable";

interface StaffProfileDrawerProps {
  staff: BackendStaffProfile | null;
  open: boolean;
  onClose: () => void;
  onEditWorkingHours: (staff: BackendStaffProfile) => void;
  readOnly?: boolean;
  shifts?: BackendShift[];
  appointments?: BackendAppointment[];
  availabilityExceptions?: BackendAvailabilityException[];
  onSaveProfile?: (staff: BackendStaffProfile) => void;
  onSaveShifts?: (staffId: string, shifts: BackendShift[]) => void;
  onAddLeave?: (staff: BackendStaffProfile) => void;
  onEditLeave?: (exception: BackendAvailabilityException) => void;
  onCancelLeave?: (exceptionId: string) => void;
  onViewAffectedAppointments?: (exception: BackendAvailabilityException) => void;
}

export function StaffProfileDrawer({
  staff,
  open,
  onClose,
  onEditWorkingHours,
  readOnly = false,
  shifts: providedShifts,
  appointments = [],
  availabilityExceptions = [],
  onSaveProfile,
  onSaveShifts,
  onAddLeave,
  onEditLeave,
  onCancelLeave,
  onViewAffectedAppointments,
}: StaffProfileDrawerProps) {
  const [activeTab, setActiveTab] = useState("general");
  const [editMode, setEditMode] = useState(false);
  const [draftStaff, setDraftStaff] = useState<BackendStaffProfile | null>(staff);
  const [draftShifts, setDraftShifts] = useState<BackendShift[]>(providedShifts ?? []);
  const [activityNote, setActivityNote] = useState("Mock profile activity can be used for schedule notes, onboarding status, and clinic administration reminders.");
  const [selectedAppointment, setSelectedAppointment] = useState<BackendAppointment | null>(null);

  const fallbackShifts = useMemo(
    () => staff ? getShiftsForStaffProfile(staff.id) : [],
    [staff],
  );
  const profileShifts = providedShifts ?? fallbackShifts;
  const todayAppointments = useMemo(
    () => appointments.filter((appointment) => appointment.doctorId === staff?.id && appointment.date === "2026-02-09"),
    [appointments, staff],
  );

  useEffect(() => {
    if (open) {
      setActiveTab("general");
      setEditMode(false);
      setDraftStaff(staff);
      setDraftShifts(profileShifts);
      setActivityNote("Mock profile activity can be used for schedule notes, onboarding status, and clinic administration reminders.");
    }
  }, [open, staff, profileShifts]);

  if (!staff || !draftStaff) {
    return null;
  }

  const displayStaff = editMode ? draftStaff : staff;
  const displayShifts = editMode ? draftShifts : profileShifts;
  const profileExceptions = availabilityExceptions.filter((exception) => exception.userId === staff.id);
  const role = displayStaff.role === "Doctor" ? "Dentist" : displayStaff.specialty ?? "Clinic Staff";
  const validationMessage = getShiftValidationMessage(draftShifts);

  const updateDraftStaff = (field: keyof BackendStaffProfile, value: string) => {
    setDraftStaff((current) => current ? { ...current, [field]: value } : current);
  };

  const saveChanges = () => {
    if (validationMessage) return;
    const savedShifts = sortShifts(draftShifts).map((shift) => ({ ...shift, staffOrDoctorId: draftStaff.id }));
    onSaveProfile?.(draftStaff);
    onSaveShifts?.(draftStaff.id, savedShifts);
    setEditMode(false);
  };

  const cancelChanges = () => {
    setDraftStaff(staff);
    setDraftShifts(profileShifts);
    setEditMode(false);
  };

  const tabs = [
    {
      id: "general",
      label: "General",
      content: (
        <div className="soft-panel">
          {editMode ? (
            <div className="field-grid">
              <Input label="Full name" value={draftStaff.fullName} onChange={(event) => updateDraftStaff("fullName", event.target.value)} />
              <Input label="Email" type="email" value={draftStaff.email} onChange={(event) => updateDraftStaff("email", event.target.value)} />
              <Input label="Phone" value={draftStaff.phone} onChange={(event) => updateDraftStaff("phone", event.target.value)} />
              <Select label="Role" options={["Doctor", "Staff"]} value={draftStaff.role} onChange={(event) => updateDraftStaff("role", event.target.value as BackendStaffProfile["role"])} />
              <Select label="Gender" options={["Male", "Female"]} value={draftStaff.gender} onChange={(event) => updateDraftStaff("gender", event.target.value as Gender)} />
              <Select label="Status" options={["Active", "Inactive", "On Leave"]} value={draftStaff.status} onChange={(event) => updateDraftStaff("status", event.target.value as ProfileStatus)} />
              <Input
                className="span-2"
                label={draftStaff.role === "Doctor" ? "Specialty" : "Position"}
                value={draftStaff.specialty ?? ""}
                onChange={(event) => updateDraftStaff("specialty", event.target.value)}
              />
            </div>
          ) : (
            <dl className="detail-list">
              <div><dt>Full name</dt><dd>{displayStaff.fullName}</dd></div>
              <div><dt>Email</dt><dd>{displayStaff.email}</dd></div>
              <div><dt>Phone</dt><dd>{displayStaff.phone}</dd></div>
              <div><dt>Role</dt><dd>{role}</dd></div>
              <div><dt>Gender</dt><dd>{displayStaff.gender}</dd></div>
              <div><dt>{displayStaff.role === "Doctor" ? "Specialty" : "Position"}</dt><dd>{displayStaff.specialty}</dd></div>
              <div><dt>Status</dt><dd><Badge tone={userStatusTone[displayStaff.status]}>{displayStaff.status}</Badge></dd></div>
            </dl>
          )}
        </div>
      ),
    },
    {
      id: "hours",
      label: "Schedule",
      content: (
        <div className="stack">
          {!readOnly && !editMode && (
            <div className="right">
              <Button icon={<Clock size={17} />} onClick={() => onEditWorkingHours(staff)}>Edit Working Hours / Shifts</Button>
            </div>
          )}
          {editMode ? (
            <>
              <EditableShiftsEditor rows={draftShifts} staffOrDoctorId={draftStaff.id} onRowsChange={setDraftShifts} />
              {validationMessage && <div className="alert-card">{validationMessage}</div>}
            </>
          ) : (
            <GroupedShiftsTable shifts={displayShifts} />
          )}
        </div>
      ),
    },
    {
      id: "leave",
      label: "Leave",
      content: (
        <div className="stack">
          {!readOnly && (
            <div className="right">
              <Button icon={<Plus size={17} />} onClick={() => onAddLeave?.(staff)}>Add Leave</Button>
            </div>
          )}
          <div className="profile-leave-list">
            {profileExceptions.map((exception) => {
              const affected = detectAffectedAppointments(exception, appointments);
              return (
                <article className="soft-panel profile-leave-card" key={exception.exceptionId}>
                  <div>
                    <span className="tiny">Date / Time</span>
                    <strong>{exception.startDateTime.replace("T", " ")}</strong>
                    <span className="tiny">to {exception.endDateTime.replace("T", " ")}</span>
                  </div>
                  <div>
                    <span className="tiny">Reason</span>
                    <strong>{exception.reason}</strong>
                    {exception.note && <span className="tiny">{exception.note}</span>}
                  </div>
                  <div className="profile-leave-badges">
                    <Badge tone={affected.length ? "orange" : "muted"}>{affected.length} affected</Badge>
                    <Badge tone={exception.status === "Active" ? "warning" : "muted"}>{exception.status}</Badge>
                  </div>
                  <div className="right">
                    <Button variant="ghost" onClick={() => onViewAffectedAppointments?.(exception)}>View Affected</Button>
                    {!readOnly && exception.status === "Active" && (
                      <Button variant="secondary" onClick={() => onEditLeave?.(exception)}>Edit</Button>
                    )}
                    {!readOnly && exception.status === "Active" && (
                      <Button variant="danger" onClick={() => onCancelLeave?.(exception.exceptionId)}>Cancel Leave</Button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
          {profileExceptions.length === 0 && <div className="empty-inline">No temporary leave exceptions for this profile.</div>}
        </div>
      ),
    },
    {
      id: "appointments",
      label: "Appointments",
      content: (
        <div className="stack">
          {todayAppointments.map((appointment) => {
            const patient = getPatientById(appointment.patientId);
            return (
              <button
                className="soft-panel appointment-profile-row"
                key={appointment.id}
                type="button"
                onClick={() => setSelectedAppointment(appointment)}
              >
                <div>
                  <strong>{appointment.time} - {patient ? fullPatientName(patient) : appointment.patientId}</strong>
                  <div className="tiny">{appointment.visitType}</div>
                </div>
                <Badge tone={appointmentStatusTone[appointment.status]}>{appointment.status}</Badge>
              </button>
            );
          })}
          {todayAppointments.length === 0 && <div className="empty-inline">No assigned appointments today.</div>}
        </div>
      ),
    },
    {
      id: "activity",
      label: "Notes",
      content: (
        <div className="soft-panel">
          <h3 className="card-title">Profile notes</h3>
          {editMode ? (
            <Textarea className="mt-16" label="Activity notes" value={activityNote} onChange={(event) => setActivityNote(event.target.value)} />
          ) : (
            <p className="muted">{activityNote}</p>
          )}
        </div>
      ),
    },
  ];

  return (
    <Drawer title="Doctor/Staff Profile" open={open} onClose={onClose} width={1240}>
      <div className="detail-layout staff-profile-drawer">
        <aside className="detail-sidebar patient-side">
          <span className="avatar large">{initials(displayStaff.fullName.replace("Dr. ", ""))}</span>
          <div className="patient-headline">
            <h2>{displayStaff.fullName}</h2>
            <p>{role} - {displayStaff.specialty}</p>
          </div>
          <Badge tone={userStatusTone[displayStaff.status]}>{displayStaff.status}</Badge>
          <div className="staff-lines">
            <span><Mail size={18} /> {displayStaff.email}</span>
            <span><Phone size={18} /> {displayStaff.phone}</span>
            <span><CalendarDays size={18} /> {todayAppointments.length} appointments today</span>
          </div>
          {!readOnly && !editMode && <Button icon={<Clock size={17} />} onClick={() => onEditWorkingHours(staff)}>Edit Working Hours / Shifts</Button>}
        </aside>
        <section className="detail-main patient-main">
          <div className="patient-main-header">
            <div>
              <h2 className="section-title">{displayStaff.fullName}</h2>
              <p className="tiny">Profile, schedule, and assigned appointment context.</p>
            </div>
            {!readOnly && (
              <div className="right">
                {editMode ? (
                  <>
                    <Button variant="secondary" onClick={cancelChanges}>Cancel</Button>
                    <Button icon={<Save size={17} />} disabled={Boolean(validationMessage)} onClick={saveChanges}>Save Changes</Button>
                  </>
                ) : (
                  <Button variant="secondary" icon={<Pencil size={17} />} onClick={() => setEditMode(true)}>Edit</Button>
                )}
              </div>
            )}
          </div>
          <Tabs tabs={tabs} activeId={activeTab} onChange={setActiveTab} />
        </section>
      </div>
      <AppointmentModal
        appointment={selectedAppointment}
        mode="view"
        open={Boolean(selectedAppointment)}
        appointments={appointments}
        availabilityExceptions={availabilityExceptions}
        onClose={() => setSelectedAppointment(null)}
      />
    </Drawer>
  );
}
