import type { BackendPatient, Gender } from "../../types/models";
import { ageFromDate } from "../../utils/format";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { Textarea } from "../ui/Textarea";

interface PatientFormProps {
  patient: BackendPatient;
  editable?: boolean;
  onChange?: (patient: BackendPatient) => void;
}

const bloodGroups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

export function PatientForm({ patient, editable = false, onChange }: PatientFormProps) {
  const updateField = (field: keyof BackendPatient, value: string) => {
    onChange?.({ ...patient, [field]: value });
  };

  if (!editable) {
    return (
      <div className="stack">
        <section className="soft-panel">
          <h3 className="card-title">Personal Identification</h3>
          <div className="field-grid mt-16">
            <ReadOnlyField label="Patient ID" value={patient.patientId} />
            <ReadOnlyField label="Blood Group" value={patient.bloodGroup} />
            <ReadOnlyField label="First Name" value={patient.firstName} />
            <ReadOnlyField label="Last Name" value={patient.lastName} />
            <ReadOnlyField label="National ID / Passport" value={patient.nationalIdOrPassport} />
            <ReadOnlyField label="Date of Birth" value={patient.dateOfBirth} />
            <ReadOnlyField label="Age" value={`${ageFromDate(patient.dateOfBirth)} years`} />
            <ReadOnlyField label="Sex" value={patient.gender} />
          </div>
        </section>

        <section className="soft-panel">
          <h3 className="card-title">Contact Details</h3>
          <div className="field-grid mt-16">
            <ReadOnlyField label="Phone" value={patient.phoneNumber} />
            <ReadOnlyField label="Email" value={patient.email ?? ""} />
            <ReadOnlyField className="span-2" label="Address" value={patient.address} />
            <ReadOnlyField className="span-2" label="Emergency Contact" value={patient.emergencyContact} />
          </div>
        </section>

        <section className="soft-panel">
          <h3 className="card-title">Insurance Details</h3>
          <div className="mt-16">
            <ReadOnlyField label="Insurance Info" value={patient.insuranceInfo} />
          </div>
        </section>

        <section className="soft-panel">
          <h3 className="card-title">Medical Conditions History</h3>
          <ReadOnlyField className="mt-16" label="History" value={patient.medicalConditionsHistory} multiline />
        </section>
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="soft-panel">
        <h3 className="card-title">Personal Identification</h3>
        <div className="field-grid mt-16">
          <Input label="Patient ID" value={patient.patientId} readOnly />
          <Select label="Blood Group" options={bloodGroups} value={patient.bloodGroup || "O+"} onChange={(event) => updateField("bloodGroup", event.target.value)} />
          <Input label="First Name" value={patient.firstName} onChange={(event) => updateField("firstName", event.target.value)} />
          <Input label="Last Name" value={patient.lastName} onChange={(event) => updateField("lastName", event.target.value)} />
          <Input label="National ID / Passport" value={patient.nationalIdOrPassport} onChange={(event) => updateField("nationalIdOrPassport", event.target.value)} />
          <Input label="Date of Birth" type="date" value={patient.dateOfBirth} onChange={(event) => updateField("dateOfBirth", event.target.value)} />
          <Input label="Age" value={`${ageFromDate(patient.dateOfBirth)} years`} readOnly />
          <Select label="Sex" options={["Male", "Female"]} value={patient.gender} onChange={(event) => updateField("gender", event.target.value as Gender)} />
        </div>
      </section>

      <section className="soft-panel">
        <h3 className="card-title">Contact Details</h3>
        <div className="field-grid mt-16">
          <Input label="Phone" value={patient.phoneNumber} onChange={(event) => updateField("phoneNumber", event.target.value)} />
          <Input label="Email" value={patient.email ?? ""} onChange={(event) => updateField("email", event.target.value)} />
          <Input className="span-2" label="Address" value={patient.address} onChange={(event) => updateField("address", event.target.value)} />
          <Input className="span-2" label="Emergency Contact" value={patient.emergencyContact} onChange={(event) => updateField("emergencyContact", event.target.value)} />
        </div>
      </section>

      <section className="soft-panel">
        <h3 className="card-title">Insurance Details</h3>
        <div className="mt-16">
          <Input label="Insurance Info" value={patient.insuranceInfo} onChange={(event) => updateField("insuranceInfo", event.target.value)} />
        </div>
      </section>

      <section className="soft-panel">
        <h3 className="card-title">Medical Conditions History</h3>
        <div className="mt-16">
          <Textarea label="History" value={patient.medicalConditionsHistory} onChange={(event) => updateField("medicalConditionsHistory", event.target.value)} />
        </div>
      </section>
    </div>
  );
}

function ReadOnlyField({ label, value, className = "", multiline = false }: { label: string; value?: string; className?: string; multiline?: boolean }) {
  return (
    <div className={`readonly-field ${multiline ? "readonly-field-multiline" : ""} ${className}`.trim()}>
      <span>{label}</span>
      <strong>{value || "Not set"}</strong>
    </div>
  );
}
