import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: ReactNode;
}

export function Button({ variant = "primary", icon, children, className = "", type = "button", ...props }: ButtonProps) {
  return (
    <button className={`btn btn-${variant} ${className}`.trim()} type={type} {...props}>
      {icon}
      {children}
    </button>
  );
}
