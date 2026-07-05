import { useEffect, useMemo, useState } from "react";
import { CalendarPlus, FileUp, Pencil, Save, Trash2 } from "lucide-react";
import {
  adaptAttachmentDTO,
  deleteAttachment as deleteAttachmentRequest,
  fetchAttachmentOriginalBlob,
  listAttachments,
  uploadAttachment,
} from "../../api/attachments";
import { adaptAIResultDTO, listAIResults } from "../../api/aiResults";
import { isApiError } from "../../api/errors";
import { AppointmentModal } from "../appointments/AppointmentModal";
import { InvoiceDetails } from "../billing/InvoiceDetails";
import {
  getStaffProfileById,
  getVisitsForPatient,
  invoices,
  patients,
} from "../../data/adapters";
import { useSession } from "../../context/SessionContext";
import type { BackendAIResult, BackendAppointment, BackendAttachment, BackendInvoice, BackendPatient, BackendVisit, Invoice } from "../../types/models";
import { ageFromDate, currency, fullPatientName, initials, prettyDate } from "../../utils/format";
import { loadMockAppointments, loadMockAvailabilityExceptions, saveMockAppointments } from "../../utils/mockScheduleState";
import { aiStatusTone, appointmentStatusTone, invoiceStatusTone } from "../../utils/statusStyles";
import { AiFindingsTable } from "../ai/AiFindingsTable";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Drawer } from "../ui/Drawer";
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
  onSavePatient?: (patient: BackendPatient) => BackendPatient | Promise<BackendPatient> | void | Promise<void>;
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
  const { accessToken, clearSession, currentUser } = useSession();
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
  const [patientAttachments, setPatientAttachments] = useState<BackendAttachment[]>([]);
  const [attachmentsLoading, setAttachmentsLoading] = useState(false);
  const [attachmentError, setAttachmentError] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDescription, setUploadDescription] = useState("");
  const [uploadingAttachment, setUploadingAttachment] = useState(false);
  const [openingAttachmentId, setOpeningAttachmentId] = useState("");
  const [aiResults, setAiResults] = useState<BackendAIResult[]>([]);
  const [aiResultsLoading, setAiResultsLoading] = useState(false);
  const [aiResultError, setAiResultError] = useState("");
  const [appointmentRows, setAppointmentRows] = useState<BackendAppointment[]>(loadMockAppointments);
  const [appointmentCreateOpen, setAppointmentCreateOpen] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [savingPatient, setSavingPatient] = useState(false);
  const selectedPatient = editMode ? draftPatient : localPatient;
  const patientName = fullPatientName(selectedPatient) || "Patient";
  const canCreateAppointments = currentUser?.role === "Staff";

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
      setPatientAttachments([]);
      setAttachmentError("");
      setUploadFile(null);
      setUploadDescription("");
      setUploadingAttachment(false);
      setOpeningAttachmentId("");
      setAiResults([]);
      setAiResultError("");
      setAiResultsLoading(false);
      setAppointmentRows(loadMockAppointments());
      setAppointmentCreateOpen(false);
      setSaveError("");
      setSavingPatient(false);
    }
  }, [open, patient?.patientId]);

  useEffect(() => {
    if (!open || !accessToken || !selectedPatient.patientId) {
      return;
    }

    let cancelled = false;
    setAttachmentsLoading(true);
    setAttachmentError("");

    listAttachments({ patientId: selectedPatient.patientId, attachmentType: "X-ray" }, { accessToken })
      .then((rows) => {
        if (cancelled) return;
        setPatientAttachments(rows.map(adaptAttachmentDTO));
        setAttachmentError("");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        handleAttachmentAuthError(error, clearSession);
        setAttachmentError(toAttachmentErrorMessage(error, "Unable to load attachments."));
      })
      .finally(() => {
        if (!cancelled) {
          setAttachmentsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, clearSession, open, selectedPatient.patientId]);

  useEffect(() => {
    if (!open || !accessToken || !selectedPatient.patientId) {
      return;
    }

    let cancelled = false;
    setAiResultsLoading(true);
    setAiResultError("");

    listAIResults({ patientId: selectedPatient.patientId }, { accessToken })
      .then((rows) => {
        if (cancelled) return;
        setAiResults(rows.map(adaptAIResultDTO));
        setAiResultError("");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        handleAttachmentAuthError(error, clearSession);
        setAiResultError(toAttachmentErrorMessage(error, "Unable to load stored AI results."));
      })
      .finally(() => {
        if (!cancelled) {
          setAiResultsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, clearSession, open, selectedPatient.patientId]);

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
  const aiResultsByAttachment = useMemo(() => {
    const grouped = new Map<string, BackendAIResult[]>();
    aiResults.forEach((result) => {
      const key = result.attachmentId ?? result.fileId;
      grouped.set(key, [...(grouped.get(key) ?? []), result]);
    });
    return grouped;
  }, [aiResults]);
  const uploadSelectedAttachment = async () => {
    if (!accessToken || !uploadFile) {
      setAttachmentError("Choose a file to upload.");
      return;
    }

    setUploadingAttachment(true);
    setAttachmentError("");
    try {
      const created = adaptAttachmentDTO(await uploadAttachment({
        patientId: selectedPatient.patientId,
        file: uploadFile,
        attachmentType: "X-ray",
        description: uploadDescription,
      }, { accessToken }));
      setPatientAttachments((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setUploadFile(null);
      setUploadDescription("");
      setUploadOpen(false);
    } catch (error) {
      handleAttachmentAuthError(error, clearSession);
      setAttachmentError(toAttachmentErrorMessage(error, "Unable to upload attachment."));
    } finally {
      setUploadingAttachment(false);
    }
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

  const removeAttachment = async (attachment: BackendAttachment) => {
    if (!accessToken || !window.confirm(`Delete ${attachment.fileName}? This removes the attachment from the backend.`)) {
      return;
    }

    setAttachmentError("");
    try {
      await deleteAttachmentRequest(attachment.id, { accessToken });
      setPatientAttachments((current) => current.filter((item) => item.id !== attachment.id));
    } catch (error) {
      handleAttachmentAuthError(error, clearSession);
      setAttachmentError(toAttachmentErrorMessage(error, "Unable to delete attachment."));
    }
  };

  const openAttachment = async (attachment: BackendAttachment) => {
    if (!accessToken) {
      setAttachmentError("Sign in again to open this attachment.");
      return;
    }

    setOpeningAttachmentId(attachment.id);
    setAttachmentError("");
    try {
      const blob = await fetchAttachmentOriginalBlob(attachment.id, { accessToken });
      const objectUrl = URL.createObjectURL(blob);
      window.open(objectUrl, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (error) {
      handleAttachmentAuthError(error, clearSession);
      setAttachmentError(toAttachmentErrorMessage(error, "Unable to open attachment."));
    } finally {
      setOpeningAttachmentId("");
    }
  };

  const saveNewAppointment = (appointment: BackendAppointment) => {
    const nextAppointments = [...appointmentRows, appointment];
    setAppointmentRows(nextAppointments);
    saveMockAppointments(nextAppointments);
    setAppointmentCreateOpen(false);
  };

  const savePatientChanges = async () => {
    setSaveError("");
    setSavingPatient(true);

    try {
      const savedPatient = await onSavePatient?.(draftPatient);
      const nextPatient = savedPatient ?? draftPatient;
      setLocalPatient(nextPatient);
      setDraftPatient(nextPatient);
      setLocalVisits(draftVisits);
      setEditMode(false);
    } catch (caughtError) {
      setSaveError(caughtError instanceof Error ? caughtError.message : "Unable to save patient.");
    } finally {
      setSavingPatient(false);
    }
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
                <h3 className="card-title">X-ray upload</h3>
                <p className="muted">Supported: PNG, JPG, JPEG, WEBP, PDF, or DICOM files up to 10 MB.</p>
                <input type="file" accept=".png,.jpg,.jpeg,.webp,.pdf,.dcm,.dicom" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
                <Textarea label="Description" value={uploadDescription} onChange={(event) => setUploadDescription(event.target.value)} />
              </div>
              <Button type="button" disabled={uploadingAttachment} onClick={() => { void uploadSelectedAttachment(); }}>
                {uploadingAttachment ? "Uploading..." : "Upload"}
              </Button>
            </div>
          )}
          {attachmentError && <div className="alert-card">{attachmentError}</div>}
          {aiResultError && <div className="alert-card">{aiResultError}</div>}
          {attachmentsLoading && <div className="empty-inline">Loading attachments...</div>}
          {aiResultsLoading && <div className="empty-inline">Loading stored AI results...</div>}
          {patientAttachments.map((attachment) => {
            const storedResults = aiResultsByAttachment.get(attachment.id) ?? [];
            const latestResult = storedResults[0];
            return (
              <article className="soft-panel" key={attachment.id}>
                <div className="between">
                  <div>
                    <h3 className="card-title">{attachment.fileName}</h3>
                    <p className="tiny">{attachment.fileType} - Uploaded {prettyDate(attachment.uploadedAt)}</p>
                  </div>
                  <Badge tone="primary">{attachment.mimeType || attachment.fileType}</Badge>
                </div>
                {attachment.description && <p className="muted">{attachment.description}</p>}
                {latestResult ? (
                  <div className="stack mt-16">
                    <div className="between">
                      <div>
                        <h3 className="card-title">Stored AI Analysis</h3>
                        <p className="tiny">Educational / research output only. Not a clinical diagnosis.</p>
                      </div>
                      <Badge tone={aiStatusTone[latestResult.status]}>{latestResult.status}</Badge>
                    </div>
                    <dl className="detail-list mt-16">
                      <div><dt>Model</dt><dd>{latestResult.modelName || "Not provided"}</dd></div>
                      <div><dt>Model Version</dt><dd>{latestResult.modelVersion || "Not provided"}</dd></div>
                      <div><dt>Processed</dt><dd>{prettyDate(latestResult.processedDate)}</dd></div>
                      <div><dt>Overall Confidence</dt><dd>{latestResult.overallConfidence ? `${Math.round(latestResult.overallConfidence * 100)}%` : "Not provided"}</dd></div>
                    </dl>
                    {latestResult.resultSummary && <p className="muted">{latestResult.resultSummary}</p>}
                    {latestResult.errorMessage && <div className="alert-card">{latestResult.errorMessage}</div>}
                    <AiFindingsTable findings={latestResult.findings ?? []} compact />
                    <div className="notice-card">AI Research Result: educational / research output only. Doctor review is required before any clinical use.</div>
                  </div>
                ) : (
                  <div className="empty-inline">No stored AI result for this attachment.</div>
                )}
                <div className="right">
                  {canEdit && (
                    <Button variant="danger" icon={<Trash2 size={16} />} onClick={() => { void removeAttachment(attachment); }}>
                      Delete X-ray
                    </Button>
                  )}
                  <Button
                    variant="secondary"
                    disabled={openingAttachmentId === attachment.id}
                    onClick={() => { void openAttachment(attachment); }}
                  >
                    {openingAttachmentId === attachment.id ? "Opening..." : "Open / Download"}
                  </Button>
                </div>
              </article>
            );
          })}
          {!attachmentsLoading && patientAttachments.length === 0 && <div className="empty-inline">No X-rays uploaded for this patient.</div>}
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
                    disabled={savingPatient}
                    onClick={() => {
                      setDraftPatient(localPatient);
                      setDraftVisits(localVisits);
                      setSaveError("");
                      setEditMode(false);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    icon={<Save size={17} />}
                    disabled={savingPatient}
                    onClick={() => { void savePatientChanges(); }}
                  >
                    {savingPatient ? "Saving..." : "Save Changes"}
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
          {saveError && <div className="alert-card">{saveError}</div>}
          <Tabs tabs={tabs} activeId={activeTab} onChange={setActiveTab} />
        </section>
      </div>
    </Drawer>
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

function handleAttachmentAuthError(error: unknown, clearSession: (message?: string) => void) {
  if (isApiError(error) && error.status === 401) {
    clearSession("Your session has expired. Please sign in again.");
  }
}

function toAttachmentErrorMessage(error: unknown, fallback: string) {
  if (isApiError(error)) {
    const validationMessage = formatAttachmentValidationErrors(error.validationErrors);
    if (validationMessage) {
      return validationMessage;
    }
    if (error.status === 403) {
      return error.message || "You do not have permission to manage this attachment.";
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

function formatAttachmentValidationErrors(errors: Record<string, string[]> | undefined) {
  if (!errors) {
    return "";
  }
  return Object.entries(errors)
    .map(([field, messages]) => `${field}: ${messages.join(" ")}`)
    .join(" ");
}

export const defaultPatient = patients[0];
