import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleDollarSign, FileText, Search, WalletCards } from "lucide-react";
import {
  adaptInvoiceDTO,
  adaptPaymentDTO,
  cancelInvoice,
  createPayment,
  listInvoices,
  listPayments,
  toInvoiceCancelPayload,
  toInvoiceUpdatePayload,
  toPaymentPayload,
  updateInvoiceTotal,
} from "../../api/billing";
import { isApiError } from "../../api/errors";
import { InvoiceDetails } from "../../components/billing/InvoiceDetails";
import { PaymentModal } from "../../components/billing/PaymentModal";
import { PageHeader } from "../../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../../components/tables/DataTable";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { FilterPopover } from "../../components/ui/FilterPopover";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { StatCard } from "../../components/ui/StatCard";
import { useCurrentUser, useSession } from "../../context/SessionContext";
import { getPatientById, getStaffProfileById, getVisitById } from "../../data/adapters";
import type { BackendInvoice, BackendPayment } from "../../types/models";
import { currency, fullPatientName, prettyDate } from "../../utils/format";
import { invoiceStatusTone } from "../../utils/statusStyles";

export function BillingPage() {
  const currentUser = useCurrentUser();
  const { accessToken, clearSession } = useSession();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("All");
  const [dateFilter, setDateFilter] = useState("");
  const [invoiceIdQuery, setInvoiceIdQuery] = useState("");
  const [invoiceRows, setInvoiceRows] = useState<BackendInvoice[]>([]);
  const [paymentRows, setPaymentRows] = useState<BackendPayment[]>([]);
  const [selectedInvoice, setSelectedInvoice] = useState<BackendInvoice | null>(null);
  const [paymentInvoice, setPaymentInvoice] = useState<BackendInvoice | null>(null);
  const [loadingBilling, setLoadingBilling] = useState(true);
  const [pageError, setPageError] = useState("");

  useEffect(() => {
    if (!accessToken) {
      setLoadingBilling(false);
      setPageError("Sign in again to view billing.");
      return;
    }
    let cancelled = false;
    setLoadingBilling(true);
    setPageError("");
    Promise.all([listInvoices({ accessToken }), listPayments({ accessToken })])
      .then(([invoices, payments]) => {
        if (cancelled) return;
        setInvoiceRows(invoices.map(adaptInvoiceDTO));
        setPaymentRows(payments.map(adaptPaymentDTO));
        setPageError("");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        handleAuthError(error, clearSession);
        setPageError(toBillingErrorMessage(error, "Unable to load billing."));
      })
      .finally(() => {
        if (!cancelled) setLoadingBilling(false);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, clearSession]);

  const filteredInvoices = useMemo(() => {
    const normalized = query.toLowerCase();
    return invoiceRows.filter((invoice) => {
      const patient = getPatientById(invoice.patientId);
      const matchesQuery = `${invoice.id} ${patient ? fullPatientName(patient) : ""}`.toLowerCase().includes(normalized);
      const matchesStatus = status === "All" || invoice.status === status;
      const matchesDate = !dateFilter || invoice.invoiceDate === dateFilter;
      const matchesInvoice = !invoiceIdQuery || invoice.id.toLowerCase().includes(invoiceIdQuery.toLowerCase());
      return matchesQuery && matchesStatus && matchesDate && matchesInvoice;
    });
  }, [dateFilter, invoiceIdQuery, invoiceRows, query, status]);

  const activeFilters = (status !== "All" ? 1 : 0) + (dateFilter ? 1 : 0) + (invoiceIdQuery ? 1 : 0);
  const canEditInvoice = currentUser.role === "Staff";
  const canProcessPayment = currentUser.role === "Staff";

  const pendingAmount = invoiceRows
    .filter((invoice) => invoice.status !== "Paid" && invoice.status !== "Cancelled")
    .reduce((sum, invoice) => sum + (invoice.balance ?? Math.max(invoice.totalAmount - (invoice.paidAmount ?? 0), 0)), 0);

  const refreshBilling = async (targetInvoiceId?: string) => {
    if (!accessToken) return;
    const [invoices, payments] = await Promise.all([listInvoices({ accessToken }), listPayments({ accessToken })]);
    const adaptedInvoices = invoices.map(adaptInvoiceDTO);
    setInvoiceRows(adaptedInvoices);
    setPaymentRows(payments.map(adaptPaymentDTO));
    if (targetInvoiceId) {
      const refreshed = adaptedInvoices.find((invoice) => invoice.id === targetInvoiceId) ?? null;
      setSelectedInvoice((current) => current?.id === targetInvoiceId ? refreshed : current);
      setPaymentInvoice((current) => current?.id === targetInvoiceId ? (refreshed?.status === "Cancelled" ? null : refreshed) : current);
    }
  };

  const saveInvoice = async (invoice: BackendInvoice) => {
    if (!accessToken) throw new Error("Sign in again to edit invoices.");
    try {
      const savedInvoice = adaptInvoiceDTO(await updateInvoiceTotal(invoice.id, toInvoiceUpdatePayload(invoice), { accessToken }));
      setInvoiceRows((current) => current.map((item) => item.id === savedInvoice.id ? savedInvoice : item));
      setSelectedInvoice(savedInvoice);
      setPaymentInvoice((current) => current?.id === savedInvoice.id ? savedInvoice : current);
      setPageError("");
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toBillingErrorMessage(error, "Unable to save invoice."));
    }
  };

  const saveInvoiceCancel = async (invoice: BackendInvoice) => {
    if (!accessToken) throw new Error("Sign in again to cancel invoices.");
    try {
      const savedInvoice = adaptInvoiceDTO(await cancelInvoice(invoice.id, toInvoiceCancelPayload(invoice), { accessToken }));
      setInvoiceRows((current) => current.map((item) => item.id === savedInvoice.id ? savedInvoice : item));
      setSelectedInvoice(savedInvoice);
      setPaymentInvoice((current) => current?.id === savedInvoice.id ? null : current);
      setPageError("");
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toBillingErrorMessage(error, "Unable to cancel invoice."));
    }
  };

  const applyPayment = async (invoice: BackendInvoice, amount: number, note?: string) => {
    if (invoice.status === "Cancelled") return;
    if (!accessToken) throw new Error("Sign in again to process payments.");
    try {
      const payment = adaptPaymentDTO(await createPayment(toPaymentPayload(invoice, amount, note), { accessToken }));
      setPaymentRows((current) => [payment, ...current]);
      await refreshBilling(invoice.id);
      setPageError("");
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toBillingErrorMessage(error, "Unable to process payment."));
    }
  };

  const openPayment = (invoice: BackendInvoice) => {
    if (invoice.status === "Cancelled") return;
    setPaymentInvoice(invoice);
  };

  const columns: DataColumn<BackendInvoice>[] = [
    { header: "Invoice ID", cell: (invoice) => invoice.id },
    {
      header: "Patient",
      cell: (invoice) => {
        const patient = getPatientById(invoice.patientId);
        return invoice.patientName || (patient ? fullPatientName(patient) : invoice.patientId);
      },
    },
    {
      header: "Visit Date",
      cell: (invoice) => {
        const visit = getVisitById(invoice.visitId);
        return visit ? prettyDate(visit.visitDate) : prettyDate(invoice.invoiceDate);
      },
    },
    {
      header: "Doctor",
      cell: (invoice) => invoice.doctorName || getStaffProfileById(invoice.doctorId)?.fullName,
    },
    { header: "Total", cell: (invoice) => currency(invoice.totalAmount) },
    { header: "Paid", cell: (invoice) => currency(invoice.paidAmount ?? 0) },
    { header: "Balance", cell: (invoice) => currency(invoice.balance ?? Math.max(invoice.totalAmount - (invoice.paidAmount ?? 0), 0)) },
    { header: "Status", cell: (invoice) => <Badge tone={invoiceStatusTone[invoice.status]}>{invoice.status}</Badge> },
  ];

  return (
    <div className="page-shell">
      <PageHeader title="Billing" subtitle="Manage invoices and payments." />
      {pageError && <div className="alert-card">{pageError}</div>}
      <div className="grid grid-4">
        <StatCard label="Total Invoices" value={invoiceRows.length} icon={<FileText size={22} />} />
        <StatCard label="Pending Amount" value={currency(pendingAmount)} icon={<CircleDollarSign size={22} />} />
        <StatCard label="Partially Paid" value={invoiceRows.filter((invoice) => invoice.status === "Partially Paid").length} icon={<WalletCards size={22} />} />
        <StatCard label="Paid Invoices" value={invoiceRows.filter((invoice) => invoice.status === "Paid").length} icon={<CheckCircle2 size={22} />} />
      </div>
      <Card>
        <div className="filter-card">
          <Input icon={<Search size={18} />} placeholder="Search by patient or invoice ID..." value={query} onChange={(event) => setQuery(event.target.value)} />
          <FilterPopover activeCount={activeFilters}>
            <div className="filter-popover-content">
              <Input label="Date" type="date" value={dateFilter} onChange={(event) => setDateFilter(event.target.value)} />
              <Select label="Payment status" options={["All", "Pending", "Partially Paid", "Paid", "Cancelled"]} value={status} onChange={(event) => setStatus(event.target.value)} />
              <Input label="Invoice ID" placeholder="INV-2026" value={invoiceIdQuery} onChange={(event) => setInvoiceIdQuery(event.target.value)} />
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setDateFilter("");
                  setInvoiceIdQuery("");
                  setStatus("All");
                }}
              >
                Clear filters
              </Button>
            </div>
          </FilterPopover>
        </div>
      </Card>
      <Card>
        <div className="between mb-16">
          <h2 className="card-title">All Invoices</h2>
        </div>
        {loadingBilling ? <div className="empty-inline">Loading billing...</div> : <DataTable columns={columns} rows={filteredInvoices} getRowKey={(invoice) => invoice.id} onRowClick={setSelectedInvoice} onRowDoubleClick={setSelectedInvoice} />}
      </Card>
      <InvoiceDetails
        invoice={selectedInvoice}
        open={Boolean(selectedInvoice)}
        onClose={() => setSelectedInvoice(null)}
        onProcessPayment={openPayment}
        onSave={saveInvoice}
        onCancelInvoice={saveInvoiceCancel}
        payments={paymentRows}
        canEditInvoice={canEditInvoice}
        canProcessPayment={canProcessPayment}
      />
      {canProcessPayment && paymentInvoice?.status !== "Cancelled" && (
        <PaymentModal invoice={paymentInvoice} open={Boolean(paymentInvoice)} onClose={() => setPaymentInvoice(null)} onPaymentSaved={applyPayment} />
      )}
    </div>
  );
}

function handleAuthError(error: unknown, clearSession: (message?: string) => void) {
  if (isApiError(error) && error.status === 401) {
    clearSession("Your session has expired. Please sign in again.");
  }
}

function toBillingErrorMessage(error: unknown, fallback: string) {
  if (isApiError(error)) {
    if (error.status === 409) {
      return "This billing record was updated elsewhere. Please refresh and try again.";
    }
    const validationMessage = formatValidationErrors(error.validationErrors);
    if (validationMessage) return validationMessage;
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
  if (!errors) return "";
  return Object.entries(errors)
    .map(([field, messages]) => `${field}: ${messages.join(" ")}`)
    .join(" ");
}
