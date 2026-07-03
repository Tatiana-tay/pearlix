import type { SelectHTMLAttributes } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: string[];
}

export function Select({ label, id, options, className = "", ...props }: SelectProps) {
  const selectId = id ?? props.name ?? label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <label className={`form-field ${className}`.trim()} htmlFor={selectId}>
      {label && <span>{label}</span>}
      <select id={selectId} {...props}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
