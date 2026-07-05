import { useEffect, useMemo, useState } from "react";
import { CalendarPlus, FileUp, Pencil, Save, Trash2 } from "lucide-react";
import { AppointmentModal } from "../appointments/AppointmentModal";
import { InvoiceDetails } from "../billing/InvoiceDetails";
import {
  getAIFindingsByAnalysisId,
  getAIResultByFileId,
  getAttachmentsForPatient,
  getStaffProfileById,
  getVisitsForPatient,
  invoices,
  patients,
} from "../../data/adapters";
import { useCurrentUser } from "../../context/SessionContext";
import type { BackendAIResult, BackendAIResultFinding, BackendAppointment, BackendAttachment, BackendInvoice, BackendPatient, BackendVisit, Invoice } from "../../types/models";
import { ageFromDate, currency, fullPatientName, initials, prettyDate } from "../../utils/format";
import { loadMockAppointments, loadMockAvailabilityExceptions, saveMockAppointments } from "../../utils/mockScheduleState";
import { aiStatusTone, appointmentStatusTone, invoiceStatusTone } from "../../utils/statusStyles";
import { AiFindingsTable } from "../ai/AiFindingsTable";
import { XrayViewer } from "../ai/XrayViewer";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Drawer } from "../ui/Drawer";
import { Modal } from "../ui/Modal";
import { Select } from "../ui/Select";
import { Tabs } from "../ui/Tabs";
import { Textarea } from "../ui/Textarea";
import { PatientForm } from "./PatientForm";

interface PatientProfileDrawerProps {
  open: boolean;
  onClose: () => void;
  patient: BackendPatient | null;
  canEdit?: boolean;
  readOnlyBilling?: boolean;
  onSavePatient?: (patient: BackendPatient) => void;
}

const blankPatient: BackendPatient = {
  patientId: "PT-NEW",
  firstName: "",
  lastName: "",
  nationalIdOrPassport: "",
  dateOfBirth: "1990-01-01",
  gender: "Female",
  phoneNumber: "",
  medicalConditionsHistory: "",
  bloodGroup: "",
  insuranceInfo: "",
  emergencyContact: "",
  address: "",
  createdAt: "2026-02-09",
  email: "",
};

