import type { TextareaHTMLAttributes } from "react";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export function Textarea({ label, id, className = "", ...props }: TextareaProps) {
  const textareaId = id ?? props.name ?? label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <label className={`form-field ${className}`.trim()} htmlFor={textareaId}>
      {label && <span>{label}</span>}
      <textarea id={textareaId} {...props} />
    </label>
  );
}
