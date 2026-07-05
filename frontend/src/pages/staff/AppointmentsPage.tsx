import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, Search } from "lucide-react";
import {
  adaptAppointmentDTO,
  createAppointment,
  listAppointments,
  rescheduleAppointment as rescheduleAppointmentRequest,
  runAppointmentWorkflowAction,
  toAppointmentPayload,
  toAppointmentStatusPayload,
  toAppointmentUpdatePayload,
  updateAppointment,
  type AppointmentWorkflowAction,
} from "../../api/appointments";
import { listAvailabilityExceptions, adaptAvailabilityExceptionDTO } from "../../api/availabilityExceptions";
import { adaptEmployeeProfileDTO, listEmployeeProfiles } from "../../api/employeeProfiles";
import { isApiError } from "../../api/errors";
import { adaptPatientDTO, listPatients } from "../../api/patients";
import { adaptWorkingShiftList, listWorkingShifts } from "../../api/workingShifts";
import { AppointmentCalendar } from "../../components/appointments/AppointmentCalendar";
import { AppointmentModal } from "../../components/appointments/AppointmentModal";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { FilterPopover } from "../../components/ui/FilterPopover";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import { TimeInput } from "../../components/ui/TimeInput";
import { useCurrentUser, useSession } from "../../context/SessionContext";
import { getPatientById, getStaffProfileById } from "../../data/adapters";
import type {
  AppointmentChangeLog,
  AppointmentStatus,
  BackendAppointment,
  BackendAppointmentChangeLog,
  BackendAvailabilityException,
  BackendPatient,
  BackendShift,
  BackendStaffProfile,
} from "../../types/models";
import {
  getAvailableDoctorsForSlot,
  isDoctorAvailableForInterval,
  toDateTime,
  toLocalDateTime,
} from "../../utils/availability";
import { fullPatientName } from "../../utils/format";
import {
  loadMockAppointmentChangeLogs,
} from "../../utils/mockScheduleState";
import { timePresetOptions } from "../../utils/shifts";
import { appointmentStatusTone, appointmentStatusVisual } from "../../utils/statusStyles";

type ViewMode = "Day" | "Week" | "Month";
type AppointmentSection = "Calendar" | "Reschedule Queue";
type RescheduleReason = AppointmentChangeLog["reason"];

const initialSelectedDate = "2026-02-09";
const calendarSlots = timePresetOptions;
const statusOptions: ("All" | AppointmentStatus)[] = [
  "All",
  "Scheduled",
  "Arrived",
  "Checked-in",
  "In Visit",
  "Completed",
  "Cancelled",
  "No-show",
  "Postponed",
  "Needs Reschedule",
];
const rescheduleReasons: RescheduleReason[] = ["Doctor on leave", "Patient requested reschedule", "Clinic schedule adjustment", "Other"];

