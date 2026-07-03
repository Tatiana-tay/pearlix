import { NavLink, useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, LogOut, Stethoscope } from "lucide-react";
import { useSession } from "../../context/SessionContext";
import { navConfig } from "../../navigation/navConfig";
import { routes } from "../../routes";
import type { Role, User } from "../../types/models";

interface SidebarProps {
  role: Role;
  user: User;
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ role, collapsed, onToggle }: SidebarProps) {
  const navigate = useNavigate();
  const { logout } = useSession();

  const handleLogout = () => {
    logout();
    navigate(routes.auth.login);
  };

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-logo">
        <span className="logo-mark" aria-hidden="true">
          <Stethoscope size={21} />
        </span>
        <span className="sidebar-label">DentalCare</span>
        <button
          className="sidebar-toggle"
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={19} /> : <ChevronLeft size={19} />}
        </button>
      </div>
      <nav className="sidebar-nav" aria-label={`${role} navigation`}>
        {navConfig[role].map((item) => {
          const Icon = item.icon;
          return (
            <NavLink key={item.to} to={item.to} className="sidebar-link" title={item.label} aria-label={item.label}>
              <Icon size={20} />
              <span className="sidebar-label">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="sidebar-profile">
        <button className="sidebar-logout" type="button" onClick={handleLogout}>
          <LogOut size={17} />
          <span className="sidebar-label">Logout</span>
        </button>
      </div>
    </aside>
  );
}