export function PatientProfileDrawer({ open, onClose, patient, canEdit = true, readOnlyBilling = false, onSavePatient }: PatientProfileDrawerProps) {
  const currentUser = useCurrentUser();
  const [activeTab, setActiveTab] = useState("general");
  const [editMode, setEditMode] = useState(false);
  const [localPatient, setLocalPatient] = useState<BackendPatient>(patient ?? blankPatient);
  const [draftPatient, setDraftPatient] = useState<BackendPatient>(patient ?? blankPatient);
  const [localVisits, setLocalVisits] = useState<BackendVisit[]>([]);
  const [draftVisits, setDraftVisits] = useState<BackendVisit[]>([]);
  const [localInvoices, setLocalInvoices] = useState<BackendInvoice[]>([]);
  const [selectedInvoice, setSelectedInvoice] = useState<BackendInvoice | null>(null);
  const [lastInvoiceTap, setLastInvoiceTap] = useState<{ id: string; at: number } | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [mockUploads, setMockUploads] = useState<BackendAttachment[]>([]);
  const [deletedAttachmentIds, setDeletedAttachmentIds] = useState<string[]>([]);
  const [viewerPayload, setViewerPayload] = useState<{ result: BackendAIResult; findings: BackendAIResultFinding[] } | null>(null);
  const [appointmentRows, setAppointmentRows] = useState<BackendAppointment[]>(loadMockAppointments);
  const [appointmentCreateOpen, setAppointmentCreateOpen] = useState(false);
  const selectedPatient = editMode ? draftPatient : localPatient;
  const patientName = fullPatientName(selectedPatient) || "Patient";
  const canCreateAppointments = currentUser.role === "Staff";

  useEffect(() => {
    if (open) {
      setEditMode(false);
      setLocalPatient(patient ?? blankPatient);
      setDraftPatient(patient ?? blankPatient);
      setLocalVisits(getVisitsForPatient((patient ?? blankPatient).patientId));
      setDraftVisits(getVisitsForPatient((patient ?? blankPatient).patientId));
      setLocalInvoices(invoices.filter((invoice) => invoice.patientId === (patient ?? blankPatient).patientId));
      setSelectedInvoice(null);
      setUploadOpen(false);
      setViewerPayload(null);
      setAppointmentRows(loadMockAppointments());
      setAppointmentCreateOpen(false);
    }
  }, [open, patient?.patientId]);

  const patientVisits = editMode ? draftVisits : localVisits;
  const patientInvoices = localInvoices;
  const patientAppointments = useMemo(
    () => appointmentRows.filter((appointment) => appointment.patientId === selectedPatient.patientId),
    [appointmentRows, selectedPatient.patientId],
  );
  const patientOptions = useMemo(() => {
    const exists = patients.some((item) => item.patientId === selectedPatient.patientId);
    return exists ? patients : [...patients, selectedPatient];
  }, [selectedPatient]);
  const patientAttachments = useMemo(
    () => [
      ...getAttachmentsForPatient(selectedPatient.patientId),
      ...mockUploads.filter((attachment) => attachment.patientId === selectedPatient.patientId),
    ].filter((attachment) => !deletedAttachmentIds.includes(attachment.id)),
    [deletedAttachmentIds, mockUploads, selectedPatient.patientId],
  );

  const addMockUpload = () => {
    setMockUploads((current) => [
      ...current,
      {
        id: `FILE-MOCK-${current.length + 1}`,
        patientId: selectedPatient.patientId,
        visitId: patientVisits[0]?.id ?? "VIS-MOCK",
        filePath: "local-mock-upload.dcm",
        fileName: "local-mock-upload.dcm",
        fileType: "Mock Uploaded X-ray",
        uploadedBy: patientVisits[0]?.doctorId ?? "DOC-001",
        uploadedAt: "2026-02-09",
      },
    ]);
    setUploadOpen(false);
  };

  const updateDraftVisit = (visitId: string, field: keyof Pick<BackendVisit, "symptomsChiefComplaint" | "diagnosisNotes" | "treatmentNotes" | "clinicalNotes">, value: string) => {
    setDraftVisits((current) => current.map((visit) => visit.id === visitId ? { ...visit, [field]: value } : visit));
  };

  const openInvoice = (invoice: BackendInvoice) => {
    setSelectedInvoice(invoice);
  };

  const handleInvoiceTouch = (invoice: BackendInvoice) => {
    const now = Date.now();
    if (lastInvoiceTap?.id === invoice.id && now - lastInvoiceTap.at < 360) {
      openInvoice(invoice);
    }
    setLastInvoiceTap({ id: invoice.id, at: now });
  };

  const saveInvoice = (invoice: Invoice) => {
    setLocalInvoices((current) =>
      current.map((item) => {
        if (item.id !== invoice.id) return item;
        const paidAmount = item.paidAmount ?? 0;
        return {
          ...item,
          ...invoice,
          paidAmount,
          balance: Math.max(invoice.totalAmount - paidAmount, 0),
        };
      }),
    );
    setSelectedInvoice((current) => {
      if (!current || current.id !== invoice.id) return current;
      const paidAmount = current.paidAmount ?? 0;
      return {
        ...current,
        ...invoice,
        paidAmount,
        balance: Math.max(invoice.totalAmount - paidAmount, 0),
      };
    });
  };

  const deleteAttachment = (attachment: BackendAttachment) => {
    if (!window.confirm(`Delete ${attachment.fileType}? This removes the local mock X-ray and linked viewer action.`)) {
      return;
    }
    setMockUploads((current) => current.filter((item) => item.id !== attachment.id));
    setDeletedAttachmentIds((current) => [...current, attachment.id]);
    if (viewerPayload?.result.fileId === attachment.id) {
      setViewerPayload(null);
    }
  };

  const saveNewAppointment = (appointment: BackendAppointment) => {
    const nextAppointments = [...appointmentRows, appointment];
    setAppointmentRows(nextAppointments);
    saveMockAppointments(nextAppointments);
    setAppointmentCreateOpen(false);
  };

  const tabs = [
    {
      id: "general",
      label: "General",
      content: (
        <div className="stack">
          <PatientForm patient={selectedPatient} editable={editMode} onChange={setDraftPatient} />
        </div>
      ),
    },
    {
      id: "history",
      label: "History",
      content: (
        <div className="stack">
          {patientVisits.map((visit) => {
            const doctor = getStaffProfileById(visit.doctorId);
            return (
              <article className="soft-panel" key={visit.id}>
                <div className="between">
                  <div>
                    <h3 className="card-title">{prettyDate(visit.visitDate)}</h3>
                    <p className="tiny">{doctor?.fullName}</p>
                  </div>
                  <Badge tone={visit.status === "Completed" ? "green" : "primary"}>{visit.status}</Badge>
                </div>
                {editMode && canEdit ? (
                  <div className="stack mt-16">
                    <Textarea label="Symptoms / Chief Complaint" value={visit.symptomsChiefComplaint} onChange={(event) => updateDraftVisit(visit.id, "symptomsChiefComplaint", event.target.value)} />
                    <Textarea label="Diagnosis Notes" value={visit.diagnosisNotes} onChange={(event) => updateDraftVisit(visit.id, "diagnosisNotes", event.target.value)} />
                    <Textarea label="Treatment Notes" value={visit.treatmentNotes} onChange={(event) => updateDraftVisit(visit.id, "treatmentNotes", event.target.value)} />
                    <Textarea label="Clinical Notes" value={visit.clinicalNotes} onChange={(event) => updateDraftVisit(visit.id, "clinicalNotes", event.target.value)} />
                  </div>
                ) : (
                  <dl className="detail-list">
                    <div><dt>Symptoms / Chief Complaint</dt><dd>{visit.symptomsChiefComplaint}</dd></div>
                    <div><dt>Diagnosis Notes</dt><dd>{visit.diagnosisNotes}</dd></div>
                    <div><dt>Treatment Notes</dt><dd>{visit.treatmentNotes}</dd></div>
                    <div><dt>Clinical Notes</dt><dd>{visit.clinicalNotes}</dd></div>
                  </dl>
                )}
              </article>
            );
          })}
          {patientVisits.length === 0 && <div className="empty-inline">No visit history yet.</div>}
        </div>
      ),
    },
    {
      id: "ai",
      label: "X-rays",
      content: (
        <div className="stack">
          {canEdit && (
            <div className="right">
              <Button variant="secondary" icon={<FileUp size={17} />} onClick={() => setUploadOpen((value) => !value)}>Upload X-ray</Button>
            </div>
          )}
          {uploadOpen && (
            <div className="soft-panel upload-card">
              <span className="stat-icon"><FileUp size={22} /></span>
              <div>
                <h3 className="card-title">Mock X-ray upload</h3>
                <p className="muted">Supported: PNG, JPG, JPEG, or DICOM placeholder files.</p>
                <input type="file" accept=".png,.jpg,.jpeg,.dcm" />
                <div className="progress-bar"><span style={{ width: "72%" }} /></div>
                <p className="tiny">Mock progress only. No file leaves this prototype.</p>
              </div>
              <Button type="button" onClick={addMockUpload}>Add Upload</Button>
            </div>
          )}
          {patientAttachments.map((attachment) => {
            const aiResult = getAIResultByFileId(attachment.id);
            const findings = aiResult
              ? getAIFindingsByAnalysisId(aiResult.analysisId).slice(0, 3)
              : [];
            return (
              <article className="soft-panel" key={attachment.id}>
                <div className="between">
                  <div>
                    <h3 className="card-title">{attachment.fileType}</h3>
                    <p className="tiny">Uploaded {prettyDate(attachment.uploadedAt)}</p>
                  </div>
                  {aiResult && <Badge tone={aiStatusTone[aiResult.status]}>{aiResult.status}</Badge>}
                </div>
                {aiResult && <p className="muted">{aiResult.resultSummary}</p>}
                <AiFindingsTable findings={findings} compact />
                {editMode && canEdit && <Textarea label="Doctor review note" placeholder="Add a local mock note about this image." />}
                <div className="right">
                  {canEdit && (
                    <Button variant="danger" icon={<Trash2 size={16} />} onClick={() => deleteAttachment(attachment)}>
                      Delete X-ray
                    </Button>
                  )}
                  <Button
                    variant="secondary"
                    disabled={!aiResult}
                    onClick={() => aiResult && setViewerPayload({ result: aiResult, findings })}
                  >
                    {aiResult ? "Open X-ray Viewer" : "No viewer available"}
                  </Button>
                </div>
              </article>
            );
          })}
          {patientAttachments.length === 0 && <div className="empty-inline">No X-rays uploaded for this patient.</div>}
        </div>
      ),
    },
    {
      id: "billing",
      label: "Billing",
      content: (
        <div className="stack">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Total</th>
                  <th>Paid</th>
                  <th>Remaining</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {patientInvoices.map((invoice) => (
                  <tr
                    className="clickable"
                    key={invoice.id}
                    onClick={() => openInvoice(invoice)}
                    onDoubleClick={() => openInvoice(invoice)}
                    onTouchEnd={() => handleInvoiceTouch(invoice)}
                  >
                    <td>{invoice.id}</td>
                    <td>{currency(invoice.totalAmount)}</td>
                    <td>{currency(invoice.paidAmount ?? 0)}</td>
                    <td>{currency(invoice.balance ?? 0)}</td>
                    <td><Badge tone={invoiceStatusTone[invoice.status]}>{invoice.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {patientInvoices.length === 0 && <div className="empty-inline">No invoices for this patient.</div>}
        </div>
      ),
    },
    {
      id: "appointments",
      label: "Appointments",
      content: (
        <div className="stack">
          {canCreateAppointments && <Button className="self-start" icon={<CalendarPlus size={17} />} onClick={() => setAppointmentCreateOpen(true)}>Book new appointment</Button>}
          {patientAppointments.map((appointment) => {
            const doctor = getStaffProfileById(appointment.doctorId);
            return (
              <article className="soft-panel" key={appointment.id}>
                <div className="between">
                <div>
                  <h3 className="card-title">{appointment.visitType}</h3>
                  <p className="tiny">{prettyDate(appointment.date)} at {appointment.time} with {doctor?.fullName}</p>
                </div>
                  {editMode && canEdit ? (
                    <Select options={["Scheduled", "Arrived", "Checked-in", "In Visit", "Completed", "Cancelled", "No-show", "Postponed", "Needs Reschedule"]} defaultValue={appointment.status} />
                  ) : (
                    <Badge tone={appointmentStatusTone[appointment.status]}>{appointment.status}</Badge>
                  )}
                </div>
                {editMode && canEdit && <Textarea className="mt-16" label="Appointment note" defaultValue={appointment.notes} />}
              </article>
            );
          })}
        </div>
      ),
    },
  ];

  return (
    <>
    <Drawer title="Patient Details" open={open} onClose={onClose} width={1240}>
      <div className="detail-layout patient-drawer">
        <aside className="detail-sidebar patient-side patient-side-compact">
          <div className="avatar large">{initials(patientName)}</div>
          <div className="patient-headline">
            <h2>{patientName}</h2>
            <p>{selectedPatient.gender} - {ageFromDate(selectedPatient.dateOfBirth)} years</p>
          </div>
          <div className="patient-meta patient-meta-compact">
            <span>Phone</span><strong>{selectedPatient.phoneNumber || "Not set"}</strong>
            <span>Email</span><strong>{selectedPatient.email || "Not set"}</strong>
            <span>Blood Group</span><strong>{selectedPatient.bloodGroup || "Not set"}</strong>
            <span>Insurance</span><strong>{selectedPatient.insuranceInfo || "Not set"}</strong>
            <span>Emergency Contact</span><strong>{selectedPatient.emergencyContact || "Not set"}</strong>
          </div>
        </aside>
        <section className="detail-main patient-main">
          <div className="patient-main-header">
            <div>
              <h2 className="section-title">Patient Details</h2>
              <p className="tiny">Complete patient record and visit context.</p>
            </div>
            <div className="right">
              {editMode ? (
                <>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setDraftPatient(localPatient);
                      setDraftVisits(localVisits);
                      setEditMode(false);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    icon={<Save size={17} />}
                    onClick={() => {
                      setLocalPatient(draftPatient);
                      setLocalVisits(draftVisits);
                      onSavePatient?.(draftPatient);
                      setEditMode(false);
                    }}
                  >
                    Save Changes
                  </Button>
                </>
              ) : canEdit ? (
                <Button
                  variant="secondary"
                  icon={<Pencil size={17} />}
                  onClick={() => {
                    setDraftPatient(localPatient);
                    setDraftVisits(localVisits);
                    setEditMode(true);
                  }}
                >
                  Edit
                </Button>
              ) : null}
            </div>
          </div>
          <Tabs tabs={tabs} activeId={activeTab} onChange={setActiveTab} />
        </section>
      </div>
    </Drawer>
    <Modal
      title="X-ray Viewer"
      subtitle={viewerPayload?.result.modelVersion}
      open={Boolean(viewerPayload)}
      onClose={() => setViewerPayload(null)}
      width={1080}
    >
      {viewerPayload && <XrayViewer result={viewerPayload.result} findings={viewerPayload.findings} />}
    </Modal>
    <InvoiceDetails
      invoice={selectedInvoice}
      open={Boolean(selectedInvoice)}
      onClose={() => setSelectedInvoice(null)}
      canEditInvoice={canEdit && !readOnlyBilling}
      canProcessPayment={false}
      onSave={saveInvoice}
    />
    <AppointmentModal
      appointment={null}
      mode="new"
      open={appointmentCreateOpen}
      initialPatientId={selectedPatient.patientId}
      patientOptions={patientOptions}
      slotDate=""
      slotTime=""
      appointments={appointmentRows}
      availabilityExceptions={loadMockAvailabilityExceptions()}
      onCreate={saveNewAppointment}
      onClose={() => setAppointmentCreateOpen(false)}
    />
    </>
  );
}

export const defaultPatient = patients[0];