export function AppointmentsPage() {
  const currentUser = useCurrentUser();
  const { accessToken, clearSession } = useSession();
  const [appointmentRows, setAppointmentRows] = useState<BackendAppointment[]>([]);
  const [availabilityExceptionRows, setAvailabilityExceptionRows] = useState<BackendAvailabilityException[]>([]);
  const [changeLogRows, setChangeLogRows] = useState<BackendAppointmentChangeLog[]>(loadMockAppointmentChangeLogs);
  const [patientRows, setPatientRows] = useState<BackendPatient[]>([]);
  const [staffProfileRows, setStaffProfileRows] = useState<BackendStaffProfile[]>([]);
  const [shiftRows, setShiftRows] = useState<BackendShift[]>([]);
  const [loadingAppointments, setLoadingAppointments] = useState(true);
  const [pageError, setPageError] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("Day");
  const [selectedDate, setSelectedDate] = useState(initialSelectedDate);
  const [selectedAppointment, setSelectedAppointment] = useState<BackendAppointment | null>(null);
  const [rescheduleAppointment, setRescheduleAppointment] = useState<BackendAppointment | null>(null);
  const [modalMode, setModalMode] = useState<"view" | "new">("view");
  const [slotTime, setSlotTime] = useState("09:00");
  const [slotDate, setSlotDate] = useState(initialSelectedDate);
  const [query, setQuery] = useState("");
  const [doctorFilter, setDoctorFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [activeSection, setActiveSection] = useState<AppointmentSection>("Calendar");

  const doctorProfiles = useMemo(() => staffProfileRows.filter((doctor) => doctor.role === "Doctor"), [staffProfileRows]);
  const activeDoctorProfiles = useMemo(() => doctorProfiles.filter((profile) => profile.status === "Active"), [doctorProfiles]);
  const doctorOptions = useMemo(() => ["All", ...doctorProfiles.map((doctor) => doctor.fullName)], [doctorProfiles]);
  const weekDays = useMemo(() => getWeekDays(selectedDate), [selectedDate]);
  const monthCalendar = useMemo(() => getMonthCalendar(selectedDate), [selectedDate]);
  const periodAppointments = useMemo(
    () => appointmentRows.filter((appointment) => isInView(appointment.date, viewMode, selectedDate, weekDays, monthCalendar.monthKey)),
    [appointmentRows, monthCalendar.monthKey, selectedDate, viewMode, weekDays],
  );
  const needsReschedule = useMemo(
    () => appointmentRows
      .filter((appointment) => appointment.status === "Needs Reschedule")
      .sort((a, b) => `${a.date}T${a.time}`.localeCompare(`${b.date}T${b.time}`)),
    [appointmentRows],
  );
  const visibleAppointments = useMemo(() => {
    const normalized = query.toLowerCase();
    return periodAppointments.filter((appointment) => {
      const patient = findPatient(patientRows, appointment.patientId);
      const doctor = findStaffProfile(staffProfileRows, appointment.doctorId);
      const text = `${patient ? fullPatientName(patient) : appointment.patientId} ${doctor?.fullName ?? ""} ${appointment.visitType} ${appointment.date} ${appointment.time}`.toLowerCase();
      const matchesDoctor = doctorFilter === "All" || doctor?.fullName === doctorFilter;
      const matchesStatus = statusFilter === "All" || appointment.status === statusFilter;
      return text.includes(normalized) && matchesDoctor && matchesStatus;
    });
  }, [doctorFilter, patientRows, periodAppointments, query, staffProfileRows, statusFilter]);

  const activeFilters = (doctorFilter !== "All" ? 1 : 0) + (statusFilter !== "All" ? 1 : 0);
  const summaryTitle = viewMode === "Day" ? "Today's Summary" : viewMode === "Week" ? "Week Summary" : "Month Summary";
  const canCreateAppointments = currentUser.role === "Staff";
  const queueVisible = currentUser.role === "Staff" || currentUser.role === "Admin";
  const canManageReschedule = currentUser.role === "Staff";
  const selectedDayName = dayNameFromDate(selectedDate);

  useEffect(() => {
    if (!accessToken) {
      setLoadingAppointments(false);
      setPageError("Sign in again to view appointments.");
      return;
    }

    let cancelled = false;
    setLoadingAppointments(true);
    setPageError("");

    Promise.all([
      listAppointments({ accessToken }),
      listPatients({ accessToken }),
      listEmployeeProfiles({ accessToken }),
      listWorkingShifts({ accessToken }),
      listAvailabilityExceptions({ accessToken }),
    ])
      .then(([appointments, patients, profiles, shifts, exceptions]) => {
        if (cancelled) return;
        setAppointmentRows(sortAppointments(appointments.map(adaptAppointmentDTO)));
        setPatientRows(patients.map(adaptPatientDTO));
        setStaffProfileRows(profiles.map(adaptEmployeeProfileDTO));
        setShiftRows(adaptWorkingShiftList(shifts));
        setAvailabilityExceptionRows(exceptions.map(adaptAvailabilityExceptionDTO));
        setPageError("");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        handleAuthError(error, clearSession);
        setPageError(toAppointmentErrorMessage(error, "Unable to load appointments."));
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

  const openNew = (time = "09:00", date = selectedDate) => {
    if (!canCreateAppointments) return;
    setSlotTime(time);
    setSlotDate(date);
    setSelectedAppointment(null);
    setModalMode("new");
  };

  const openView = (appointment: BackendAppointment) => {
    setSelectedAppointment(appointment);
    setModalMode("view");
  };

  const closeModal = () => {
    setSelectedAppointment(null);
    setModalMode("view");
  };

  const navigateToDay = (date: string) => {
    setSelectedDate(date);
    setViewMode("Day");
  };

  const movePeriod = (direction: -1 | 1) => {
    setSelectedDate((current) => {
      if (viewMode === "Day") return addDays(current, direction);
      if (viewMode === "Week") return addDays(current, direction * 7);
      return addMonths(current, direction);
    });
  };

  const saveReschedule = async (updatedAppointment: BackendAppointment, changeLog: BackendAppointmentChangeLog) => {
    if (!accessToken) {
      throw new Error("Sign in again to reschedule appointments.");
    }
    try {
      const response = await rescheduleAppointmentRequest(updatedAppointment.id, {
        ...toAppointmentUpdatePayload(updatedAppointment),
        reason: changeLog.reason,
      }, { accessToken });
      const savedAppointment = adaptAppointmentDTO(response.appointment);
      const nextLogs = [...changeLogRows, changeLog];
      setAppointmentRows((current) => sortAppointments(current.map((appointment) => appointment.id === savedAppointment.id ? savedAppointment : appointment)));
      setChangeLogRows(nextLogs);
      setSelectedAppointment((current) => current?.id === savedAppointment.id ? savedAppointment : current);
      setSelectedDate(savedAppointment.date);
      setPageError("");
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toAppointmentErrorMessage(error, "Unable to reschedule appointment."));
    }
    setViewMode("Day");
    setRescheduleAppointment(null);
  };

  const saveNewAppointment = async (appointment: BackendAppointment) => {
    if (!accessToken) {
      throw new Error("Sign in again to create appointments.");
    }
    try {
      const savedAppointment = adaptAppointmentDTO(await createAppointment(toAppointmentPayload(appointment), { accessToken }));
      setAppointmentRows((current) => sortAppointments([...current, savedAppointment]));
      setSelectedDate(savedAppointment.date);
      setPageError("");
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toAppointmentErrorMessage(error, "Unable to create appointment."));
    }
    setViewMode("Day");
    setModalMode("view");
    setSelectedAppointment(null);
  };

  const saveUpdatedAppointment = async (updatedAppointment: BackendAppointment) => {
    if (!accessToken) {
      throw new Error("Sign in again to edit appointments.");
    }
    try {
      const savedAppointment = adaptAppointmentDTO(await updateAppointment(updatedAppointment.id, toAppointmentUpdatePayload(updatedAppointment), { accessToken }));
      setAppointmentRows((current) => sortAppointments(current.map((appointment) => appointment.id === savedAppointment.id ? savedAppointment : appointment)));
      setSelectedAppointment((current) => current?.id === savedAppointment.id ? savedAppointment : current);
      setPageError("");
      return savedAppointment;
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toAppointmentErrorMessage(error, "Unable to save appointment."));
    }
  };

  const saveAppointmentStatus = async (appointment: BackendAppointment, status: AppointmentStatus) => {
    if (!accessToken) {
      throw new Error("Sign in again to update appointments.");
    }
    try {
      const savedAppointment = adaptAppointmentDTO(await runAppointmentWorkflowAction(appointment.id, toWorkflowAction(status), toAppointmentStatusPayload(appointment, status), { accessToken }));
      setAppointmentRows((current) => sortAppointments(current.map((item) => item.id === savedAppointment.id ? savedAppointment : item)));
      setSelectedAppointment((current) => current?.id === savedAppointment.id ? savedAppointment : current);
      setPageError("");
      return savedAppointment;
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toAppointmentErrorMessage(error, "Unable to update appointment status."));
    }
  };

  return (
    <div className="page-shell">
      <PageHeader
        title="Appointments"
        subtitle="Manage clinic appointments."
        actions={canCreateAppointments && <Button icon={<Plus size={18} />} onClick={() => openNew()}>New Appointment</Button>}
      />
      {pageError && <div className="alert-card">{pageError}</div>}
      <Card className="calendar-controls">
        {activeSection === "Calendar" ? (
          <>
            <Button variant="secondary" icon={<ChevronLeft size={17} />} aria-label="Previous period" onClick={() => movePeriod(-1)} />
            <h2 className="card-title">{calendarTitle(viewMode, selectedDate, weekDays)}</h2>
            <Button variant="secondary" icon={<ChevronRight size={17} />} aria-label="Next period" onClick={() => movePeriod(1)} />
          </>
        ) : (
          <div>
            <h2 className="card-title">Reschedule Queue</h2>
            <p className="tiny">Appointments needing staff follow-up.</p>
          </div>
        )}
        <div className="grow" />
        {queueVisible && (
          <SegmentedControl<AppointmentSection> options={["Calendar", "Reschedule Queue"]} value={activeSection} onChange={setActiveSection} />
        )}
        {activeSection === "Calendar" && <SegmentedControl<ViewMode> options={["Day", "Week", "Month"]} value={viewMode} onChange={setViewMode} />}
      </Card>
      {activeSection === "Reschedule Queue" && queueVisible ? (
        <RescheduleQueue
          appointments={needsReschedule}
          patientRows={patientRows}
          staffProfiles={staffProfileRows}
          canManage={canManageReschedule}
          onOpen={openView}
          onReschedule={setRescheduleAppointment}
        />
      ) : (
        <>
          <Card>
            <div className="filter-card">
              <Input icon={<Search size={18} />} placeholder="Search by patient, doctor, treatment, date, or time..." value={query} onChange={(event) => setQuery(event.target.value)} />
              <FilterPopover activeCount={activeFilters}>
                <div className="filter-popover-content">
                  <Select label="Doctor" options={doctorOptions} value={doctorFilter} onChange={(event) => setDoctorFilter(event.target.value)} />
                  <Select label="Status" options={statusOptions} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} />
                  <Button
                    variant="ghost"
                    type="button"
                    onClick={() => {
                      setDoctorFilter("All");
                      setStatusFilter("All");
                    }}
                  >
                    Clear filters
                  </Button>
                </div>
              </FilterPopover>
            </div>
          </Card>
          <div className="appointments-layout">
            <Card>
              <h2 className="card-title">Schedule</h2>
              {viewMode === "Day" && (
                loadingAppointments ? <div className="empty-inline">Loading appointments...</div> : <AppointmentCalendar
                  appointments={visibleAppointments.filter((appointment) => appointment.date === selectedDate)}
                  onAppointmentClick={openView}
                  onSlotClick={(time) => openNew(time, selectedDate)}
                  canCreate={canCreateAppointments}
                  patientOptions={patientRows}
                  staffOptions={staffProfileRows}
                  isSlotAvailable={(time) =>
                    getAvailableDoctorsForSlot({
                      date: selectedDate,
                      time,
                      durationMinutes: 30,
                      appointments: appointmentRows,
                      shifts: shiftRows,
                      exceptions: availabilityExceptionRows,
                      staffProfiles: staffProfileRows,
                    }).length > 0
                  }
                />
              )}
              {viewMode === "Week" && (
                <div className="calendar-scroll">
                  <WeekCalendarView appointments={visibleAppointments} weekDays={weekDays} onAppointmentClick={openView} onDayNavigate={navigateToDay} />
                </div>
              )}
              {viewMode === "Month" && (
                <div className="calendar-scroll">
                  <MonthCalendarView
                    appointments={visibleAppointments}
                    monthDays={monthCalendar.monthDays}
                    leadingBlanks={monthCalendar.leadingBlanks}
                    onAppointmentClick={openView}
                    onDayNavigate={navigateToDay}
                  />
                </div>
              )}
            </Card>
            <aside className="stack">
              <Card>
                <h2 className="card-title">{summaryTitle}</h2>
                <div className="summary-list mt-16">
                  <span>Total <strong>{visibleAppointments.length}</strong></span>
                  <span>Scheduled <Badge tone="primary">{countByStatuses(visibleAppointments, ["Scheduled"])}</Badge></span>
                  <span>In Visit <Badge tone="indigo">{countByStatuses(visibleAppointments, ["In Visit"])}</Badge></span>
                  <span>Completed <Badge tone="green">{countByStatuses(visibleAppointments, ["Completed"])}</Badge></span>
                  <span>Needs Reschedule <Badge tone="orange">{countByStatuses(visibleAppointments, ["Needs Reschedule"])}</Badge></span>
                  <span>Needs Follow-up <Badge tone="warning">{countByStatuses(visibleAppointments, ["Postponed", "No-show", "Cancelled"])}</Badge></span>
                </div>
              </Card>
              <Card>
                <h2 className="card-title">Available Doctors</h2>
                <div className="stack mt-16">
                  {doctorProfiles.map((doctor) => {
                    const shifts = shiftRows.filter((item) => item.staffOrDoctorId === doctor.id && item.dayOfWeek === selectedDayName && item.isActive !== false);
                    const available = doctor.status === "Active" && calendarSlots.some((time) =>
                      isDoctorAvailableForInterval({
                        doctorId: doctor.id,
                        date: selectedDate,
                        time,
                        durationMinutes: 30,
                        appointments: appointmentRows,
                        shifts: shiftRows,
                        exceptions: availabilityExceptionRows,
                        dayOfWeek: selectedDayName,
                      }),
                    );
                    return (
                      <div className="soft-panel between" key={doctor.id}>
                        <div>
                          <strong>{doctor.fullName}</strong>
                          <div className="tiny">{doctor.specialty}</div>
                          <div className="tiny">{shifts.length ? shifts.map((shift) => `${shift.shiftName} ${shift.startTime}-${shift.endTime}`).join(", ") : "No weekly shift"}</div>
                        </div>
                        <Badge tone={available ? "green" : "warning"}>{available ? "Available" : "Unavailable"}</Badge>
                      </div>
                    );
                  })}
                </div>
              </Card>
              <Card>
                <h2 className="card-title">Quick Actions</h2>
                <div className="action-list mt-16">
                  {canCreateAppointments && <Button variant="secondary" onClick={() => openNew("09:00")}>Add Walk-in</Button>}
                  <Button variant="secondary" onClick={() => setViewMode("Month")}>View Calendar</Button>
                  <Button variant="secondary" onClick={() => setViewMode("Week")}>Manage Time Slots</Button>
                </div>
              </Card>
            </aside>
          </div>
        </>
      )}
      <AppointmentModal
        appointment={selectedAppointment}
        mode={modalMode}
        slotTime={slotTime}
        slotDate={slotDate}
        appointments={appointmentRows}
        patientOptions={patientRows}
        staffOptions={staffProfileRows}
        shifts={shiftRows}
        availabilityExceptions={availabilityExceptionRows}
        changeLogs={selectedAppointment ? changeLogRows.filter((log) => log.appointmentId === selectedAppointment.id) : []}
        open={modalMode === "new" || Boolean(selectedAppointment)}
        onClose={closeModal}
        onCreate={saveNewAppointment}
        onUpdate={saveUpdatedAppointment}
        onStatusChange={saveAppointmentStatus}
        onRescheduleRequest={setRescheduleAppointment}
      />
      <RescheduleModal
        appointment={rescheduleAppointment}
        appointmentRows={appointmentRows}
        doctorProfiles={activeDoctorProfiles}
        shiftRows={shiftRows}
        availabilityExceptionRows={availabilityExceptionRows}
        changedBy={currentUser.fullName}
        onClose={() => setRescheduleAppointment(null)}
        onSave={saveReschedule}
      />
    </div>
  );
}

