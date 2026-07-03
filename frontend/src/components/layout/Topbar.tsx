import { Moon, Sun } from "lucide-react";
import type { User } from "../../types/models";

interface TopbarProps {
  user: User;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

export function Topbar({ user, theme, onToggleTheme }: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-identity" aria-label={`Current user: ${user.fullName}, ${user.role}`}>
        <strong>{user.fullName}</strong>
        <span>{user.role}</span>
      </div>
      <button
        className="icon-button theme-toggle"
        type="button"
        onClick={onToggleTheme}
        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        title={theme === "dark" ? "Light mode" : "Dark mode"}
      >
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </button>
    </header>
  );
}
