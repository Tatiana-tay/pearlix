import type { ReactNode } from "react";
import { AlertCircle, FileSearch, LoaderCircle, ShieldAlert } from "lucide-react";

type EmptyStateKind = "empty" | "loading" | "permission" | "error" | "search";

interface EmptyStateProps {
  kind?: EmptyStateKind;
  title: string;
  description: string;
  action?: ReactNode;
}

const icons = {
  empty: FileSearch,
  loading: LoaderCircle,
  permission: ShieldAlert,
  error: AlertCircle,
  search: FileSearch,
};

export function EmptyState({ kind = "empty", title, description, action }: EmptyStateProps) {
  const Icon = icons[kind];
  return (
    <div className="empty-state">
      <Icon size={32} className={kind === "loading" ? "spin" : ""} />
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
