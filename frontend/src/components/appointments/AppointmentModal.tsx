import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSession } from "../../context/SessionContext";
import { getPatientById, getStaffProfileById, patients, staffProfiles } from "../../data/adapters";
import { routes } from "../../routes";
import type { AppointmentStatus, BackendAppointment, BackendAppointmentChangeLog, BackendAvailabilityException, BackendPatient, BackendShift, BackendStaffProfile } from "../../types/models";
import { addMinutes, intervalsOverlap, isDoctorAvailableForInterval, toDateTime } from "../../utils/availability";
import { currency, fullPatientName } from "../../utils/format";
import { loadMockShifts, saveActiveVisitAppointmentId } from "../../utils/mockClinicState";
import { appointmentStatusTone } from "../../utils/statusStyles";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { Select } from "../ui/Select";
import { Textarea } from "../ui/Textarea";
import { TimeInput } from "../ui/TimeInput";

interface AppointmentModalProps {
  appointment: BackendAppointment | null;
  open: boolean;
  mode: "view" | "new";
  slotTime?: string;
  slotDate?: string;
  initialPatientId?: string;
  patientOptions?: BackendPatient[];
  staffOptions?: BackendStaffProfile[];
  shifts?: BackendShift[];
  appointments?: BackendAppointment[];
  availabilityExceptions?: BackendAvailabilityException[];
  changeLogs?: BackendAppointmentChangeLog[];
  onCreate?: (appointment: BackendAppointment) => void;
  onUpdate?: (appointment: BackendAppointment) => void;
  onStatusChange?: (appointment: BackendAppointment, status: AppointmentStatus) => void;
  onRescheduleRequest?: (appointment: BackendAppointment) => void;
  onClose: () => void;
}

