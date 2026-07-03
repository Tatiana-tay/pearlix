import {
  Activity,
  BadgeDollarSign,
  CalendarDays,
  LayoutDashboard,
  Settings,
  Stethoscope,
  UserRound,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { routes } from "../routes";
import type { Role } from "../types/models";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
}

export const navConfig: Record<Role, NavItem[]> = {
  Admin: [
    { label: "Dashboard", to: routes.admin.dashboard, icon: LayoutDashboard },
    { label: "Users", to: routes.admin.users, icon: Users },
    { label: "Doctors/Staff", to: routes.admin.doctorsStaff, icon: Stethoscope },
    { label: "Appointments", to: routes.admin.appointments, icon: CalendarDays },
    { label: "Patients", to: routes.admin.patients, icon: UserRound },
    { label: "Billing", to: routes.admin.billing, icon: BadgeDollarSign },
    { label: "Settings", to: routes.admin.settings, icon: Settings },
  ],
  Staff: [
    { label: "Dashboard", to: routes.staff.dashboard, icon: LayoutDashboard },
    { label: "Appointments", to: routes.staff.appointments, icon: CalendarDays },
    { label: "Patients", to: routes.staff.patients, icon: UserRound },
    { label: "Billing", to: routes.staff.billing, icon: BadgeDollarSign },
    { label: "Doctors/Staff", to: routes.staff.doctorsStaff, icon: Stethoscope },
    { label: "Settings", to: routes.staff.profile, icon: Settings },
  ],
  Doctor: [
    { label: "Dashboard", to: routes.doctor.dashboard, icon: LayoutDashboard },
    { label: "My Appointments", to: routes.doctor.appointments, icon: CalendarDays },
    { label: "Patients", to: routes.doctor.patients, icon: UserRound },
    { label: "Active Visit", to: routes.doctor.activeVisit, icon: Activity },
    { label: "Profile / Settings", to: routes.doctor.profile, icon: Settings },
  ],
};

export const roleHome: Record<Role, string> = {
  Admin: routes.admin.dashboard,
  Staff: routes.staff.dashboard,
  Doctor: routes.doctor.dashboard,
};
