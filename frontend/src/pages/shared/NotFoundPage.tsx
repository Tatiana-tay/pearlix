import { Link } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { useSession } from "../../context/SessionContext";
import { roleHome } from "../../navigation/navConfig";

export function NotFoundPage() {
  const { currentUser } = useSession();
  const targetRoute = currentUser ? roleHome[currentUser.role] : "/login";
  const buttonLabel = currentUser ? "Go to dashboard" : "Go to login";

  return (
    <main className="auth-page">
      <div className="auth-card">
        <EmptyState
          title="Page not found"
          description="The route is not part of the DentalCare prototype."
          action={<Link to={targetRoute}><Button>{buttonLabel}</Button></Link>}
        />
      </div>
    </main>
  );
}
