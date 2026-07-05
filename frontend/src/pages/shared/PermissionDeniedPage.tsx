import { Link } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { roleHome } from "../../navigation/navConfig";
import { useSession } from "../../context/SessionContext";

export function PermissionDeniedPage() {
  const { currentUser } = useSession();
  const targetRoute = currentUser ? roleHome[currentUser.role] : "/login";
  const buttonLabel = currentUser ? "Go to my dashboard" : "Go to login";

  return (
    <main className="auth-page">
      <div className="auth-card">
        <EmptyState
          kind="permission"
          title="Permission denied"
          description="Your current role cannot access this route."
          action={
            <Link to={targetRoute}>
              <Button>{buttonLabel}</Button>
            </Link>
          }
        />
      </div>
    </main>
  );
}