function RescheduleQueue({
  appointments,
  patientRows,
  staffProfiles,
  canManage,
  onOpen,
  onReschedule,
}: {
  appointments: BackendAppointment[];
  patientRows: BackendPatient[];
  staffProfiles: BackendStaffProfile[];
  canManage: boolean;
  onOpen: (appointment: BackendAppointment) => void;
  onReschedule: (appointment: BackendAppointment) => void;
}) {
  return (
    <Card>
      <div className="between">
        <div>
          <h2 className="card-title">Reschedule Queue</h2>
          <p className="tiny">Only appointments currently marked Needs Reschedule appear here.</p>
        </div>
        <Badge tone="orange">{appointments.length} pending</Badge>
      </div>
      <div className="reschedule-queue-list mt-16">
        {appointments.map((appointment) => {
          const patient = findPatient(patientRows, appointment.patientId);
          const doctor = findStaffProfile(staffProfiles, appointment.doctorId);
          return (
            <article className="soft-panel reschedule-queue-card" key={appointment.id}>
              <div>
                <span className="tiny">Patient</span>
                <strong>{patient ? fullPatientName(patient) : appointment.patientId}</strong>
              </div>
              <div>
                <span className="tiny">Current date/time</span>
                <strong>{appointment.date} at {appointment.time}</strong>
              </div>
              <div>
                <span className="tiny">Doctor</span>
                <strong>{doctor?.fullName ?? appointment.doctorId}</strong>
              </div>
              <div className="reschedule-reason">
                <span className="tiny">Reason / leave conflict</span>
                <p className="muted">{appointment.notes || "Needs reception follow-up."}</p>
              </div>
              <div className="right">
                {!canManage && <Button variant="secondary" onClick={() => onOpen(appointment)}>View Details</Button>}
                {canManage && <Button onClick={() => onReschedule(appointment)}>Reschedule</Button>}
              </div>
            </article>
          );
        })}
      </div>
      {appointments.length === 0 && <div className="empty-inline mt-16">No appointments need rescheduling.</div>}
    </Card>
  );
}

