import { useEffect, useMemo, useState } from "react";
import { FileUp, Save, Trash2, UserRound } from "lucide-react";
import { XrayViewer } from "../../components/ai/XrayViewer";
import { PageHeader } from "../../components/layout/PageHeader";
import { PatientProfileDrawer } from "../../components/patients/PatientProfileDrawer";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Tabs } from "../../components/ui/Tabs";
import { Textarea } from "../../components/ui/Textarea";
import { useCurrentUser } from "../../context/SessionContext";
import { getAIFindingsByAnalysisId } from "../../data/adapters";
import type { BackendAIResult, BackendAppointment, BackendAttachment, BackendInvoice, BackendVisit } from "../../types/models";
import { ageFromDate, fullPatientName, initials } from "../../utils/format";
import {
  getMockStaffProfileForUser,
  loadActiveVisitAppointmentId,
  loadMockAIResults,
  loadMockAttachments,
  loadMockInvoices,
  loadMockPatients,
  loadMockStaffProfiles,
  loadMockVisits,
  saveMockAIResults,
  saveMockAttachments,
  saveMockInvoices,
  saveMockVisits,
} from "../../utils/mockClinicState";
import { loadMockAppointments, saveMockAppointments } from "../../utils/mockScheduleState";

const maxXrayBytes = 10 * 1024 * 1024;
const acceptedXrayTypes = ["image/png", "image/jpeg", "application/dicom"];

