import { BadgeDollarSign, CalendarDays, Settings, UserCog, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card } from "../../components/ui/Card";
import { StatCard } from "../../components/ui/StatCard";
import { staffProfiles } from "../../data/adapters";
import { mockInvoices } from "../../data/mockInvoices";
import { mockUsers } from "../../data/mockUsers";
import { routes } from "../../routes";
import { loadMockAppointments } from "../../utils/mockScheduleState";

export function AdminDashboardPage() {
  const activeUsers = mockUsers.filter((user) => user.status === "Active").length;
  const doctorsCount = staffProfiles.filter((profile) => profile.role === "Doctor").length;
  const staffCount = staffProfiles.filter((profile) => profile.role === "Staff").length;
  const pendingInvoices = mockInvoices.filter((invoice) => invoice.status === "Pending" || invoice.status === "Partially Paid").length;
  const todayAppointments = loadMockAppointments().filter((appointment) => appointment.date === "2026-02-09").length;

  return (
    <div className="page-shell">
      <PageHeader title="Admin Dashboard" subtitle="Operational overview for users, appointments, and clinic setup." />
      <div className="grid grid-4">
        <StatCard label="Active Users" value={activeUsers} icon={<Users size={22} />} />
        <StatCard label="Doctors" value={doctorsCount} icon={<UserCog size={22} />} />
        <StatCard label="Staff" value={staffCount} icon={<Users size={22} />} />
        <StatCard label="Pending Invoices" value={pendingInvoices} icon={<BadgeDollarSign size={22} />} />
      </div>
      <div className="grid grid-4 action-grid">
        {[
          { label: "Manage Users", icon: Users, to: routes.admin.users, description: "Create, edit, deactivate, and reset user access." },
          { label: "Doctors/Staff", icon: UserCog, to: routes.admin.doctorsStaff, description: `${staffProfiles.length} team profiles with shifts.` },
          { label: "Appointments", icon: CalendarDays, to: routes.admin.appointments, description: `${todayAppointments} appointments scheduled today.` },
          { label: "Settings", icon: Settings, to: routes.admin.settings, description: "Clinic profile and system preferences." },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Link to={item.to} key={item.label}>
              <Card className="action-card">
                <span className="stat-icon"><Icon size={22} /></span>
                <h2 className="card-title">{item.label}</h2>
                <p className="muted">{item.description}</p>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
