import { useEffect, useState } from "react";
import { FileDown, Pencil, Printer, Save } from "lucide-react";
import { getPatientById, getStaffProfileById, getVisitById } from "../../data/adapters";
import type { BackendInvoice, BackendPayment, Invoice } from "../../types/models";
import { currency, fullPatientName, prettyDate } from "../../utils/format";
import { invoiceStatusTone } from "../../utils/statusStyles";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { Select } from "../ui/Select";
import { Textarea } from "../ui/Textarea";

interface InvoiceDetailsProps {
  invoice: BackendInvoice | null;
  open: boolean;
  onClose: () => void;
  onProcessPayment?: (invoice: BackendInvoice) => void;
  canProcessPayment?: boolean;
  canEditInvoice?: boolean;
  payments?: BackendPayment[];
  onSave?: (invoice: BackendInvoice) => Promise<void> | void;
  onCancelInvoice?: (invoice: BackendInvoice) => Promise<void> | void;
}

const emptyPayments: BackendPayment[] = [];

export function InvoiceDetails({
  invoice,
  open,
  onClose,
  onProcessPayment,
  canProcessPayment = true,
  canEditInvoice = false,
  payments: invoicePayments = emptyPayments,
  onSave,
  onCancelInvoice,
}: InvoiceDetailsProps) {
  const [editMode, setEditMode] = useState(false);
  const [draftInvoice, setDraftInvoice] = useState<BackendInvoice | null>(invoice);
  const [description, setDescription] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [payments, setPayments] = useState<BackendPayment[]>([]);
  const [actionMessage, setActionMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setEditMode(false);
      setDraftInvoice(invoice);
      setPayments(invoice ? invoicePayments.filter((payment) => payment.invoiceId === invoice.id) : []);
      setActionMessage("");
      setSaving(false);
      const visit = getVisitById(invoice?.visitId);
      setDescription(visit?.treatmentNotes ?? "");
      setDraftDescription(visit?.treatmentNotes ?? "");
    }
  }, [invoice, invoicePayments, open]);

  if (!invoice) {
    return null;
  }

  const patient = getPatientById(invoice.patientId);
  const doctor = getStaffProfileById(invoice.doctorId);
  const visit = getVisitById(invoice.visitId);
  const displayInvoice = editMode && draftInvoice ? draftInvoice : invoice;
  const paid = payments.reduce((total, payment) => total + payment.amountPaid, 0);
  const rawBalance = displayInvoice.totalAmount - paid;
  const balance = Math.max(rawBalance, 0);
  const invalidTotal = rawBalance < 0;
  const isCancelled = invoice.status === "Cancelled";
  const canModifyInvoice = canEditInvoice && !isCancelled;
  const canTakePayment = canProcessPayment && !isCancelled;

  const updateDraft = (updates: Partial<BackendInvoice>) => {
    if (isCancelled) return;
    setDraftInvoice((current) => current ? { ...current, ...updates } : current);
  };

  const save = () => {
    if (!draftInvoice || invalidTotal || isCancelled) return;
    setSaving(true);
    Promise.resolve(onSave?.({
      ...draftInvoice,
      paidAmount: paid,
      balance: Math.max(draftInvoice.totalAmount - paid, 0),
    }))
      .then(() => {
        setDescription(draftDescription);
        setEditMode(false);
        setActionMessage("Invoice saved.");
      })
      .catch((error: unknown) => {
        setActionMessage(error instanceof Error ? error.message : "Unable to save invoice.");
      })
      .finally(() => setSaving(false));
  };

  const cancel = () => {
    setDraftInvoice(invoice);
    setDraftDescription(description);
    setEditMode(false);
  };

  const cancelInvoice = () => {
    if (isCancelled) return;
    setSaving(true);
    Promise.resolve(onCancelInvoice?.(invoice))
      .then(() => {
        setDraftInvoice({ ...invoice, status: "Cancelled" as Invoice["status"] });
        setActionMessage("Invoice cancelled.");
      })
      .catch((error: unknown) => {
        setActionMessage(error instanceof Error ? error.message : "Unable to cancel invoice.");
      })
      .finally(() => setSaving(false));
  };

  const printInvoice = () => {
    window.print();
    setActionMessage("Print dialog opened for this invoice.");
  };

  const exportInvoice = () => {
    const payload = [
      `Invoice: ${invoice.id}`,
      `Patient: ${patient ? fullPatientName(patient) : invoice.patientId}`,
      `Doctor: ${doctor?.fullName ?? invoice.doctorId}`,
      `Total: ${currency(displayInvoice.totalAmount)}`,
      `Paid: ${currency(paid)}`,
      `Balance: ${currency(balance)}`,
      `Status: ${displayInvoice.status}`,
    ].join("\n");
    const blob = new Blob([payload], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${invoice.id}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    setActionMessage("Invoice summary exported as a frontend demo text file.");
  };

  return (
    <Modal
      title="Invoice Details"
      subtitle={invoice.id}
      open={open}
      onClose={onClose}
      width={820}
      footer={
        editMode ? (
          <>
            <Button variant="secondary" disabled={saving} onClick={cancel}>Cancel</Button>
            <Button icon={<Save size={17} />} disabled={invalidTotal || saving} onClick={save}>{saving ? "Saving..." : "Save Changes"}</Button>
          </>
        ) : (
          <>
            <Button variant="secondary" icon={<Printer size={17} />} onClick={printInvoice}>Print Invoice</Button>
            <Button variant="secondary" icon={<FileDown size={17} />} onClick={exportInvoice}>Export PDF</Button>
            {canModifyInvoice && <Button variant="secondary" icon={<Pencil size={17} />} onClick={() => setEditMode(true)}>Edit</Button>}
            {canModifyInvoice && <Button variant="danger" disabled={saving} onClick={cancelInvoice}>Cancel Invoice</Button>}
            {canEditInvoice && isCancelled && <Button variant="secondary" disabled>Already Cancelled</Button>}
            {canTakePayment && onProcessPayment && <Button onClick={() => onProcessPayment(invoice)}>Process Payment</Button>}
          </>
        )
      }
    >
      <div className="stack">
        {actionMessage && <div className="notice-card">{actionMessage}</div>}
        {isCancelled && <div className="alert-card">This invoice has been cancelled and cannot be modified.</div>}
        <div className="grid grid-3">
          <div className="soft-panel">
            <span className="tiny">Patient information</span>
            <h3 className="card-title">{patient ? fullPatientName(patient) : invoice.patientId}</h3>
            <p className="muted">{patient?.phoneNumber}</p>
          </div>
          <div className="soft-panel">
            <span className="tiny">Visit information</span>
            <h3 className="card-title">{visit ? prettyDate(visit.visitDate) : invoice.invoiceDate}</h3>
            <p className="muted">{visit?.symptomsChiefComplaint}</p>
          </div>
          <div className="soft-panel">
            <span className="tiny">Doctor</span>
            <h3 className="card-title">{doctor?.fullName}</h3>
            <p className="muted">{doctor?.specialty}</p>
          </div>
        </div>

        <section className="soft-panel">
          <h3 className="card-title">Treatment notes from visit</h3>
          {editMode ? (
            <Textarea className="mt-16" label="Invoice description / treatment notes" value={draftDescription} onChange={(event) => setDraftDescription(event.target.value)} />
          ) : (
            <p className="muted">{description || visit?.treatmentNotes}</p>
          )}
        </section>

        {editMode && draftInvoice && !isCancelled ? (
          <section className="soft-panel">
            <h3 className="card-title">Edit invoice</h3>
            <div className="field-grid mt-16">
              <Input
                label="Total amount"
                type="number"
                min={paid}
                value={String(draftInvoice.totalAmount)}
                onChange={(event) => updateDraft({ totalAmount: Number(event.target.value) || 0 })}
              />
              <Select
                label="Status"
                options={["Pending", "Partially Paid", "Paid"]}
                value={draftInvoice.status}
                onChange={(event) => updateDraft({ status: event.target.value as Invoice["status"] })}
              />
            </div>
            {invalidTotal && <div className="alert-card mt-16">Total amount cannot be lower than the amount already paid.</div>}
          </section>
        ) : null}

        <div className="grid grid-4">
          <div className="soft-panel"><span className="tiny">Total amount</span><div className="metric">{currency(displayInvoice.totalAmount)}</div></div>
          <div className="soft-panel"><span className="tiny">Paid</span><div className="metric">{currency(paid)}</div></div>
          <div className="soft-panel"><span className="tiny">Remaining</span><div className="metric">{currency(balance)}</div></div>
          <div className="soft-panel"><span className="tiny">Payment status</span><div className="mt-12"><Badge tone={invoiceStatusTone[displayInvoice.status]}>{displayInvoice.status}</Badge></div></div>
        </div>

        <section className="soft-panel">
          <h3 className="card-title">Payment history</h3>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Payment Date</th>
                  <th>Amount Paid</th>
                  <th>Payment Method</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((payment) => (
                  <tr key={payment.id}>
                    <td>{prettyDate(payment.paymentDate)}</td>
                    <td>{currency(payment.amountPaid)}</td>
                    <td>{payment.paymentMethod}</td>
                    <td>{payment.notes ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {payments.length === 0 && <div className="empty-inline">No payments recorded yet.</div>}
        </section>
      </div>
    </Modal>
  );
}
