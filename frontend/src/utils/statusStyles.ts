import type { BadgeTone } from "../components/ui/Badge";
import type { AIResult, AppointmentStatus, DoctorProfile, Invoice, User } from "../types/models";

export const appointmentStatusTone: Record<AppointmentStatus, BadgeTone> = {
  Scheduled: "primary",
  Arrived: "secondary",
  "Checked-in": "purple",
  "In Visit": "indigo",
  Completed: "green",
  Cancelled: "danger",
  "No-show": "orange",
  Postponed: "warning",
  "Needs Reschedule": "orange",
};

export const invoiceStatusTone: Record<Invoice["status"], BadgeTone> = {
  Pending: "warning",
  "Partially Paid": "primary",
  Paid: "green",
  Cancelled: "danger",
};

export const aiStatusTone: Record<AIResult["Status"], BadgeTone> = {
  Pending: "warning",
  Processing: "indigo",
  Completed: "green",
  Failed: "danger",
};

export const userStatusTone: Record<User["status"] | DoctorProfile["Status"], BadgeTone> = {
  Active: "green",
  Inactive: "muted",
  "On Leave": "warning",
};

interface StatusVisual {
  accent: string;
  background: string;
  text: string;
}

export const appointmentStatusVisual: Record<AppointmentStatus, StatusVisual> = {
  Scheduled: { accent: "#2563eb", background: "rgba(37, 99, 235, 0.11)", text: "#1d4ed8" },
  Arrived: { accent: "#0891b2", background: "rgba(8, 145, 178, 0.12)", text: "#0e7490" },
  "Checked-in": { accent: "#9333ea", background: "rgba(147, 51, 234, 0.12)", text: "#7e22ce" },
  "In Visit": { accent: "#4338ca", background: "rgba(67, 56, 202, 0.14)", text: "#3730a3" },
  Completed: { accent: "#16a34a", background: "rgba(22, 163, 74, 0.12)", text: "#15803d" },
  Cancelled: { accent: "#e11d48", background: "rgba(225, 29, 72, 0.12)", text: "#be123c" },
  "No-show": { accent: "#f97316", background: "rgba(249, 115, 22, 0.13)", text: "#c2410c" },
  Postponed: { accent: "#d97706", background: "rgba(217, 119, 6, 0.14)", text: "#a16207" },
  "Needs Reschedule": { accent: "#f97316", background: "rgba(249, 115, 22, 0.16)", text: "#c2410c" },
};

export const invoiceStatusVisual: Record<Invoice["status"], StatusVisual> = {
  Pending: { accent: "#d97706", background: "rgba(217, 119, 6, 0.14)", text: "#a16207" },
  "Partially Paid": { accent: "#2563eb", background: "rgba(37, 99, 235, 0.11)", text: "#1d4ed8" },
  Paid: { accent: "#16a34a", background: "rgba(22, 163, 74, 0.12)", text: "#15803d" },
  Cancelled: { accent: "#e11d48", background: "rgba(225, 29, 72, 0.12)", text: "#be123c" },
};
