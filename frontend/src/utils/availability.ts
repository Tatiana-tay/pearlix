import type { BackendAppointment, BackendAvailabilityException, BackendShift, BackendStaffProfile } from "../types/models";
import { timeToMinutes } from "./shifts";

export const blockingAppointmentStatuses = ["Scheduled", "Arrived", "Checked-in", "In Visit", "Needs Reschedule"] as const;
export const leaveAffectedStatuses = ["Scheduled", "Arrived", "Checked-in", "Needs Reschedule"] as const;

export function toDateTime(date: string, time: string) {
  return `${date}T${time}`;
}

export function datePart(dateTime: string) {
  return dateTime.slice(0, 10);
}

export function timePart(dateTime: string) {
  return dateTime.slice(11, 16);
}

export function appointmentStart(appointment: BackendAppointment) {
  return toDateTime(appointment.date, appointment.time);
}

export function appointmentEnd(appointment: BackendAppointment) {
  return addMinutes(appointmentStart(appointment), appointment.durationMinutes);
}

export function addMinutes(dateTime: string, minutes: number) {
  const date = new Date(dateTime);
  date.setMinutes(date.getMinutes() + minutes);
  return toLocalDateTime(date);
}

export function intervalsOverlap(startA: string, endA: string, startB: string, endB: string) {
  return new Date(startA).getTime() < new Date(endB).getTime() && new Date(endA).getTime() > new Date(startB).getTime();
}

export function isBlockingAppointment(appointment: BackendAppointment) {
  return blockingAppointmentStatuses.includes(appointment.status as (typeof blockingAppointmentStatuses)[number]);
}

export function isLeaveAffectedAppointment(appointment: BackendAppointment) {
  return leaveAffectedStatuses.includes(appointment.status as (typeof leaveAffectedStatuses)[number]);
}

export function detectAffectedAppointments(exception: BackendAvailabilityException, appointments: BackendAppointment[]) {
  if (exception.userRole !== "Doctor" || exception.status !== "Active") {
    return [];
  }

  return appointments.filter((appointment) =>
    appointment.doctorId === exception.userId &&
    isLeaveAffectedAppointment(appointment) &&
    intervalsOverlap(appointmentStart(appointment), appointmentEnd(appointment), exception.startDateTime, exception.endDateTime),
  );
}

export function hasOverlappingException(exception: BackendAvailabilityException, exceptions: BackendAvailabilityException[]) {
  return exceptions.some((item) =>
    item.status === "Active" &&
    item.userId === exception.userId &&
    item.exceptionId !== exception.exceptionId &&
    intervalsOverlap(item.startDateTime, item.endDateTime, exception.startDateTime, exception.endDateTime),
  );
}

export function isDoctorAvailableForInterval({
  doctorId,
  date,
  time,
  durationMinutes,
  appointments,
  shifts,
  exceptions,
  dayOfWeek,
  ignoreAppointmentId,
}: {
  doctorId: string;
  date: string;
  time: string;
  durationMinutes: number;
  appointments: BackendAppointment[];
  shifts: BackendShift[];
  exceptions: BackendAvailabilityException[];
  dayOfWeek: string;
  ignoreAppointmentId?: string;
}) {
  const start = toDateTime(date, time);
  const end = addMinutes(start, durationMinutes);
  const startMinutes = timeToMinutes(time);
  const endMinutes = startMinutes + durationMinutes;
  const doctorShifts = shifts.filter((shift) => shift.staffOrDoctorId === doctorId && shift.dayOfWeek === dayOfWeek && !shift.isOnLeave);
  const insideShift = doctorShifts.some((shift) => timeToMinutes(shift.startTime) <= startMinutes && timeToMinutes(shift.endTime) >= endMinutes);

  if (!insideShift) return false;

  const blockedByLeave = exceptions.some((exception) =>
    exception.userId === doctorId &&
    exception.userRole === "Doctor" &&
    exception.status === "Active" &&
    intervalsOverlap(start, end, exception.startDateTime, exception.endDateTime),
  );

  if (blockedByLeave) return false;

  return !appointments.some((appointment) =>
    appointment.id !== ignoreAppointmentId &&
    appointment.doctorId === doctorId &&
    appointment.date === date &&
    isBlockingAppointment(appointment) &&
    intervalsOverlap(start, end, appointmentStart(appointment), appointmentEnd(appointment)),
  );
}

export function getAvailableDoctorsForSlot({
  date,
  time,
  durationMinutes,
  appointments,
  shifts,
  exceptions,
  staffProfiles,
}: {
  date: string;
  time: string;
  durationMinutes: number;
  appointments: BackendAppointment[];
  shifts: BackendShift[];
  exceptions: BackendAvailabilityException[];
  staffProfiles: BackendStaffProfile[];
}) {
  const dayOfWeek = new Intl.DateTimeFormat("en-US", { weekday: "long" }).format(new Date(`${date}T00:00:00`));
  return staffProfiles.filter((profile) =>
    profile.role === "Doctor" &&
    profile.status === "Active" &&
    isDoctorAvailableForInterval({
      doctorId: profile.id,
      date,
      time,
      durationMinutes,
      appointments,
      shifts,
      exceptions,
      dayOfWeek,
    }),
  );
}

export function toLocalDateTime(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}T${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
