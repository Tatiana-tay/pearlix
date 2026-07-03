import type { BackendAIResultFinding } from "../../types/models";

interface AiFindingsTableProps {
  findings: BackendAIResultFinding[];
  compact?: boolean;
}

export function AiFindingsTable({ findings, compact = false }: AiFindingsTableProps) {
  if (findings.length === 0) {
    return <div className="empty-inline">No AI findings to display.</div>;
  }

  return (
    <div className={compact ? "table-wrap compact-table" : "table-wrap"}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Tooth ID</th>
            <th>Finding</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => (
            <tr key={finding.findingId}>
              <td>{finding.fdiToothId}</td>
              <td>{finding.diseaseLabel}</td>
              <td>{Math.round(finding.confidenceScore * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
