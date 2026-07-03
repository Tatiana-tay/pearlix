import { useState } from "react";
import type { ReactNode } from "react";
import { EmptyState } from "../ui/EmptyState";

export interface DataColumn<T> {
  header: string;
  cell: (row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: DataColumn<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  onRowDoubleClick?: (row: T) => void;
  emptyTitle?: string;
}

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  onRowClick,
  onRowDoubleClick,
  emptyTitle = "No records found",
}: DataTableProps<T>) {
  const [lastTap, setLastTap] = useState<{ key: string; at: number } | null>(null);

  if (rows.length === 0) {
    return <EmptyState kind="search" title={emptyTitle} description="Try clearing the search or changing the filters." />;
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.header} className={column.className}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const rowKey = getRowKey(row);
            return (
            <tr
              key={rowKey}
              className={onRowClick || onRowDoubleClick ? "clickable" : ""}
              role={onRowClick || onRowDoubleClick ? "button" : undefined}
              tabIndex={onRowClick || onRowDoubleClick ? 0 : undefined}
              onClick={() => onRowClick?.(row)}
              onDoubleClick={() => onRowDoubleClick?.(row)}
              onKeyDown={(event) => {
                if (!onRowClick && !onRowDoubleClick) return;
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  (onRowClick ?? onRowDoubleClick)?.(row);
                }
              }}
              onTouchEnd={() => {
                if (!onRowDoubleClick) return;
                const now = Date.now();
                if (lastTap?.key === rowKey && now - lastTap.at < 360) {
                  onRowDoubleClick(row);
                }
                setLastTap({ key: rowKey, at: now });
              }}
            >
              {columns.map((column) => (
                <td key={column.header} className={column.className}>
                  {column.cell(row)}
                </td>
              ))}
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
