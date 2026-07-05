import { useEffect, useMemo, useState } from "react";
import { Plus, Search } from "lucide-react";
import {
  adaptPatientDTO,
  createPatient,
  getPatient,
  listPatients,
  toPatientUpdatePayload,
  updatePatient,
  type PatientPayload,
} from "../../api/patients";
import { isApiError } from "../../api/errors";
import { PageHeader } from "../../components/layout/PageHeader";
import { PatientCreateModal } from "../../components/patients/PatientCreateModal";
import { PatientProfileDrawer } from "../../components/patients/PatientProfileDrawer";
import { DataTable, type DataColumn } from "../../components/tables/DataTable";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { FilterPopover } from "../../components/ui/FilterPopover";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { useCurrentUser, useSession } from "../../context/SessionContext";
import { appointments, visits } from "../../data/adapters";
import type { BackendPatient } from "../../types/models";
import { ageFromDate, fullPatientName, initials, prettyDate } from "../../utils/format";

export function PatientsPage() {
  const currentUser = useCurrentUser();
  const { accessToken, clearSession } = useSession();
  const [query, setQuery] = useState("");
  const [genderFilter, setGenderFilter] = useState("All");
  const [bloodFilter, setBloodFilter] = useState("All");
  const [selectedPatient, setSelectedPatient] = useState<BackendPatient | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [patientRows, setPatientRows] = useState<BackendPatient[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [pageError, setPageError] = useState("");
  const canWritePatients = currentUser.role === "Staff";

  useEffect(() => {
    if (!accessToken) {
      setLoadingPatients(false);
      setPageError("Sign in again to view patients.");
      return;
    }

    let cancelled = false;
    setLoadingPatients(true);
    setPageError("");

    listPatients({ accessToken })
      .then((patients) => {
        if (cancelled) {
          return;
        }
        setPatientRows(patients.map(adaptPatientDTO));
        setPageError("");
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        handleAuthError(error, clearSession);
        setPageError(toPatientErrorMessage(error, "Unable to load patients."));
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingPatients(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, clearSession]);

  const bloodGroups = useMemo(
    () => ["All", ...Array.from(new Set(patientRows.map((patient) => patient.bloodGroup).filter(Boolean)))],
    [patientRows],
  );

  const filteredPatients = useMemo(() => {
    const normalized = query.toLowerCase();
    return patientRows.filter((patient) => {
      const text = `${fullPatientName(patient)} ${patient.phoneNumber} ${patient.email ?? ""} ${patient.nationalIdOrPassport}`.toLowerCase();
      const matchesGender = genderFilter === "All" || patient.gender === genderFilter;
      const matchesBlood = bloodFilter === "All" || patient.bloodGroup === bloodFilter;
      return text.includes(normalized) && matchesGender && matchesBlood;
    });
  }, [bloodFilter, genderFilter, patientRows, query]);

  const activeFilters = (genderFilter !== "All" ? 1 : 0) + (bloodFilter !== "All" ? 1 : 0);

  const openDrawer = (patient: BackendPatient | null) => {
    setSelectedPatient(patient);
    setDrawerOpen(true);
    setPageError("");

    if (!patient?.id || !accessToken) {
      return;
    }

    getPatient(patient.id, { accessToken })
      .then((freshPatient) => {
        const adaptedPatient = adaptPatientDTO(freshPatient);
        setSelectedPatient(adaptedPatient);
        setPatientRows((current) => current.map((row) => row.id === adaptedPatient.id ? adaptedPatient : row));
      })
      .catch((error: unknown) => {
        handleAuthError(error, clearSession);
        setPageError(toPatientErrorMessage(error, "Unable to refresh patient details."));
      });
  };

  const createBackendPatient = async (payload: PatientPayload) => {
    if (!accessToken) {
      throw new Error("Sign in again to create patients.");
    }

    try {
      const createdPatient = adaptPatientDTO(await createPatient(payload, { accessToken }));
      setPatientRows((current) => [...current, createdPatient]);
      setSelectedPatient(createdPatient);
      setDrawerOpen(true);
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toPatientErrorMessage(error, "Unable to create patient."));
    }
  };

  const updateBackendPatient = async (patient: BackendPatient) => {
    if (!accessToken) {
      throw new Error("Sign in again to edit patients.");
    }
    if (!patient.id) {
      throw new Error("Missing backend patient ID. Refresh the patient list and try again.");
    }

    try {
      const updatedPatient = adaptPatientDTO(await updatePatient(patient.id, toPatientUpdatePayload(patient), { accessToken }));
      setPatientRows((current) => current.map((row) => row.id === updatedPatient.id ? updatedPatient : row));
      setSelectedPatient(updatedPatient);
      return updatedPatient;
    } catch (error) {
      handleAuthError(error, clearSession);
      throw new Error(toPatientErrorMessage(error, "Unable to save patient."));
    }
  };

  const columns: DataColumn<BackendPatient>[] = [
    {
      header: "Patient",
      cell: (patient) => (
        <div className="row">
          <span className="avatar">{initials(fullPatientName(patient))}</span>
          <div><strong>{fullPatientName(patient)}</strong><div className="tiny">{patient.gender}, {patient.age ?? ageFromDate(patient.dateOfBirth)} years</div></div>
        </div>
      ),
    },
    {
      header: "Contact",
      cell: (patient) => (
        <div>{patient.phoneNumber}<div className="tiny">{patient.email}</div></div>
      ),
    },
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
      <PageHeader
        title="Patients"
        subtitle="Search and manage patient records."
        actions={canWritePatients && <Button icon={<Plus size={18} />} onClick={() => setCreateOpen(true)}>Add Patient</Button>}
      />
      <Card>
        {pageError && <div className="alert-card mb-16">{pageError}</div>}
        <div className="filter-card">
          <Input
            icon={<Search size={18} />}
            placeholder="Search by name, phone, national ID/passport..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
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
        <div className="between mb-16">
          <h2 className="card-title">All Patients ({filteredPatients.length})</h2>
        </div>
        {loadingPatients ? (
          <div className="empty-inline">Loading patients...</div>
        ) : (
          <DataTable columns={columns} rows={filteredPatients} getRowKey={(patient) => patient.id ?? patient.patientId} onRowClick={openDrawer} />
        )}
      </Card>
      <PatientProfileDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        patient={selectedPatient}
        canEdit={canWritePatients}
        onSavePatient={updateBackendPatient}
      />
      <PatientCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreate={createBackendPatient}
      />
    </div>
  );
}

function handleAuthError(error: unknown, clearSession: (message?: string) => void) {
  if (isApiError(error) && error.status === 401) {
    clearSession("Your session has expired. Please sign in again.");
  }
}

function toPatientErrorMessage(error: unknown, fallback: string) {
  if (isApiError(error)) {
    if (error.status === 409) {
      return "This patient was updated elsewhere. Please refresh and try again.";
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