const visitTypes = [
  "Initial Consultation",
  "Routine Checkup",
  "Treatment Continuation",
  "Follow-up Visit",
  "Emergency Visit",
  "X-ray Review",
  "Post-treatment Review",
  "Cleaning Visit",
];
export function AppointmentModal({
  appointment,
  open,
  mode,
  slotTime = "09:00",
  slotDate = "2026-02-09",
  initialPatientId,
  patientOptions = patients,
  staffOptions = staffProfiles,
  shifts = loadMockShifts(),
  appointments = [],
  availabilityExceptions = [],
  changeLogs = [],
  onCreate,
  onUpdate,
  onStatusChange,
  onRescheduleRequest,
  onClose,
}: AppointmentModalProps) {
  const navigate = useNavigate();
  const { currentUser } = useSession();
  const [editMode, setEditMode] = useState(mode === "new");
  const [displayedStatus, setDisplayedStatus] = useState<AppointmentStatus>("Scheduled");
  const [feedback, setFeedback] = useState("");
  const [form, setForm] = useState({
    patientName: "",
    doctorName: staffOptions.find((profile) => profile.role === "Doctor")?.fullName ?? staffOptions[0].fullName,
    visitType: "Routine Checkup",
    date: slotDate,
    time: slotTime,
    durationMinutes: "30",
    notes: "",
  });

  useEffect(() => {
    setEditMode(mode === "new");
    setDisplayedStatus(appointment?.status ?? "Scheduled");
    setFeedback("");
    const nextPatient = appointment
      ? getPatientById(appointment.patientId) ?? patientOptions.find((item) => item.patientId === appointment.patientId) ?? patientOptions[0]
      : initialPatientId
        ? patientOptions.find((item) => item.patientId === initialPatientId) ?? getPatientById(initialPatientId)
        : undefined;
    const nextDoctor = staffOptions.find((profile) => profile.id === appointment?.doctorId)
      ?? getStaffProfileById(appointment?.doctorId)
      ?? staffOptions.find((profile) => profile.role === "Doctor")
      ?? staffProfiles.find((profile) => profile.role === "Doctor")
      ?? staffProfiles[0];
    setForm({
      patientName: nextPatient ? fullPatientName(nextPatient) : "",
      doctorName: nextDoctor.fullName,
      visitType: appointment?.visitType ?? "Routine Checkup",
      date: appointment?.date ?? slotDate,
      time: appointment?.time ?? slotTime,
      durationMinutes: String(appointment?.durationMinutes ?? 30),
      notes: appointment?.notes ?? "",
    });
  }, [mode, appointment, initialPatientId, patientOptions, slotDate, slotTime, staffOptions]);

  const uniquePatientOptions = useMemo(() => {
    const byId = new Map<string, BackendPatient>();
    patientOptions.forEach((item) => byId.set(item.patientId, item));
    return Array.from(byId.values());
  }, [patientOptions]);
  const patient = useMemo(
    () => getPatientById(appointment?.patientId) ?? uniquePatientOptions.find((item) => item.patientId === appointment?.patientId) ?? patients[0],
    [appointment, uniquePatientOptions],
  );
  const doctor = useMemo(
    () => staffOptions.find((profile) => profile.id === appointment?.doctorId) ?? getStaffProfileById(appointment?.doctorId) ?? staffOptions[0] ?? staffProfiles[0],
    [appointment, staffOptions],
  );
  const selectedPatient = uniquePatientOptions.find((item) => fullPatientName(item) === form.patientName);
  const doctorOptions = staffOptions.filter((item) => item.role === "Doctor");
  const selectedDoctor = doctorOptions.find((profile) => profile.fullName === form.doctorName);
  const parsedDuration = Number(form.durationMinutes) || 0;
  const proposedStart = form.date && form.time ? toDateTime(form.date, form.time) : "";
  const proposedEnd = proposedStart && parsedDuration > 0 ? addMinutes(proposedStart, parsedDuration) : "";
  const dayOfWeek = form.date ? new Intl.DateTimeFormat("en-US", { weekday: "long" }).format(new Date(`${form.date}T00:00:00`)) : "";
  const hasDoctorConflict = Boolean(
    selectedDoctor &&
      form.date &&
      form.time &&
      parsedDuration > 0 &&
      appointments.some((item) => {
        if (item.id === appointment?.id) return false;
        if (item.doctorId !== selectedDoctor.id) return false;
        if (["Completed", "Cancelled", "No-show", "Postponed"].includes(item.status)) return false;
        return intervalsOverlap(proposedStart, proposedEnd, toDateTime(item.date, item.time), addMinutes(toDateTime(item.date, item.time), item.durationMinutes));
      }),
  );
  const doctorBlockedByLeave = Boolean(
    selectedDoctor &&
      proposedStart &&
      proposedEnd &&
      availabilityExceptions.some((exception) =>
        exception.status === "Active" &&
        exception.userRole === "Doctor" &&
        exception.userId === selectedDoctor.id &&
        intervalsOverlap(proposedStart, proposedEnd, exception.startDateTime, exception.endDateTime),
      ),
  );
  const doctorOutsideWorkingHours = Boolean(
    selectedDoctor &&
      form.date &&
      form.time &&
      parsedDuration > 0 &&
      !isDoctorAvailableForInterval({
        doctorId: selectedDoctor.id,
        date: form.date,
        time: form.time,
        durationMinutes: parsedDuration,
        appointments,
        shifts,
        exceptions: availabilityExceptions,
        dayOfWeek,
        ignoreAppointmentId: appointment?.id,
      }) &&
      !hasDoctorConflict &&
      !doctorBlockedByLeave,
  );
  const canManageAppointments = currentUser.role === "Staff";
  const canStartVisit = currentUser.role === "Doctor" && ["Checked-in", "In Visit"].includes(displayedStatus);
  const isReadOnly = !canManageAppointments && mode !== "new";
  const canSave =
    canManageAppointments &&
    Boolean(selectedPatient) &&
    Boolean(selectedDoctor) &&
    Boolean(form.date) &&
    Boolean(form.time) &&
    parsedDuration >= 15 &&
    !hasDoctorConflict &&
    !doctorBlockedByLeave &&
    !doctorOutsideWorkingHours;
  const canReschedule = canManageAppointments && appointment?.status === "Needs Reschedule";
  const patientSelectOptions = ["Select patient", ...uniquePatientOptions.map(fullPatientName)];

  const saveNewAppointment = () => {
    if (!canSave || !selectedPatient || !selectedDoctor || mode !== "new") return;
    onCreate?.({
      id: `APT-${Date.now()}`,
      patientId: selectedPatient.patientId,
      doctorId: selectedDoctor.id,
      visitType: form.visitType,
      date: form.date,
      time: form.time,
      durationMinutes: parsedDuration,
      due: 0,
      status: "Scheduled",
      notes: form.notes.trim(),
    });
    onClose();
  };

  const saveExistingAppointment = () => {
    if (!appointment || !canSave || !selectedPatient || !selectedDoctor || mode === "new") return;
    const updated: BackendAppointment = {
      ...appointment,
      patientId: selectedPatient.patientId,
      doctorId: selectedDoctor.id,
      visitType: form.visitType,
      date: form.date,
      time: form.time,
      durationMinutes: parsedDuration,
      notes: form.notes.trim(),
    };
    onUpdate?.(updated);
    setDisplayedStatus(updated.status);
    setFeedback("Appointment changes saved.");
    setEditMode(false);
  };

  const applyStatus = (status: AppointmentStatus) => {
    if (!appointment) return;
    setDisplayedStatus(status);
    onStatusChange?.(appointment, status);
    setFeedback(`Appointment marked ${status}.`);
  };

  const openActiveVisit = () => {
    if (!appointment) return;
    saveActiveVisitAppointmentId(appointment.id);
    if (displayedStatus === "Checked-in") {
      applyStatus("In Visit");
    }
    navigate(routes.doctor.activeVisit);
  };

  const footer = editMode ? (
    <>
      <Button variant="secondary" onClick={onClose}>Close</Button>
      <Button disabled={!canSave} onClick={mode === "new" ? saveNewAppointment : saveExistingAppointment}>Save</Button>
    </>
  ) : mode === "new" ? null : (
    <>
      {canManageAppointments && <Button variant="secondary" onClick={() => setEditMode(true)}>Edit</Button>}
      {canReschedule && appointment && <Button onClick={() => onRescheduleRequest?.(appointment)}>Reschedule</Button>}
      {canManageAppointments && nextStatus(displayedStatus) && (
        <Button onClick={() => applyStatus(nextStatus(displayedStatus) ?? displayedStatus)}>
          Mark {nextStatus(displayedStatus)}
        </Button>
      )}
      {canManageAppointments && <Button variant="secondary" onClick={() => applyStatus("Postponed")}>Postpone</Button>}
      {canManageAppointments && <Button variant="ghost" onClick={() => applyStatus("No-show")}>No-show</Button>}
      {canManageAppointments && <Button variant="danger" onClick={() => applyStatus("Cancelled")}>Cancel Appointment</Button>}
      {canStartVisit && <Button onClick={openActiveVisit}>{displayedStatus === "In Visit" ? "Continue Visit" : "Start Visit"}</Button>}
      {isReadOnly && <Button variant="secondary" onClick={onClose}>Close</Button>}
    </>
  );

  return (
    <Modal
      title={mode === "new" ? "New Appointment" : "Appointment Details"}
      subtitle={mode === "new" ? "Book a clinic appointment with local mock data." : appointment?.id}
      open={open}
      onClose={onClose}
      width={680}
      footer={footer}
    >
      {editMode ? (
        <div className="stack">
          <div className="field-grid">
            <Select label="Patient" options={patientSelectOptions} value={form.patientName || "Select patient"} onChange={(event) => setForm((current) => ({ ...current, patientName: event.target.value === "Select patient" ? "" : event.target.value }))} />
            <Select label="Doctor" options={doctorOptions.map((item) => item.fullName)} value={form.doctorName} onChange={(event) => setForm((current) => ({ ...current, doctorName: event.target.value }))} />
            <Select label="Visit Type" options={visitTypes} value={form.visitType} onChange={(event) => setForm((current) => ({ ...current, visitType: event.target.value }))} />
            <Input label="Date" type="date" value={form.date} onChange={(event) => setForm((current) => ({ ...current, date: event.target.value }))} />
            <TimeInput label="Time" value={form.time} onChange={(event) => setForm((current) => ({ ...current, time: event.target.value }))} />
            <Input label="Duration" type="number" min="15" value={form.durationMinutes} onChange={(event) => setForm((current) => ({ ...current, durationMinutes: event.target.value }))} />
          </div>
          <Textarea label="Notes" value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} />
          {mode === "new" && <div className="notice-card">New appointments are created as Scheduled.</div>}
          {hasDoctorConflict && <div className="alert-card">This doctor already has an overlapping appointment. Choose another time or doctor.</div>}
          {doctorBlockedByLeave && <div className="alert-card">This doctor has an active leave exception covering that slot.</div>}
          {doctorOutsideWorkingHours && <div className="alert-card">This slot is outside the doctor's working hours.</div>}
        </div>
      ) : appointment ? (
        <div className="stack">
          {feedback && <div className="notice-card">{feedback}</div>}
          {displayedStatus === "Needs Reschedule" && (
            <div className="alert-card">
              This appointment needs reception follow-up before it can return to the normal schedule.
            </div>
          )}
          <div className="appointment-detail-grid">
            <div><span>Patient</span><strong>{fullPatientName(patient)}</strong></div>
            <div><span>Doctor</span><strong>{doctor.fullName}</strong></div>
            <div><span>Visit Type</span><strong>{appointment.visitType}</strong></div>
            <div><span>Date</span><strong>{appointment.date}</strong></div>
            <div><span>Time</span><strong>{appointment.time}</strong></div>
            <div><span>Duration</span><strong>{appointment.durationMinutes} minutes</strong></div>
            <div><span>Due</span><strong>{currency(appointment.due)}</strong></div>
            <div><span>Status</span><Badge tone={appointmentStatusTone[displayedStatus]}>{displayedStatus}</Badge></div>
            <div className="span-2"><span>Notes</span><strong>{appointment.notes}</strong></div>
            {canManageAppointments && (
              <div className="span-2 right">
                {canReschedule && <Button onClick={() => onRescheduleRequest?.(appointment)}>Reschedule</Button>}
                <Button variant="ghost" onClick={() => applyStatus("No-show")}>Mark No-show</Button>
                <Button variant="ghost" onClick={() => applyStatus("Postponed")}>Postpone</Button>
              </div>
            )}
          </div>
          <div className="soft-panel">
            <h3 className="card-title">Appointment Change Log</h3>
            {changeLogs.length > 0 ? (
              <div className="stack mt-16">
                {changeLogs.map((log) => {
                  const oldDoctor = getStaffProfileById(log.oldDoctorId);
                  const newDoctor = getStaffProfileById(log.newDoctorId);
                  return (
                    <div className="soft-panel" key={log.logId}>
                      <div className="between">
                        <strong>{log.reason}</strong>
                        <span className="tiny">{formatLogDateTime(log.changedAt)}</span>
                      </div>
                      <p className="tiny">Changed by {log.changedBy}</p>
                      <dl className="detail-list">
                        <div><dt>Old time</dt><dd>{formatLogDateTime(log.oldDateTime)}</dd></div>
                        <div><dt>New time</dt><dd>{formatLogDateTime(log.newDateTime)}</dd></div>
                        <div><dt>Old doctor</dt><dd>{oldDoctor?.fullName ?? log.oldDoctorId}</dd></div>
                        <div><dt>New doctor</dt><dd>{newDoctor?.fullName ?? log.newDoctorId}</dd></div>
                      </dl>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="empty-inline mt-16">No appointment changes recorded yet.</div>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

function formatLogDateTime(value: string) {
  return value.replace("T", " ");
}

function nextStatus(status: AppointmentStatus): AppointmentStatus | null {
  const transitions: Partial<Record<AppointmentStatus, AppointmentStatus>> = {
    Scheduled: "Arrived",
    Arrived: "Checked-in",
    "Checked-in": "In Visit",
    "In Visit": "Completed",
  };
  return transitions[status] ?? null;
}
