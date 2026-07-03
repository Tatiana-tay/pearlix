import { appointmentChangeLogs, appointments, availabilityExceptions } from "../data/adapters";
import type { BackendAppointment, BackendAppointmentChangeLog, BackendAvailabilityException } from "../types/models";

const appointmentStorageKey = "dentalcare.mock.appointments.v1";
const availabilityExceptionStorageKey = "dentalcare.mock.availabilityExceptions.v1";
const appointmentChangeLogStorageKey = "dentalcare.mock.appointmentChangeLogs.v1";

function loadRows<T>(key: string, fallback: T[]) {
  if (typeof window === "undefined") return fallback;

  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed as T[] : fallback;
  } catch {
    return fallback;
  }
}

function saveRows<T>(key: string, rows: T[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(rows));
}

export const loadMockAppointments = () =>
  loadRows<BackendAppointment>(appointmentStorageKey, appointments);

export const saveMockAppointments = (rows: BackendAppointment[]) =>
  saveRows(appointmentStorageKey, rows);

export const loadMockAvailabilityExceptions = () =>
  loadRows<BackendAvailabilityException>(availabilityExceptionStorageKey, availabilityExceptions);

export const saveMockAvailabilityExceptions = (rows: BackendAvailabilityException[]) =>
  saveRows(availabilityExceptionStorageKey, rows);

export const loadMockAppointmentChangeLogs = () =>
  loadRows<BackendAppointmentChangeLog>(appointmentChangeLogStorageKey, appointmentChangeLogs);

export const saveMockAppointmentChangeLogs = (rows: BackendAppointmentChangeLog[]) =>
  saveRows(appointmentChangeLogStorageKey, rows);