export function ActiveVisitPage() {
  const currentUser = useCurrentUser();
  const [activeTab, setActiveTab] = useState("notes");
  const [profileOpen, setProfileOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [appointments, setAppointments] = useState<BackendAppointment[]>(loadMockAppointments);
  const [visits, setVisits] = useState<BackendVisit[]>(loadMockVisits);
  const [attachments, setAttachments] = useState<BackendAttachment[]>(loadMockAttachments);
  const [aiResults, setAiResults] = useState<BackendAIResult[]>(loadMockAIResults);
  const [invoices, setInvoices] = useState<BackendInvoice[]>(loadMockInvoices);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [visitMessage, setVisitMessage] = useState("");
  const [xrayMessage, setXrayMessage] = useState("");
  const [billingMessage, setBillingMessage] = useState("");
  const [notes, setNotes] = useState({
    symptomsChiefComplaint: "",
    clinicalNotes: "",
    diagnosisNotes: "",
    treatmentNotes: "",
  });

  const staffProfiles = useMemo(loadMockStaffProfiles, []);
  const patientRows = useMemo(loadMockPatients, []);
  const doctorProfile = getMockStaffProfileForUser(currentUser, staffProfiles);
  const activeAppointmentId = loadActiveVisitAppointmentId();
  const appointment = findActiveAppointment(appointments, doctorProfile?.id, activeAppointmentId);
  const visit = findOrCreateVisit(visits, appointment, doctorProfile?.id);
  const patient = patientRows.find((item) => item.patientId === visit.patientId);
  const doctor = staffProfiles.find((item) => item.id === visit.doctorId) ?? doctorProfile;
  const visitAttachments = attachments.filter((attachment) => attachment.visitId === visit.id);
  const latestAttachment = visitAttachments[visitAttachments.length - 1];
  const latestAiResult = latestAttachment
    ? aiResults.find((result) => result.fileId === latestAttachment.id) ?? aiResults.find((result) => result.fileId === "FILE-001")
    : aiResults.find((result) => result.fileId === "FILE-001");
  const findings = latestAiResult ? getAIFindingsByAnalysisId(latestAiResult.analysisId) : [];

  useEffect(() => {
    setNotes({
      symptomsChiefComplaint: visit.symptomsChiefComplaint,
      clinicalNotes: visit.clinicalNotes,
      diagnosisNotes: visit.diagnosisNotes,
      treatmentNotes: visit.treatmentNotes,
    });
    setVisitMessage("");
    setBillingMessage("");
  }, [visit.id]);

  const persistVisit = (updates: Partial<BackendVisit>, message: string) => {
    const updatedVisit = { ...visit, ...updates };
    const exists = visits.some((item) => item.id === updatedVisit.id);
    const nextVisits = exists ? visits.map((item) => item.id === updatedVisit.id ? updatedVisit : item) : [...visits, updatedVisit];
    setVisits(nextVisits);
    saveMockVisits(nextVisits);
    setVisitMessage(message);
  };

  const saveNotes = (status: BackendVisit["status"], message: string) => {
    persistVisit({ ...notes, status }, message);
  };

  const completeVisit = () => {
    saveNotes("Completed", "Visit notes completed.");
    if (!appointment) return;
    const updatedAppointment = { ...appointment, status: "Completed" as const };
    const nextAppointments = appointments.map((item) => item.id === appointment.id ? updatedAppointment : item);
    setAppointments(nextAppointments);
    saveMockAppointments(nextAppointments);
  };

  const addMockXray = () => {
    setXrayMessage("");
    if (!selectedFile) {
      setXrayMessage("Choose a PNG, JPG, JPEG, or DICOM placeholder file first.");
      return;
    }
    const isDicomByName = selectedFile.name.toLowerCase().endsWith(".dcm");
    const supportedType = acceptedXrayTypes.includes(selectedFile.type) || isDicomByName;
    if (!supportedType) {
      setXrayMessage("Unsupported file type. Use PNG, JPG, JPEG, or DICOM placeholder files.");
      return;
    }
    if (selectedFile.size > maxXrayBytes) {
      setXrayMessage("File is too large for the frontend demo. Keep mock X-rays under 10 MB.");
      return;
    }
    const nextAttachment: BackendAttachment = {
      id: `FILE-${Date.now()}`,
      patientId: visit.patientId,
      visitId: visit.id,
      filePath: `mock://${selectedFile.name}`,
      fileName: selectedFile.name,
      fileType: selectedFile.type || "application/dicom",
      uploadedBy: doctor?.id ?? currentUser.id,
      uploadedAt: new Date().toISOString().slice(0, 10),
    };
    const nextAttachments = [...attachments, nextAttachment];
    setAttachments(nextAttachments);
    saveMockAttachments(nextAttachments);
    setSelectedFile(null);
    setUploadOpen(false);
    setXrayMessage(`${nextAttachment.fileName} uploaded to this visit in mock state.`);
  };

  const runAiAnalysis = (attachment = latestAttachment) => {
    if (!attachment) {
      setXrayMessage("Upload an X-ray before running AI analysis.");
      return;
    }
    const existing = aiResults.find((result) => result.fileId === attachment.id);
    const completedResult: BackendAIResult = {
      analysisId: existing?.analysisId ?? `AI-${Date.now()}`,
      fileId: attachment.id,
      resultSummary: "Assistive review completed. Doctor review is required before clinical use.",
      overallConfidence: 0.84,
      processedDate: new Date().toISOString().slice(0, 10),
      modelVersion: "DentalVision-R 0.8",
      status: "Completed",
      overlayFilePath: `mock-overlay://${attachment.fileName}`,
    };
    const nextResults = existing
      ? aiResults.map((result) => result.analysisId === existing.analysisId ? completedResult : result)
      : [...aiResults, completedResult];
    setAiResults(nextResults);
    saveMockAIResults(nextResults);
    setXrayMessage("AI analysis completed in mock state and is ready for doctor review.");
  };

  const deleteMockUpload = (upload: BackendAttachment) => {
    if (!window.confirm(`Delete ${upload.fileName}? This removes the local mock X-ray from this visit.`)) {
      return;
    }
    const nextAttachments = attachments.filter((item) => item.id !== upload.id);
    setAttachments(nextAttachments);
    saveMockAttachments(nextAttachments);
    setXrayMessage(`${upload.fileName} removed from this visit.`);
  };

  const sendToBilling = () => {
    if (invoices.some((invoice) => invoice.visitId === visit.id)) {
      setBillingMessage("This visit already has a linked invoice in the frontend demo.");
      return;
    }
    const nextInvoice: BackendInvoice = {
      id: `INV-${new Date().getFullYear()}-${String(invoices.length + 1).padStart(3, "0")}`,
      visitId: visit.id,
      patientId: visit.patientId,
      doctorId: visit.doctorId,
      invoiceDate: new Date().toISOString().slice(0, 10),
      totalAmount: appointment?.due && appointment.due > 0 ? appointment.due : 250,
      paidAmount: 0,
      balance: appointment?.due && appointment.due > 0 ? appointment.due : 250,
      status: "Pending",
    };
    const nextInvoices = [...invoices, nextInvoice];
    saveMockInvoices(nextInvoices);
    setInvoices(loadMockInvoices());
    setBillingMessage(`Invoice ${nextInvoice.id} created for staff billing. Doctors cannot process payment here.`);
  };

  const tabs = [
    {
      id: "notes",
      label: "Visit Notes",
      content: (
        <Card>
          <div className="stack">
            {visitMessage && <div className="notice-card">{visitMessage}</div>}
            <Textarea label="Symptoms / Chief Complaint" value={notes.symptomsChiefComplaint} onChange={(event) => setNotes((current) => ({ ...current, symptomsChiefComplaint: event.target.value }))} />
            <Textarea label="Clinical Notes" value={notes.clinicalNotes} onChange={(event) => setNotes((current) => ({ ...current, clinicalNotes: event.target.value }))} />
            <Textarea label="Diagnosis Notes" value={notes.diagnosisNotes} onChange={(event) => setNotes((current) => ({ ...current, diagnosisNotes: event.target.value }))} />
            <Textarea label="Treatment Notes" value={notes.treatmentNotes} onChange={(event) => setNotes((current) => ({ ...current, treatmentNotes: event.target.value }))} />
            <div className="right">
              <Button variant="secondary" icon={<Save size={17} />} onClick={() => saveNotes("Active", "Draft saved locally.")}>Save draft</Button>
              <Button variant="secondary" onClick={() => saveNotes("Pending Notes", "Notes saved locally and marked pending review.")}>Save notes</Button>
              <Button onClick={completeVisit}>Complete visit notes</Button>
            </div>
          </div>
        </Card>
      ),
    },
    {
      id: "xray",
      label: "X-rays & AI",
      content: (
        <div className="stack">
          <div className="right">
            <Button variant="secondary" icon={<FileUp size={17} />} onClick={() => setUploadOpen((value) => !value)}>Upload X-ray</Button>
            <Button onClick={() => runAiAnalysis()}>Run AI Analysis</Button>
          </div>
          {xrayMessage && <div className={xrayMessage.includes("Unsupported") || xrayMessage.includes("Choose") || xrayMessage.includes("large") || xrayMessage.includes("Upload") ? "alert-card" : "notice-card"}>{xrayMessage}</div>}
          {uploadOpen && (
            <Card>
              <div className="upload-card">
                <span className="stat-icon"><FileUp size={22} /></span>
                <div>
                  <h2 className="card-title">Mock X-ray Upload</h2>
                  <p className="muted">Supported: PNG, JPG, JPEG, or DICOM placeholder files under 10 MB.</p>
                  <input type="file" accept=".png,.jpg,.jpeg,.dcm,image/png,image/jpeg" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
                  <p className="tiny">Selected file: {selectedFile?.name ?? "None"}</p>
                  <div className="notice-card">Mock upload only. File metadata is stored locally for this frontend demo.</div>
                </div>
                <Button onClick={addMockXray}>Add Mock Upload</Button>
              </div>
            </Card>
          )}
          {visitAttachments.map((attachment) => (
            <Card className="soft-panel between" key={attachment.id}>
              <div>
                <h3 className="card-title">{attachment.fileName}</h3>
                <p className="tiny">{attachment.fileType} - {attachment.uploadedAt}</p>
              </div>
              <div className="right">
                <Badge tone="primary">Uploaded</Badge>
                <Button variant="danger" icon={<Trash2 size={16} />} onClick={() => deleteMockUpload(attachment)}>Delete X-ray</Button>
              </div>
            </Card>
          ))}
          {latestAiResult && <XrayViewer result={latestAiResult} findings={findings} attachment={latestAttachment} onRetryAnalysis={() => runAiAnalysis(latestAttachment)} />}
          <Card>
            <Textarea label="Doctor review notes" placeholder="Document your review of the assistive educational/research output." />
          </Card>
        </div>
      ),
    },
    {
      id: "billing",
      label: "Billing / Closure",
      content: (
        <Card>
          <div className="stack">
            {billingMessage && <div className="notice-card">{billingMessage}</div>}
            <section className="soft-panel">
              <h2 className="card-title">Treatment notes</h2>
              <p className="muted">{notes.treatmentNotes || visit.treatmentNotes}</p>
            </section>
            <div className="right">
              <Button variant="secondary" onClick={completeVisit}>Mark visit completed</Button>
              <Button onClick={sendToBilling}>Send to billing / create invoice</Button>
            </div>
            <div className="notice-card">Doctors can create the invoice handoff, but payment processing stays in the Staff Billing module.</div>
          </div>
        </Card>
      ),
    },
  ];

  return (
    <div className="page-shell">
      <PageHeader
        title="Active Visit"
        subtitle={`${patient ? fullPatientName(patient) : visit.patientId} - ${doctor?.fullName ?? visit.doctorId}${appointment ? ` - ${appointment.date} ${appointment.time}` : ""}`}
        actions={<Badge tone="primary">{visit.status}</Badge>}
      />
      {patient && (
        <Card className="patient-summary-card clickable" onClick={() => setProfileOpen(true)}>
          <div className="row">
            <span className="avatar">{initials(fullPatientName(patient))}</span>
            <div>
              <h2 className="card-title">{fullPatientName(patient)}</h2>
              <p className="tiny">{patient.gender} - {ageFromDate(patient.dateOfBirth)} years - Blood group {patient.bloodGroup || "not set"}</p>
            </div>
          </div>
          <div className="patient-summary-details">
            <span><UserRound size={16} /> {patient.patientId}</span>
            <span>{patient.phoneNumber}</span>
            <span>{visit.symptomsChiefComplaint}</span>
          </div>
          <Button
            variant="secondary"
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setProfileOpen(true);
            }}
          >
            Open Patient Profile
          </Button>
        </Card>
      )}
      <Tabs tabs={tabs} activeId={activeTab} onChange={setActiveTab} />
      <PatientProfileDrawer open={profileOpen} onClose={() => setProfileOpen(false)} patient={patient ?? null} canEdit={false} readOnlyBilling />
    </div>
  );
}

