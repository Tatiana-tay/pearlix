import { PageHeader } from "../../components/layout/PageHeader";
import { Card } from "../../components/ui/Card";

export function DoctorPatientRecordsPage() {
  return (
    <div className="page-shell">
      <PageHeader title="Patients" subtitle="Patient record browsing is limited to visit context." />
      <Card>
        <div className="empty-inline">Global patient browsing is deferred for doctors. Open patient context from My Appointments or Active Visit.</div>
      </Card>
    </div>
  );
}
