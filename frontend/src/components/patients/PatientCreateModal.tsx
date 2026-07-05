import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { PatientPayload } from "../../api/patients";
import type { Gender } from "../../types/models";
import { ageFromDate } from "../../utils/format";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { Select } from "../ui/Select";
import { Textarea } from "../ui/Textarea";

interface PatientCreateModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (patient: PatientPayload) => Promise<void> | void;
}

const bloodGroups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

const emptyForm = {
  firstName: "",
  lastName: "",
  nationalIdOrPassport: "",
  dateOfBirth: "",
  gender: "Male" as Gender,
  phoneNumber: "",
  bloodGroup: "O+",
  medicalConditionsHistory: "",
  insuranceInfo: "",
  emergencyContact: "",
  address: "",
};

export function PatientCreateModal({ open, onClose, onCreate }: PatientCreateModalProps) {
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(emptyForm);
      setError("");
      setSaving(false);
    }
  }, [open]);

  const updateField = (field: keyof typeof form, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSaving(true);

    try {
      await onCreate({
        firstName: form.firstName,
        lastName: form.lastName,
        nationalIdOrPassport: form.nationalIdOrPassport,
        dateOfBirth: form.dateOfBirth,
        gender: form.gender,
        phoneNumber: form.phoneNumber,
        medicalConditionsHistory: form.medicalConditionsHistory,
        bloodGroup: form.bloodGroup,
        insuranceInfo: form.insuranceInfo,
        emergencyContact: form.emergencyContact,
        address: form.address,
      });
      onClose();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to create patient.");
    } finally {
      setSaving(false);
    }
  };

  const calculatedAge = form.dateOfBirth ? `${ageFromDate(form.dateOfBirth)} years` : "Select date of birth";

  return (
    <Modal
      title="Add Patient"
      subtitle="Create the initial patient record."
      open={open}
      onClose={onClose}
      width={760}
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button type="submit" form="patient-create-form" disabled={saving}>{saving ? "Creating..." : "Create Patient"}</Button>
        </>
      }
    >
      <form id="patient-create-form" className="stack" onSubmit={handleSubmit}>
        {error && <div className="alert-card">{error}</div>}
        <section className="soft-panel">
          <h3 className="card-title">Personal Information</h3>
          <div className="field-grid mt-16">
            <Input label="First Name" required value={form.firstName} onChange={(event) => updateField("firstName", event.target.value)} />
            <Input label="Last Name" required value={form.lastName} onChange={(event) => updateField("lastName", event.target.value)} />
            <Input label="National ID / Passport" required value={form.nationalIdOrPassport} onChange={(event) => updateField("nationalIdOrPassport", event.target.value)} />
            <Input label="Date of Birth" required type="date" value={form.dateOfBirth} onChange={(event) => updateField("dateOfBirth", event.target.value)} />
            <Input label="Age" value={calculatedAge} readOnly />
            <Select label="Sex" options={["Male", "Female"]} value={form.gender} onChange={(event) => updateField("gender", event.target.value as Gender)} />
          </div>
        </section>

        <section className="soft-panel">
          <h3 className="card-title">Contact Information</h3>
          <div className="field-grid mt-16">
            <Input label="Phone Number" required value={form.phoneNumber} onChange={(event) => updateField("phoneNumber", event.target.value)} />
            <Input className="span-2" label="Emergency Contact" required value={form.emergencyContact} onChange={(event) => updateField("emergencyContact", event.target.value)} />
            <Input className="span-2" label="Address" required value={form.address} onChange={(event) => updateField("address", event.target.value)} />
          </div>
        </section>

        <section className="soft-panel">
          <h3 className="card-title">Medical / Administrative Information</h3>
          <div className="field-grid mt-16">
            <Select label="Blood Group" options={bloodGroups} value={form.bloodGroup} onChange={(event) => updateField("bloodGroup", event.target.value)} />
            <Input label="Insurance Info" required value={form.insuranceInfo} onChange={(event) => updateField("insuranceInfo", event.target.value)} />
            <Textarea className="span-2" label="Medical Conditions History" required value={form.medicalConditionsHistory} onChange={(event) => updateField("medicalConditionsHistory", event.target.value)} />
          </div>
        </section>
      </form>
    </Modal>
  );
}