function findActiveAppointment(appointments: BackendAppointment[], doctorId?: string, activeAppointmentId?: string | null) {
  return appointments.find((appointment) => appointment.id === activeAppointmentId)
    ?? appointments.find((appointment) => appointment.doctorId === doctorId && appointment.status === "In Visit")
    ?? appointments.find((appointment) => appointment.doctorId === doctorId && appointment.status === "Checked-in")
    ?? appointments.find((appointment) => appointment.doctorId === doctorId)
    ?? appointments[0];
}

function findOrCreateVisit(visits: BackendVisit[], appointment?: BackendAppointment, doctorId?: string): BackendVisit {
  const existing = appointment
    ? visits.find((visit) => visit.appointmentId === appointment.id)
    : visits.find((visit) => visit.doctorId === doctorId && visit.status === "Active");
  if (existing) return existing;

  const fallbackAppointment = appointment ?? {
    id: "APT-DEMO",
    patientId: "PT-1044",
    doctorId: doctorId ?? "DOC-001",
    date: new Date().toISOString().slice(0, 10),
    status: "In Visit",
    visitType: "Routine Checkup",
    time: "09:00",
    durationMinutes: 30,
    due: 250,
    notes: "",
  };

  return {
    id: `VIS-${fallbackAppointment.id}`,
    appointmentId: fallbackAppointment.id,
    patientId: fallbackAppointment.patientId,
    doctorId: fallbackAppointment.doctorId,
    visitDate: fallbackAppointment.date,
    symptomsChiefComplaint: fallbackAppointment.notes || fallbackAppointment.visitType,
    clinicalNotes: "",
    diagnosisNotes: "",
    treatmentNotes: "",
    status: "Active",
  };
}
