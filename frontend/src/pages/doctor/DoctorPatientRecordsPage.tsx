import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { PatientProfileDrawer } from "../../components/patients/PatientProfileDrawer";
import { DataTable, type DataColumn } from "../../components/tables/DataTable";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { FilterPopover } from "../../components/ui/FilterPopover";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { appointments, visits } from "../../data/adapters";
import type { BackendPatient } from "../../types/models";
import { ageFromDate, fullPatientName, initials, prettyDate } from "../../utils/format";
import { loadMockPatients } from "../../utils/mockClinicState";

export function DoctorPatientRecordsPage() {
  const [query, setQuery] = useState("");
  const [genderFilter, setGenderFilter] = useState("All");
  const [bloodFilter, setBloodFilter] = useState("All");
  const [selectedPatient, setSelectedPatient] = useState<BackendPatient | null>(null);
  const patients = useMemo(loadMockPatients, []);

  const bloodGroups = useMemo(
    () => ["All", ...Array.from(new Set(patients.map((patient) => patient.bloodGroup).filter(Boolean)))],
    [],
  );

  const filteredPatients = useMemo(() => {
    const normalized = query.toLowerCase();
    return patients.filter((patient) => {
      const matchesSearch = `${fullPatientName(patient)} ${patient.phoneNumber} ${patient.email ?? ""} ${patient.nationalIdOrPassport}`.toLowerCase().includes(normalized);
      const matchesGender = genderFilter === "All" || patient.gender === genderFilter;
      const matchesBlood = bloodFilter === "All" || patient.bloodGroup === bloodFilter;
      return matchesSearch && matchesGender && matchesBlood;
    });
  }, [bloodFilter, genderFilter, query]);

  const activeFilters = (genderFilter !== "All" ? 1 : 0) + (bloodFilter !== "All" ? 1 : 0);

  const columns: DataColumn<BackendPatient>[] = [
    {
      header: "Patient",
      cell: (patient) => (
        <div className="row">
          <span className="avatar">{initials(fullPatientName(patient))}</span>
          <div><strong>{fullPatientName(patient)}</strong><div className="tiny">{patient.gender}, {ageFromDate(patient.dateOfBirth)} years</div></div>
        </div>
      ),
    },
    { header: "Contact", cell: (patient) => <div>{patient.phoneNumber}<div className="tiny">{patient.email}</div></div> },
    { header: "Gender", cell: (patient) => patient.gender },
    {
      header: "Last Visit",
      cell: (patient) => {
        const visit = visits.filter((item) => item.patientId === patient.patientId).sort((a, b) => b.visitDate.localeCompare(a.visitDate))[0];
        return visit ? prettyDate(visit.visitDate) : "-";
      },
    },
    {
      header: "Next Appointment",
      cell: (patient) => {
        const appointment = appointments.filter((item) => item.patientId === patient.patientId && item.date >= "2026-02-09").sort((a, b) => a.date.localeCompare(b.date))[0];
        return appointment ? prettyDate(appointment.date) : "-";
      },
    },
  ];

  return (
    <div className="page-shell">
      <PageHeader title="Patients" subtitle="Open patient clinical records and visit context." />
      <Card>
        <div className="filter-card">
          <Input icon={<Search size={18} />} placeholder="Search by patient name or phone..." value={query} onChange={(event) => setQuery(event.target.value)} />
          <FilterPopover activeCount={activeFilters}>
            <div className="filter-popover-content">
              <Select label="Gender" options={["All", "Male", "Female"]} value={genderFilter} onChange={(event) => setGenderFilter(event.target.value)} />
              <Select label="Blood group" options={bloodGroups} value={bloodFilter} onChange={(event) => setBloodFilter(event.target.value)} />
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setGenderFilter("All");
                  setBloodFilter("All");
                }}
              >
                Clear filters
              </Button>
            </div>
          </FilterPopover>
        </div>
      </Card>
      <Card>
        <DataTable columns={columns} rows={filteredPatients} getRowKey={(patient) => patient.patientId} onRowClick={setSelectedPatient} />
      </Card>
      <PatientProfileDrawer open={Boolean(selectedPatient)} onClose={() => setSelectedPatient(null)} patient={selectedPatient} canEdit={false} readOnlyBilling />
    </div>
  );
}
