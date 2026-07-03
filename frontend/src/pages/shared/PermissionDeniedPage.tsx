import { Link } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { roleHome } from "../../navigation/navConfig";
import { useSession } from "../../context/SessionContext";

export function PermissionDeniedPage() {
  const { currentUser } = useSession();

  return (
    <main className="auth-page">
      <div className="auth-card">
        <EmptyState
          kind="permission"
          title="Permission denied"
          description="Your current mock role cannot access this route."
          action={
            <Link to={roleHome[currentUser.role]}>
              <Button>Go to my dashboard</Button>
            </Link>
          }
        />
      </div>
    </main>
  );
}
