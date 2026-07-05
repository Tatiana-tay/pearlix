import { useMemo, useState } from "react";
import { CheckCircle2, CircleDollarSign, FileText, Search, WalletCards } from "lucide-react";
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
import { useCurrentUser } from "../../context/SessionContext";
import { getPatientById, getStaffProfileById, getVisitById } from "../../data/adapters";
import type { BackendInvoice } from "../../types/models";
import { currency, fullPatientName, prettyDate } from "../../utils/format";
import { loadMockInvoices, saveMockInvoices } from "../../utils/mockClinicState";
import { invoiceStatusTone } from "../../utils/statusStyles";

export function BillingPage() {
  const currentUser = useCurrentUser();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("All");
  const [dateFilter, setDateFilter] = useState("");
  const [invoiceIdQuery, setInvoiceIdQuery] = useState("");
  const [invoiceRows, setInvoiceRows] = useState<BackendInvoice[]>(loadMockInvoices);
  const [selectedInvoice, setSelectedInvoice] = useState<BackendInvoice | null>(null);
  const [paymentInvoice, setPaymentInvoice] = useState<BackendInvoice | null>(null);

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

  const saveInvoice = (invoice: BackendInvoice) => {
    const nextRows = invoiceRows.map((item) => item.id === invoice.id ? invoice : item);
    saveMockInvoices(nextRows);
    const reloadedRows = loadMockInvoices();
    const reloadedInvoice = reloadedRows.find((item) => item.id === invoice.id) ?? invoice;
    setInvoiceRows(reloadedRows);
    setSelectedInvoice(reloadedInvoice);
    setPaymentInvoice((current) => current?.id === invoice.id ? (reloadedInvoice.status === "Cancelled" ? null : reloadedInvoice) : current);
  };

  const applyPayment = (invoice: BackendInvoice) => {
    if (invoice.status === "Cancelled") return;
    const reloadedRows = loadMockInvoices();
    const reloadedInvoice = reloadedRows.find((item) => item.id === invoice.id) ?? invoice;
    setInvoiceRows(reloadedRows);
    setSelectedInvoice((current) => current?.id === invoice.id ? reloadedInvoice : current);
    setPaymentInvoice(reloadedInvoice.status === "Cancelled" ? null : reloadedInvoice);
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
        return patient ? fullPatientName(patient) : invoice.patientId;
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
      cell: (invoice) => getStaffProfileById(invoice.doctorId)?.fullName,
    },
    { header: "Total", cell: (invoice) => currency(invoice.totalAmount) },
    { header: "Paid", cell: (invoice) => currency(invoice.paidAmount ?? 0) },
    { header: "Balance", cell: (invoice) => currency(invoice.balance ?? Math.max(invoice.totalAmount - (invoice.paidAmount ?? 0), 0)) },
    { header: "Status", cell: (invoice) => <Badge tone={invoiceStatusTone[invoice.status]}>{invoice.status}</Badge> },
  ];

  return (
    <div className="page-shell">
      <PageHeader title="Billing" subtitle="Manage invoices and payments." />
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
        <DataTable columns={columns} rows={filteredInvoices} getRowKey={(invoice) => invoice.id} onRowClick={setSelectedInvoice} onRowDoubleClick={setSelectedInvoice} />
      </Card>
      <InvoiceDetails
        invoice={selectedInvoice}
        open={Boolean(selectedInvoice)}
        onClose={() => setSelectedInvoice(null)}
        onProcessPayment={openPayment}
        onSave={saveInvoice}
        canEditInvoice={canEditInvoice}
        canProcessPayment={canProcessPayment}
      />
      {canProcessPayment && paymentInvoice?.status !== "Cancelled" && (
        <PaymentModal invoice={paymentInvoice} open={Boolean(paymentInvoice)} onClose={() => setPaymentInvoice(null)} onPaymentSaved={applyPayment} />
      )}
    </div>
  );
}
