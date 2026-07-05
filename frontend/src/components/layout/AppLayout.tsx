import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { useCurrentUser } from "../../context/SessionContext";
import type { Role } from "../../types/models";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

interface AppLayoutProps {
  role: Role;
}

export function AppLayout({ role }: AppLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") return "light";
    return window.localStorage.getItem("dentalcare.theme") === "dark" ? "dark" : "light";
  });
  const currentUser = useCurrentUser();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("dentalcare.theme", theme);
  }, [theme]);

  return (
    <div className={`app-frame ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <Sidebar
        role={role}
        user={currentUser}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((value) => !value)}
      />
      <div className="app-body">
        <Topbar user={currentUser} theme={theme} onToggleTheme={() => setTheme((value) => value === "dark" ? "light" : "dark")} />
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
