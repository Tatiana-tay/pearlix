import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import {
  adaptVisitDTO,
  adaptVisitWorkflowResponse,
  completeVisit as completeVisitRequest,
  getActiveVisit,
  toVisitNotesPayload,
  updateVisitNotes,
} from "../../api/visits";
import { isApiError } from "../../api/errors";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Textarea } from "../../components/ui/Textarea";
import { useSession } from "../../context/SessionContext";
import type { BackendVisit } from "../../types/models";

const emptyNotes = {
  symptomsChiefComplaint: "",
  clinicalNotes: "",
  diagnosisNotes: "",
  treatmentNotes: "",
  generalNotes: "",
};

export function ActiveVisitPage() {
  const { accessToken, clearSession } = useSession();
  const [visit, setVisit] = useState<BackendVisit | null>(null);
  const [notes, setNotes] = useState(emptyNotes);
  const [loadingVisit, setLoadingVisit] = useState(true);
  const [pageError, setPageError] = useState("");
  const [visitMessage, setVisitMessage] = useState("");
  const [savingVisit, setSavingVisit] = useState(false);

  useEffect(() => {
    if (!accessToken) {
      setLoadingVisit(false);
      setPageError("Sign in again to view your active visit.");
      return;
    }

    let cancelled = false;
    setLoadingVisit(true);
    setPageError("");
    setVisitMessage("");

    getActiveVisit({ accessToken })
      .then((activeVisit) => {
        if (cancelled) return;
        const adaptedVisit = adaptVisitDTO(activeVisit);
        setVisit(adaptedVisit);
        setNotes(toNotes(adaptedVisit));
        setPageError("");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (isApiError(error) && error.status === 404) {
          setVisit(null);
          setPageError("");
          return;
        }
        handleAuthError(error, clearSession);
        setPageError(toVisitErrorMessage(error, "Unable to load active visit."));
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingVisit(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, clearSession]);

  const saveNotes = async () => {
    if (!visit || !accessToken) return;
    setSavingVisit(true);
    setPageError("");
    setVisitMessage("");
    try {
      const nextVisit = adaptVisitDTO(await updateVisitNotes(visit.id, toVisitNotesPayload({ ...visit, ...notes }), { accessToken }));
      setVisit(nextVisit);
      setNotes(toNotes(nextVisit));
      setVisitMessage("Visit notes saved.");
    } catch (error) {
      handleAuthError(error, clearSession);
      setPageError(toVisitErrorMessage(error, "Unable to save visit notes."));
    } finally {
      setSavingVisit(false);
    }
  };

  const completeVisit = async () => {
    if (!visit || !accessToken) return;
    setSavingVisit(true);
    setPageError("");
    setVisitMessage("");
    try {
      const { visit: completedVisit } = adaptVisitWorkflowResponse(
        await completeVisitRequest(visit.id, toVisitNotesPayload({ ...visit, ...notes }), { accessToken }),
      );
      setVisit(completedVisit);
      setNotes(toNotes(completedVisit));
      setVisitMessage("Visit completed.");
    } catch (error) {
      handleAuthError(error, clearSession);
      setPageError(toVisitErrorMessage(error, "Unable to complete visit."));
    } finally {
      setSavingVisit(false);
    }
  };

  return (
    <div className="page-shell">
      <PageHeader
        title="Active Visit"
        subtitle={visit ? `${visit.patientName || visit.patientId} - ${visit.doctorName || visit.doctorId}` : "No active visit"}
        actions={visit && <Badge tone={visit.status === "Active" ? "primary" : "green"}>{visit.status}</Badge>}
      />
      {pageError && <div className="alert-card">{pageError}</div>}
      {loadingVisit ? (
        <Card><div className="empty-inline">Loading active visit...</div></Card>
      ) : !visit ? (
        <Card><div className="empty-inline">No active visit. Start a checked-in appointment from My Appointments.</div></Card>
      ) : (
        <Card>
          <div className="stack">
            {visitMessage && <div className="notice-card">{visitMessage}</div>}
            <section className="soft-panel">
              <h2 className="card-title">Visit Details</h2>
              <dl className="detail-list mt-16">
                <div><dt>Patient</dt><dd>{visit.patientName || visit.patientId}</dd></div>
                <div><dt>Doctor</dt><dd>{visit.doctorName || visit.doctorId}</dd></div>
                <div><dt>Appointment</dt><dd>{visit.appointmentId}</dd></div>
                <div><dt>Started</dt><dd>{formatDateTime(visit.startedAt ?? visit.visitDate)}</dd></div>
              </dl>
            </section>
            <Textarea label="Subjective Notes" value={notes.symptomsChiefComplaint} disabled={visit.status !== "Active"} onChange={(event) => setNotes((current) => ({ ...current, symptomsChiefComplaint: event.target.value }))} />
            <Textarea label="Objective Notes" value={notes.clinicalNotes} disabled={visit.status !== "Active"} onChange={(event) => setNotes((current) => ({ ...current, clinicalNotes: event.target.value }))} />
            <Textarea label="Assessment Notes" value={notes.diagnosisNotes} disabled={visit.status !== "Active"} onChange={(event) => setNotes((current) => ({ ...current, diagnosisNotes: event.target.value }))} />
            <Textarea label="Plan Notes" value={notes.treatmentNotes} disabled={visit.status !== "Active"} onChange={(event) => setNotes((current) => ({ ...current, treatmentNotes: event.target.value }))} />
            <Textarea label="General Notes" value={notes.generalNotes} disabled={visit.status !== "Active"} onChange={(event) => setNotes((current) => ({ ...current, generalNotes: event.target.value }))} />
            {visit.status === "Active" && (
              <div className="right">
                <Button variant="secondary" icon={<Save size={17} />} disabled={savingVisit} onClick={() => { void saveNotes(); }}>
                  {savingVisit ? "Saving..." : "Save notes"}
                </Button>
                <Button disabled={savingVisit} onClick={() => { void completeVisit(); }}>
                  {savingVisit ? "Completing..." : "Complete visit"}
                </Button>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}

function toNotes(visit: BackendVisit) {
  return {
    symptomsChiefComplaint: visit.symptomsChiefComplaint,
    clinicalNotes: visit.clinicalNotes,
    diagnosisNotes: visit.diagnosisNotes,
    treatmentNotes: visit.treatmentNotes,
    generalNotes: visit.generalNotes ?? "",
  };
}

function formatDateTime(value: string) {
  return value ? value.replace("T", " ").replace("Z", "") : "Not set";
}

function handleAuthError(error: unknown, clearSession: (message?: string) => void) {
  if (isApiError(error) && error.status === 401) {
    clearSession("Your session has expired. Please sign in again.");
  }
}

function toVisitErrorMessage(error: unknown, fallback: string) {
  if (isApiError(error)) {
    if (error.status === 409) {
      return "This visit was updated elsewhere. Please refresh and try again.";
    }
    const validationMessage = formatValidationErrors(error.validationErrors);
    if (validationMessage) {
      return validationMessage;
    }
    return error.message || fallback;
  }
  if (error instanceof TypeError) {
    return "Cannot reach the backend. Make sure the backend server is running and try again.";
  }
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function formatValidationErrors(errors: Record<string, string[]> | undefined) {
  if (!errors) {
    return "";
  }
  return Object.entries(errors)
    .map(([field, messages]) => `${field}: ${messages.join(" ")}`)
    .join(" ");
}
