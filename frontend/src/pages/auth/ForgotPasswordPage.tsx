import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { Mail, Stethoscope } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { routes } from "../../routes";

export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSent(true);
  };

  return (
    <main className="auth-page">
      <form className="auth-card stack" onSubmit={submit}>
        <div className="auth-logo">
          <span className="logo-mark"><Stethoscope size={22} /></span>
          <strong>DentalCare</strong>
        </div>
        <div>
          <h1 className="page-title">Reset your password</h1>
          <p className="page-subtitle">Enter your email to receive reset instructions.</p>
        </div>
        <Input label="Email" name="email" type="email" icon={<Mail size={18} />} placeholder="name@clinic.com" required />
        {sent && <div className="notice-card">If this email is registered, a password reset link will be sent.</div>}
        <Button type="submit">Send reset link</Button>
        <Link className="text-link center" to={routes.auth.login}>Back to login</Link>
      </form>
    </main>
  );
}
