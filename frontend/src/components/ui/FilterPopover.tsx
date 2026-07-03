import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Button } from "./Button";

interface FilterPopoverProps {
  children: ReactNode;
  activeCount?: number;
}

export function FilterPopover({ children, activeCount = 0 }: FilterPopoverProps) {
  const [open, setOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const reactId = useId();
  const popoverId = `${reactId}-filter-popover`;

  useEffect(() => {
    if (!open) return;

    const closeOnOutside = (event: MouseEvent) => {
      if (!popoverRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("mousedown", closeOnOutside);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("mousedown", closeOnOutside);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className="filter-popover-shell" ref={popoverRef}>
      <Button
        variant="secondary"
        icon={<SlidersHorizontal size={17} />}
        type="button"
        aria-expanded={open}
        aria-controls={open ? popoverId : undefined}
        onClick={() => setOpen((current) => !current)}
      >
        Filter{activeCount > 0 ? ` (${activeCount})` : ""}
      </Button>
      {open && (
        <div className="filter-popover" id={popoverId} role="dialog" aria-label="Filter options">
          {children}
        </div>
      )}
    </div>
  );
}
