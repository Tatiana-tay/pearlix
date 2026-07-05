import type { BackendShift } from "../types/models";

export const shiftDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const timePresetOptions = [
  "07:00",
  "07:30",
  "08:00",
  "08:30",
  "09:00",
  "09:30",
  "10:00",
  "10:30",
  "11:00",
  "11:30",
  "12:00",
  "12:30",
  "13:00",
  "13:30",
  "14:00",
  "14:30",
  "15:00",
  "15:30",
  "16:00",
  "16:30",
  "17:00",
  "17:30",
  "18:00",
  "18:30",
  "19:00",
  "19:30",
  "20:00",
  "20:30",
  "21:00",
];
export const shiftTimeOptions = ["-", ...timePresetOptions];

const dayOrder = new Map(shiftDays.map((day, index) => [day, index]));

export function sortShifts(rows: BackendShift[]) {
  return [...rows].sort((first, second) => {
    const dayDifference = (dayOrder.get(first.dayOfWeek) ?? 99) - (dayOrder.get(second.dayOfWeek) ?? 99);
    if (dayDifference) return dayDifference;
    return first.shiftIndex - second.shiftIndex || timeToMinutes(first.startTime) - timeToMinutes(second.startTime);
  });
}

export function groupShiftsByDay(rows: BackendShift[]) {
  const groups = new Map<string, BackendShift[]>();
  sortShifts(rows).forEach((row) => {
    groups.set(row.dayOfWeek, [...(groups.get(row.dayOfWeek) ?? []), row]);
  });
  return Array.from(groups.entries()).map(([day, shifts]) => ({ day, shifts }));
}

export function createShift(staffOrDoctorId: string, existingRows: BackendShift[], dayOfWeek = "Monday"): BackendShift {
  const existingForDay = existingRows.filter((row) => row.dayOfWeek === dayOfWeek);
  const nextIndex = existingForDay.length + 1;
  return {
    id: `SHIFT-LOCAL-${staffOrDoctorId}-${Date.now()}-${nextIndex}`,
    staffOrDoctorId,
    dayOfWeek,
    shiftName: nextIndex === 1 ? "Morning" : nextIndex === 2 ? "Evening" : `Shift ${nextIndex}`,
    shiftIndex: nextIndex,
    startTime: nextIndex === 1 ? "09:00" : "14:00",
    endTime: nextIndex === 1 ? "13:00" : "18:00",
    isActive: true,
    isOnLeave: false,
  };
}

export function getShiftValidationMessage(rows: BackendShift[]) {
  const activeRows = rows.filter((row) => row.isActive !== false);
  for (const row of activeRows) {
    if (row.startTime === "-" || row.endTime === "-" || timeToMinutes(row.startTime) >= timeToMinutes(row.endTime)) {
      return "Each active shift must have a start time before its end time.";
    }
  }

  for (let index = 0; index < activeRows.length; index += 1) {
    for (let next = index + 1; next < activeRows.length; next += 1) {
      const first = activeRows[index];
      const second = activeRows[next];
      if (first.staffOrDoctorId === second.staffOrDoctorId && first.dayOfWeek === second.dayOfWeek) {
        const overlaps =
          timeToMinutes(first.startTime) < timeToMinutes(second.endTime) &&
          timeToMinutes(first.endTime) > timeToMinutes(second.startTime);
        if (overlaps) {
          return "Shifts for the same person cannot overlap on the same day.";
        }
      }
    }
  }

  return "";
}

export function timeToMinutes(value: string) {
  if (value === "-") return 0;
  const [hours, minutes] = value.split(":").map(Number);
  return (hours || 0) * 60 + (minutes || 0);
}
