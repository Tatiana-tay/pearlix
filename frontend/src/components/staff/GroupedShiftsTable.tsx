import type { BackendShift } from "../../types/models";
import { shiftDays, sortShifts } from "../../utils/shifts";

interface GroupedShiftsTableProps {
  shifts: BackendShift[];
}

const preferredShiftOrder = new Map([
  ["morning", 1],
  ["evening", 2],
  ["night", 3],
]);

const weekdayLabels: Record<string, string> = {
  Monday: "Mon",
  Tuesday: "Tue",
  Wednesday: "Wed",
  Thursday: "Thu",
  Friday: "Fri",
  Saturday: "Sat",
  Sunday: "Sun",
};

export function GroupedShiftsTable({ shifts }: GroupedShiftsTableProps) {
  const sorted = sortShifts(shifts);
  const rowLabels = Array.from(new Set(sorted.map((shift) => shift.shiftName))).sort((first, second) => {
    const firstOrder = preferredShiftOrder.get(first.toLowerCase()) ?? 50;
    const secondOrder = preferredShiftOrder.get(second.toLowerCase()) ?? 50;
    if (firstOrder !== secondOrder) return firstOrder - secondOrder;

    const firstShift = sorted.find((shift) => shift.shiftName === first);
    const secondShift = sorted.find((shift) => shift.shiftName === second);
    return (firstShift?.shiftIndex ?? 99) - (secondShift?.shiftIndex ?? 99) || first.localeCompare(second);
  });

  if (rowLabels.length === 0) {
    return <div className="empty-inline">No shifts have been assigned yet.</div>;
  }

  return (
    <div className="schedule-matrix-wrap">
      <table className="schedule-matrix">
        <thead>
          <tr>
            <th>Shift</th>
            {shiftDays.map((day) => <th key={day}>{weekdayLabels[day] ?? day}</th>)}
          </tr>
        </thead>
        <tbody>
          {rowLabels.map((label) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              {shiftDays.map((day) => {
                const dayShifts = sorted.filter((shift) => shift.dayOfWeek === day && shift.shiftName === label);
                return (
                  <td key={day}>
                    {dayShifts.length === 0 ? (
                      <span className="muted">Off</span>
                    ) : (
                      dayShifts.map((shift) => (
                        <span className={shift.isActive === false ? "schedule-off" : undefined} key={shift.id}>
                          {shift.isActive === false ? "Off" : `${shift.startTime}-${shift.endTime}`}
                        </span>
                      ))
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
