import { useEffect, useMemo, useState } from "react";
import { getPatientById } from "../../data/adapters";
import type { BackendInvoice, Payment } from "../../types/models";
import { currency, fullPatientName } from "../../utils/format";
import { recordMockPayment } from "../../utils/mockClinicState";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { Textarea } from "../ui/Textarea";

interface PaymentModalProps {
  invoice: BackendInvoice | null;
  open: boolean;
  onClose: () => void;
  onPaymentSaved?: (invoice: BackendInvoice) => void;
}

export function PaymentModal({ invoice, open, onClose, onPaymentSaved }: PaymentModalProps) {
  const [amount, setAmount] = useState("");
  const [paymentDate, setPaymentDate] = useState("2026-02-09");
  const [notes, setNotes] = useState("");
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"notice" | "alert">("notice");

  const patient = useMemo(
    () => getPatientById(invoice?.patientId),
    [invoice],
  );

  useEffect(() => {
    if (open) {
      setAmount("");
      setPaymentDate("2026-02-09");
      setNotes("");
      setMessage("");
      setMessageKind("notice");
    }
  }, [invoice?.id, open]);

  if (!invoice || invoice.status === "Cancelled") {
    return null;
  }

  const paid = invoice.paidAmount ?? 0;
  const balance = invoice.balance ?? Math.max(invoice.totalAmount - paid, 0);
  const parsedAmount = Number(amount);
  const invalidAmount = !parsedAmount || parsedAmount <= 0 || parsedAmount > balance;

  const confirmPayment = () => {
    if (invoice.status === "Cancelled") {
      setMessage("This invoice has been cancelled and cannot be modified.");
      setMessageKind("alert");
      return;
    }
    if (invalidAmount) {
      setMessage("Enter a positive amount that does not exceed the remaining balance.");
      setMessageKind("alert");
      return;
    }
    const updatedInvoice = recordMockPayment(invoice, {
      invoiceId: invoice.id,
      amountPaid: parsedAmount,
      paymentMethod: "Cash",
      paymentDate,
      notes: notes.trim() || undefined,
    });
    onPaymentSaved?.(updatedInvoice);
    setAmount("");
    setNotes("");
    setMessage("Payment captured locally and invoice balance updated.");
    setMessageKind("notice");
  };

  return (
    <Modal
      title="Process Payment"
      subtitle={invoice.id}
      open={open}
      onClose={onClose}
      width={560}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={confirmPayment}>Confirm Payment</Button>
        </>
      }
    >
      <div className="stack">
        <div className="soft-panel">
          <dl className="detail-list">
            <div><dt>Invoice ID</dt><dd>{invoice.id}</dd></div>
            <div><dt>Patient</dt><dd>{patient ? fullPatientName(patient) : invoice.patientId}</dd></div>
            <div><dt>Total amount</dt><dd>{currency(invoice.totalAmount)}</dd></div>
            <div><dt>Already paid</dt><dd>{currency(paid)}</dd></div>
            <div><dt>Remaining balance</dt><dd>{currency(balance)}</dd></div>
          </dl>
        </div>
        <Input label="Amount to pay" type="number" min="1" max={balance} value={amount} onChange={(event) => setAmount(event.target.value)} />
        <Input label="Payment Method" value={"Cash" satisfies Payment["Payment_Method"]} readOnly />
        <Input label="Payment date" type="date" value={paymentDate} onChange={(event) => setPaymentDate(event.target.value)} />
        <Textarea label="Notes" placeholder="Optional payment note" value={notes} onChange={(event) => setNotes(event.target.value)} />
        {message && <div className={messageKind === "alert" ? "alert-card" : "notice-card"}>{message}</div>}
      </div>
    </Modal>
  );
}
