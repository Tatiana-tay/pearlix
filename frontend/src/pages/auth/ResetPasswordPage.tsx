import { FormEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Stethoscope } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { routes } from "../../routes";

type TokenState = "valid" | "expired" | "used" | "success";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const [submitted, setSubmitted] = useState(false);
  const [passwords, setPasswords] = useState({ next: "", confirm: "" });
  const [error, setError] = useState("");
  const tokenState = useMemo<TokenState>(() => {
    const state = searchParams.get("state");
    if (state === "expired" || state === "used") {
      return state;
    }
    return submitted ? "success" : "valid";
  }, [searchParams, submitted]);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    if (!passwords.next || !passwords.confirm) {
      setError("Enter and confirm your new password.");
      return;
    }
    if (passwords.next !== passwords.confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitted(true);
  };

  const stateMessages: Partial<Record<TokenState, string>> = {
    expired: "This reset link has expired. Please request a new password reset link.",
    used: "This reset link has already been used. Please request a new password reset link.",
    success: "Your password has been updated successfully. You can now sign in.",
  };
  const stateMessage = stateMessages[tokenState];

  return (
    <main className="auth-page">
      <form className="auth-card stack" onSubmit={submit}>
        <div className="auth-logo">
          <span className="logo-mark"><Stethoscope size={22} /></span>
          <strong>DentalCare</strong>
        </div>
        <div>
          <h1 className="page-title">Create a new password</h1>
          <p className="page-subtitle">Enter and confirm your new password.</p>
        </div>

        {tokenState === "valid" && (
          <>
            <Input
              label="New password"
              type="password"
              name="new-password"
              autoComplete="new-password"
              required
              value={passwords.next}
              onChange={(event) => setPasswords((current) => ({ ...current, next: event.target.value }))}
            />
            <Input
              label="Confirm password"
              type="password"
              name="confirm-password"
              autoComplete="new-password"
              required
              value={passwords.confirm}
              onChange={(event) => setPasswords((current) => ({ ...current, confirm: event.target.value }))}
            />
            {error && <div className="alert-card">{error}</div>}
            <Button type="submit">Update password</Button>
          </>
        )}

        {stateMessage && (
          <div className={tokenState === "success" ? "notice-card" : "alert-card"}>
            {stateMessage}
          </div>
        )}

        {(tokenState === "expired" || tokenState === "used") && (
          <Link className="text-link center" to={routes.auth.forgotPassword}>Request a new reset link</Link>
        )}
        <Link className="text-link center" to={routes.auth.login}>Back to login</Link>
      </form>
    </main>
  );
}
