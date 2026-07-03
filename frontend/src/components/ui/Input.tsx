import type { InputHTMLAttributes, ReactNode } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  icon?: ReactNode;
}

export function Input({ label, icon, id, className = "", ...props }: InputProps) {
  const inputId = id ?? props.name ?? label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <label className={`form-field ${className}`.trim()} htmlFor={inputId}>
      {label && <span>{label}</span>}
      <div className="input-wrap">
        {icon}
        <input id={inputId} {...props} />
      </div>
    </label>
  );
}
