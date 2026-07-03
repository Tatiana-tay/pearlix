import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Stethoscope } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useSession } from "../../context/SessionContext";
import { routes } from "../../routes";
import type { Role } from "../../types/models";
import { loadMockUsers } from "../../utils/mockClinicState";

const dashboardByRole: Record<Role, string> = {
  Admin: routes.admin.dashboard,
  Doctor: routes.doctor.dashboard,
  Staff: routes.staff.dashboard,
};

export function LoginPage() {
  const navigate = useNavigate();
  const { demoUsers, loginAsRole, loginAsUser } = useSession();
  const [message, setMessage] = useState("");
  const [credentials, setCredentials] = useState({ username: "", password: "" });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = credentials.username.trim().toLowerCase();
    const password = credentials.password;

    if (!username || !password) {
      setMessage("Enter both username/email and password.");
      return;
    }

    const user = loadMockUsers().find((item) =>
      item.username.toLowerCase() === username || item.email.toLowerCase() === username,
    );

    if (!user || password !== "password") {
      setMessage("Invalid mock credentials. Try a listed demo role or use password.");
      return;
    }

    if (user.status !== "Active") {
      setMessage("This account is inactive. Contact an administrator to reactivate access.");
      return;
    }

    if (!dashboardByRole[user.role]) {
      setMessage("This account has no dashboard permission in the mock RBAC setup.");
      return;
    }

    if (user.mustChangePassword) {
      setMessage("This account must change password before continuing. Use the reset password flow.");
      return;
    }

    loginAsUser(user);
    navigate(dashboardByRole[user.role]);
  };

  const loginAs = (role: Role) => {
    const user = loginAsRole(role);
    navigate(dashboardByRole[user.role]);
  };

  return (
    <main className="auth-page">
      <form className="auth-card stack" onSubmit={submit}>
        <div className="auth-logo">
          <span className="logo-mark"><Stethoscope size={22} /></span>
          <strong>DentalCare</strong>
        </div>
        <div>
          <h1 className="page-title">Welcome back</h1>
          <p className="page-subtitle">Sign in to manage your clinic.</p>
        </div>
        <Input
          label="Username or email"
          name="username"
          placeholder="olivia.frontdesk"
          autoComplete="username"
          required
          value={credentials.username}
          onChange={(event) => setCredentials((current) => ({ ...current, username: event.target.value }))}
        />
        <Input
          label="Password"
          name="password"
          type="password"
          placeholder="Enter password"
          autoComplete="current-password"
          required
          value={credentials.password}
          onChange={(event) => setCredentials((current) => ({ ...current, password: event.target.value }))}
        />
        <div className="between">
          <label className="checkbox-line">
            <input type="checkbox" /> Remember me
          </label>
          <Link className="text-link" to={routes.auth.forgotPassword}>Forgot password?</Link>
        </div>
        {message && <div className="notice-card">{message}</div>}
        <Button type="submit">Login</Button>
        <div className="auth-demo">
          <span className="tiny">Demo access</span>
          <div className="auth-demo-grid">
            {demoUsers.map((demoUser) => (
              <Button key={demoUser.role} type="button" variant="secondary" onClick={() => loginAs(demoUser.role)}>
                Login as {demoUser.label}
              </Button>
            ))}
          </div>
        </div>
      </form>
    </main>
  );
}
