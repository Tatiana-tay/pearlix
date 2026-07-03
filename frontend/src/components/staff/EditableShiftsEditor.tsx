import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { BackendShift } from "../../types/models";
import { createShift, groupShiftsByDay, shiftDays } from "../../utils/shifts";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { TimeInput } from "../ui/TimeInput";

interface EditableShiftsEditorProps {
  rows: BackendShift[];
  staffOrDoctorId: string;
  onRowsChange: (rows: BackendShift[]) => void;
}

export function EditableShiftsEditor({ rows, staffOrDoctorId, onRowsChange }: EditableShiftsEditorProps) {
  const [targetDay, setTargetDay] = useState("Monday");
  const groups = groupShiftsByDay(rows);

  const updateRow = (id: string, updates: Partial<BackendShift>) => {
    onRowsChange(rows.map((row) => row.id === id ? { ...row, ...updates } : row));
  };

  const removeRow = (id: string) => {
    onRowsChange(rows.filter((row) => row.id !== id));
  };

  return (
    <div className="stack">
      <div className="shift-editor-toolbar">
        <Select label="Add shift to day" options={shiftDays} value={targetDay} onChange={(event) => setTargetDay(event.target.value)} />
        <Button icon={<Plus size={17} />} type="button" onClick={() => onRowsChange([...rows, createShift(staffOrDoctorId, rows, targetDay)])}>
          Add Shift
        </Button>
      </div>
      <div className="compact-table compact-hours-table">
        <table className="data-table working-hours-table grouped-shifts-table">
          <thead>
            <tr>
              <th>Day</th>
              <th>Shift</th>
              <th>Start Time</th>
              <th>End Time</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {groups.flatMap(({ day, shifts }) =>
              shifts.map((row, index) => (
                <tr key={row.id}>
                  {index === 0 && <td rowSpan={shifts.length}><strong>{day}</strong></td>}
                  <td><Input value={row.shiftName} onChange={(event) => updateRow(row.id, { shiftName: event.target.value })} /></td>
                  <td><TimeInput aria-label={`${row.dayOfWeek} ${row.shiftName} start time`} value={row.startTime === "-" ? "" : row.startTime} disabled={row.isOnLeave} onChange={(event) => updateRow(row.id, { startTime: event.target.value || "-" })} /></td>
                  <td><TimeInput aria-label={`${row.dayOfWeek} ${row.shiftName} end time`} value={row.endTime === "-" ? "" : row.endTime} disabled={row.isOnLeave} onChange={(event) => updateRow(row.id, { endTime: event.target.value || "-" })} /></td>
                  <td>
                    <button
                      type="button"
                      className={`switch ${row.isOnLeave ? "active" : ""}`}
                      aria-label={`${row.dayOfWeek} ${row.shiftName} on leave`}
                      onClick={() => updateRow(row.id, { isOnLeave: !row.isOnLeave })}
                    />
                  </td>
                  <td>
                    <Button variant="ghost" type="button" icon={<Trash2 size={16} />} onClick={() => removeRow(row.id)}>Delete</Button>
                  </td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <div className="empty-inline">No shifts have been assigned yet.</div>}
    </div>
  );
}
