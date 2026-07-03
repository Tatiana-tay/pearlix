import { Link } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { useSession } from "../../context/SessionContext";
import { roleHome } from "../../navigation/navConfig";

export function NotFoundPage() {
  const { currentUser } = useSession();

  return (
    <main className="auth-page">
      <div className="auth-card">
        <EmptyState
          title="Page not found"
          description="The route is not part of the DentalCare prototype."
          action={<Link to={roleHome[currentUser.role]}><Button>Go to dashboard</Button></Link>}
        />
      </div>
    </main>
  );
}