function RescheduleModal({
  appointment,
  appointmentRows,
  doctorProfiles,
  shiftRows,
  availabilityExceptionRows,
  changedBy,
  onClose,
  onSave,
}: {
  appointment: BackendAppointment | null;
  appointmentRows: BackendAppointment[];
  doctorProfiles: BackendStaffProfile[];
  shiftRows: BackendShift[];
  availabilityExceptionRows: BackendAvailabilityException[];
  changedBy: string;
  onClose: () => void;
  onSave: (appointment: BackendAppointment, changeLog: BackendAppointmentChangeLog) => void;
}) {
  const initialDoctor = getStaffProfileById(appointment?.doctorId);
  const [doctorName, setDoctorName] = useState(initialDoctor?.fullName ?? doctorProfiles[0]?.fullName ?? "");
  const [date, setDate] = useState(appointment?.date ?? initialSelectedDate);
  const [time, setTime] = useState(appointment?.time ?? "09:00");
  const [duration, setDuration] = useState(String(appointment?.durationMinutes ?? 30));
  const [reason, setReason] = useState<RescheduleReason>("Doctor on leave");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!appointment) return;
    const nextDoctor = getStaffProfileById(appointment.doctorId);
    setDoctorName(nextDoctor?.fullName ?? doctorProfiles[0]?.fullName ?? "");
    setDate(appointment.date);
    setTime(appointment.time);
    setDuration(String(appointment.durationMinutes));
    setReason("Doctor on leave");
    setNotes("");
  }, [appointment?.id, doctorProfiles]);

  const selectedDoctor = doctorProfiles.find((doctor) => doctor.fullName === doctorName);
  const durationMinutes = Number(duration) || 0;
  const dayOfWeek = dayNameFromDate(date);
  const hasChanged = Boolean(
    appointment &&
      (appointment.date !== date ||
        appointment.time !== time ||
        appointment.doctorId !== selectedDoctor?.id ||
        appointment.durationMinutes !== durationMinutes),
  );
  const available = Boolean(
    appointment &&
      selectedDoctor &&
      durationMinutes >= 15 &&
      isDoctorAvailableForInterval({
        doctorId: selectedDoctor.id,
        date,
        time,
        durationMinutes,
        appointments: appointmentRows,
        shifts: shiftRows,
        exceptions: availabilityExceptionRows,
        dayOfWeek,
        ignoreAppointmentId: appointment.id,
      }),
  );
  const canSave = Boolean(appointment && selectedDoctor && durationMinutes >= 15 && hasChanged && available);

  const save = () => {
    if (!appointment || !selectedDoctor || !canSave) return;
    const updated: BackendAppointment = {
      ...appointment,
      doctorId: selectedDoctor.id,
      date,
      time,
      durationMinutes,
      status: "Scheduled",
      notes: notes.trim() ? `${appointment.notes}\nReschedule note: ${notes.trim()}` : appointment.notes,
    };
    const log: BackendAppointmentChangeLog = {
      logId: `LOG-${Date.now()}`,
      appointmentId: appointment.id,
      oldDateTime: toDateTime(appointment.date, appointment.time),
      newDateTime: toDateTime(date, time),
      oldDoctorId: appointment.doctorId,
      newDoctorId: selectedDoctor.id,
      reason,
      changedBy,
      changedAt: toLocalDateTime(new Date()),
    };
    onSave(updated, log);
  };

  return (
    <Modal
      title="Reschedule Appointment"
      subtitle={appointment?.id}
      open={Boolean(appointment)}
      onClose={onClose}
      width={760}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={!canSave} onClick={save}>Save Reschedule</Button>
        </>
      }
    >
      {appointment && (
        <div className="stack">
          <div className="notice-card">
            Choose a new available slot. Saving returns this appointment to Scheduled and records an appointment change log.
          </div>
          <div className="field-grid">
            <Select label="Doctor" options={doctorProfiles.map((doctor) => doctor.fullName)} value={doctorName} onChange={(event) => setDoctorName(event.target.value)} />
            <Select label="Reason" options={rescheduleReasons} value={reason} onChange={(event) => setReason(event.target.value as RescheduleReason)} />
            <Input label="New date" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
            <TimeInput label="New time" value={time} onChange={(event) => setTime(event.target.value)} />
            <Input label="Duration" type="number" min="15" value={duration} onChange={(event) => setDuration(event.target.value)} />
          </div>
          <Textarea label="Staff notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
          {!hasChanged && <div className="alert-card">Choose a different doctor, date, time, or duration before saving.</div>}
          {hasChanged && !available && <div className="alert-card">That doctor is unavailable for this slot because of shifts, leave, or another appointment.</div>}
        </div>
      )}
    </Modal>
  );
}

