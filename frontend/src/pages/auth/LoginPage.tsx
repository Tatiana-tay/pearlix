import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Stethoscope } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useSession } from "../../context/SessionContext";
import { routes } from "../../routes";
import type { Role } from "../../types/models";

const dashboardByRole: Record<Role, string> = {
  Admin: routes.admin.dashboard,
  Doctor: routes.doctor.dashboard,
  Staff: routes.staff.dashboard,
};

export function LoginPage() {
  const navigate = useNavigate();
  const { authError, login } = useSession();
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [credentials, setCredentials] = useState({ username: "", password: "" });

  useEffect(() => {
    if (authError) {
      setMessage(authError);
    }
  }, [authError]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = credentials.username.trim().toLowerCase();
    const password = credentials.password;

    if (!username || !password) {
      setMessage("Enter both username/email and password.");
      return;
    }

    setMessage("");
    setSubmitting(true);
    try {
      const user = await login({ username, password });
      navigate(dashboardByRole[user.role], { replace: true });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to log in. Please try again.");
    } finally {
      setSubmitting(false);
    }
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
          placeholder="staff@example.com"
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
        <Button type="submit" disabled={submitting}>{submitting ? "Signing in..." : "Login"}</Button>
      </form>
    </main>
  );
}
