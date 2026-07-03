import { Clock, UserRound } from "lucide-react";
import { getPatientById, getStaffProfileById } from "../../data/adapters";
import type { BackendAppointment } from "../../types/models";
import { fullPatientName } from "../../utils/format";
import { timePresetOptions } from "../../utils/shifts";
import { appointmentStatusTone, appointmentStatusVisual } from "../../utils/statusStyles";
import { Badge } from "../ui/Badge";

interface AppointmentCalendarProps {
  appointments: BackendAppointment[];
  onAppointmentClick: (appointment: BackendAppointment) => void;
  onSlotClick: (time: string) => void;
  canCreate?: boolean;
  isSlotAvailable?: (time: string) => boolean;
}

export function AppointmentCalendar({ appointments, onAppointmentClick, onSlotClick, canCreate = true, isSlotAvailable = () => true }: AppointmentCalendarProps) {
  return (
    <div className="schedule-list">
      {timePresetOptions.map((slot) => {
        const slotAppointments = appointments.filter((item) => item.time === slot);
        const slotAvailable = isSlotAvailable(slot);

        return (
          <div className="schedule-row" key={slot}>
            <time>{slot}</time>
            {slotAppointments.length > 0 ? (
              <div className="schedule-slot-stack">
                {slotAppointments.map((appointment) => {
                  const patient = getPatientById(appointment.patientId);
                  const doctor = getStaffProfileById(appointment.doctorId);
                  const visual = appointmentStatusVisual[appointment.status];
                  return (
                    <button
                      className="appointment-block"
                      type="button"
                      key={appointment.id}
                      style={{
                        borderLeftColor: visual.accent,
                        background: visual.background,
                      }}
                      onClick={() => onAppointmentClick(appointment)}
                    >
                      <div>
                        <strong>{patient ? fullPatientName(patient) : appointment.patientId}</strong>
                        <span>{appointment.visitType}</span>
                        <small>
                          <UserRound size={13} /> {doctor?.fullName} <Clock size={13} /> {appointment.durationMinutes} min
                        </small>
                      </div>
                      <Badge tone={appointmentStatusTone[appointment.status]}>{appointment.status}</Badge>
                    </button>
                  );
                })}
              </div>
            ) : (
              <button className="available-slot" type="button" disabled={!canCreate || !slotAvailable} onClick={() => onSlotClick(slot)}>
                {slotAvailable ? "Available" : "No doctor available"}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