function WeekCalendarView({
  appointments,
  weekDays,
  onAppointmentClick,
  onDayNavigate,
}: {
  appointments: BackendAppointment[];
  weekDays: CalendarDay[];
  onAppointmentClick: (appointment: BackendAppointment) => void;
  onDayNavigate: (date: string) => void;
}) {
  const [lastTap, setLastTap] = useState<{ date: string; at: number } | null>(null);
  const handleTouchNavigate = (date: string) => {
    const now = Date.now();
    if (lastTap?.date === date && now - lastTap.at < 360) {
      onDayNavigate(date);
    }
    setLastTap({ date, at: now });
  };

  return (
    <div className="week-calendar">
      {weekDays.map((day) => {
        const dayAppointments = appointments.filter((appointment) => appointment.date === day.date);
        return (
          <section
            className="week-day-card"
            key={day.date}
            onDoubleClick={() => onDayNavigate(day.date)}
            onTouchEnd={() => handleTouchNavigate(day.date)}
          >
            <div className="week-day-head">
              <span>{day.label}</span>
              <strong>{day.day}</strong>
            </div>
            <div className="week-appointments">
              {dayAppointments.map((appointment) => (
                <AppointmentChip appointment={appointment} key={appointment.id} onClick={onAppointmentClick} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function MonthCalendarView({
  appointments,
  monthDays,
  leadingBlanks,
  onAppointmentClick,
  onDayNavigate,
}: {
  appointments: BackendAppointment[];
  monthDays: MonthDay[];
  leadingBlanks: number;
  onAppointmentClick: (appointment: BackendAppointment) => void;
  onDayNavigate: (date: string) => void;
}) {
  const [lastTap, setLastTap] = useState<{ date: string; at: number } | null>(null);
  const handleTouchNavigate = (date: string) => {
    const now = Date.now();
    if (lastTap?.date === date && now - lastTap.at < 360) {
      onDayNavigate(date);
    }
    setLastTap({ date, at: now });
  };

  return (
    <div className="month-calendar">
      {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((label) => (
        <div className="month-weekday" key={label}>{label}</div>
      ))}
      {Array.from({ length: leadingBlanks }).map((_, index) => (
        <div className="month-day empty" key={`blank-${index}`} />
      ))}
      {monthDays.map((day) => {
        const dayAppointments = appointments.filter((appointment) => appointment.date === day.date);
        return (
          <article
            className="month-day"
            key={day.date}
            onDoubleClick={() => onDayNavigate(day.date)}
            onTouchEnd={() => handleTouchNavigate(day.date)}
          >
            <div className="between">
              <strong>{day.day}</strong>
              {dayAppointments.length > 0 && <Badge tone="primary">{dayAppointments.length}</Badge>}
            </div>
            <div className="month-day-list">
              {dayAppointments.slice(0, 3).map((appointment) => (
                <AppointmentChip appointment={appointment} key={appointment.id} onClick={onAppointmentClick} compact />
              ))}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function AppointmentChip({
  appointment,
  onClick,
  compact = false,
}: {
  appointment: BackendAppointment;
  onClick: (appointment: BackendAppointment) => void;
  compact?: boolean;
}) {
  const patient = getPatientById(appointment.patientId);
  const doctor = getStaffProfileById(appointment.doctorId);
  const visual = appointmentStatusVisual[appointment.status];

  return (
    <button
      className={compact ? "appointment-chip compact" : "appointment-chip"}
      type="button"
      style={{ borderLeftColor: visual.accent, background: visual.background }}
      onClick={() => onClick(appointment)}
      onDoubleClick={(event) => event.stopPropagation()}
      onTouchEnd={(event) => event.stopPropagation()}
    >
      <strong>{appointment.time}</strong>
      <span>{appointment.patientName || (patient ? fullPatientName(patient) : appointment.patientId)}</span>
      {!compact && <small>{appointment.doctorName || doctor?.fullName}</small>}
    </button>
  );
}

interface CalendarDay {
  date: string;
  label: string;
  day: string;
  dayOfWeek: string;
}

interface MonthDay {
  day: number;
  date: string;
}

function getSuggestedSlots(
  appointment: BackendAppointment,
  appointments: BackendAppointment[],
  shifts: BackendShift[],
  exceptions: BackendAvailabilityException[],
  staffProfiles: BackendStaffProfile[],
) {
  const suggestions: string[] = [];
  const start = parseIsoDate(appointment.date);
  for (let offset = 0; offset < 7 && suggestions.length < 3; offset += 1) {
    const date = toIsoDate(addDaysToDate(start, offset));
    for (const time of calendarSlots) {
      const doctors = getAvailableDoctorsForSlot({
        date,
        time,
        durationMinutes: appointment.durationMinutes,
        appointments,
        shifts,
        exceptions,
        staffProfiles,
      });
      if (doctors.length > 0) {
        suggestions.push(`${date} ${time} (${doctors[0].fullName})`);
      }
      if (suggestions.length >= 3) break;
    }
  }
  return suggestions;
}

function isInView(date: string, viewMode: ViewMode, selectedDate: string, weekDays: CalendarDay[], monthKey: string) {
  if (viewMode === "Day") return date === selectedDate;
  if (viewMode === "Week") return weekDays.some((day) => day.date === date);
  return date.startsWith(monthKey);
}

function countByStatuses(appointments: BackendAppointment[], statuses: AppointmentStatus[]) {
  return appointments.filter((appointment) => statuses.includes(appointment.status)).length;
}

function calendarTitle(viewMode: ViewMode, selectedDate: string, weekDays: CalendarDay[]) {
  if (viewMode === "Day") return formatLongDate(selectedDate);
  if (viewMode === "Week") return `${formatShortDate(weekDays[0].date)} - ${formatShortDate(weekDays[6].date)}`;
  return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(parseIsoDate(selectedDate));
}

function formatLongDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${date}T00:00:00`));
}

function dayNameFromDate(date: string) {
  return new Intl.DateTimeFormat("en-US", { weekday: "long" }).format(parseIsoDate(date));
}

function getWeekDays(selectedDate: string): CalendarDay[] {
  const selected = parseIsoDate(selectedDate);
  const mondayOffset = (selected.getDay() + 6) % 7;
  const monday = new Date(selected);
  monday.setDate(selected.getDate() - mondayOffset);

  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(monday);
    date.setDate(monday.getDate() + index);
    return {
      date: toIsoDate(date),
      label: new Intl.DateTimeFormat("en-US", { weekday: "short" }).format(date),
      day: String(date.getDate()),
      dayOfWeek: new Intl.DateTimeFormat("en-US", { weekday: "long" }).format(date),
    };
  });
}

function getMonthCalendar(selectedDate: string) {
  const selected = parseIsoDate(selectedDate);
  const year = selected.getFullYear();
  const month = selected.getMonth();
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const leadingBlanks = (firstDay.getDay() + 6) % 7;
  const monthDays = Array.from({ length: daysInMonth }, (_, index) => {
    const date = new Date(year, month, index + 1);
    return {
      day: index + 1,
      date: toIsoDate(date),
    };
  });

  return {
    leadingBlanks,
    monthDays,
    monthKey: `${year}-${String(month + 1).padStart(2, "0")}`,
  };
}

function addDays(date: string, days: number) {
  return toIsoDate(addDaysToDate(parseIsoDate(date), days));
}

function addDaysToDate(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(date.getDate() + days);
  return next;
}

function addMonths(date: string, months: number) {
  const parsed = parseIsoDate(date);
  parsed.setMonth(parsed.getMonth() + months);
  return toIsoDate(parsed);
}

function parseIsoDate(date: string) {
  return new Date(`${date}T00:00:00`);
}

function toIsoDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatShortDate(date: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(parseIsoDate(date));
}

function findPatient(patients: BackendPatient[], patientId?: string) {
  return patients.find((patient) => patient.patientId === patientId) ?? getPatientById(patientId);
}

function findStaffProfile(profiles: BackendStaffProfile[], profileId?: string) {
  return profiles.find((profile) => profile.id === profileId) ?? getStaffProfileById(profileId);
}

function sortAppointments(appointments: BackendAppointment[]) {
  return [...appointments].sort((a, b) => `${a.date}T${a.time}`.localeCompare(`${b.date}T${b.time}`));
}

function handleAuthError(error: unknown, clearSession: (message?: string) => void) {
  if (isApiError(error) && error.status === 401) {
    clearSession("Your session has expired. Please sign in again.");
  }
}

function toAppointmentErrorMessage(error: unknown, fallback: string) {
  if (isApiError(error)) {
    if (error.status === 409) {
      return "This appointment was updated elsewhere. Please refresh and try again.";
    }

    const validationMessage = formatValidationErrors(error.validationErrors);
    if (validationMessage) {
      return validationMessage;
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

function formatValidationErrors(errors: Record<string, string[]> | undefined) {
  if (!errors) {
    return "";
  }

  return Object.entries(errors)
    .map(([field, messages]) => `${field}: ${messages.join(" ")}`)
    .join(" ");
}

function toWorkflowAction(status: AppointmentStatus): AppointmentWorkflowAction {
  const actions: Partial<Record<AppointmentStatus, AppointmentWorkflowAction>> = {
    Arrived: "arrive",
    "Checked-in": "check-in",
    Cancelled: "cancel",
    "No-show": "no-show",
    Postponed: "postpone",
    "Needs Reschedule": "mark-needs-reschedule",
  };
  const action = actions[status];
  if (!action) {
    throw new Error(`Unsupported appointment workflow status: ${status}.`);
  }
  return action;
}
