import type { ReactNode } from "react";
import { Card } from "./Card";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  hint?: string;
}

export function StatCard({ label, value, icon, hint }: StatCardProps) {
  return (
    <Card className="stat-card">
      <div className="stat-card-copy">
        <div className="stat-card-head">
          <p className="stat-label">{label}</p>
          {icon && <span className="stat-icon">{icon}</span>}
        </div>
        <div className="metric">{value}</div>
        {hint && <p className="tiny">{hint}</p>}
      </div>
    </Card>
  );
}
