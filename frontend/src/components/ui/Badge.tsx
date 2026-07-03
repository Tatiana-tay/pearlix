import type { ReactNode } from "react";

export type BadgeTone =
  | "primary"
  | "secondary"
  | "teal"
  | "green"
  | "warning"
  | "danger"
  | "muted"
  | "purple"
  | "indigo"
  | "orange";

interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
}

export function Badge({ children, tone = "primary" }: BadgeProps) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
