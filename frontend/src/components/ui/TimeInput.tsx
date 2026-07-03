import type { InputHTMLAttributes } from "react";
import { useId } from "react";
import { timePresetOptions } from "../../utils/shifts";

interface TimeInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

export function TimeInput({ label, id, className = "", step = 1800, ...props }: TimeInputProps) {
  const generatedId = useId();
  const inputId = id ?? props.name ?? label?.toLowerCase().replace(/\s+/g, "-") ?? generatedId;
  const listId = `${inputId}-time-options`;

  return (
    <label className={`form-field ${className}`.trim()} htmlFor={inputId}>
      {label && <span>{label}</span>}
      <div className="input-wrap">
        <input id={inputId} type="time" step={step} list={listId} {...props} />
      </div>
      <datalist id={listId}>
        {timePresetOptions.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </label>
  );
}
