import { useEffect } from "react";
import type { MouseEvent, ReactNode } from "react";
import { X } from "lucide-react";

interface DrawerProps {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  width?: number;
}

export function Drawer({ title, open, onClose, children, width = 1040 }: DrawerProps) {
  useEffect(() => {
    if (!open) return;

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const closeOnBackdrop = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <div className="overlay" role="presentation" onMouseDown={closeOnBackdrop}>
      <section className="drawer-modal" style={{ width: `min(${width}px, calc(100vw - 32px))` }} role="dialog" aria-modal="true" aria-label={title}>
        <button className="drawer-close icon-button" type="button" onClick={onClose} aria-label="Close drawer">
          <X size={18} />
        </button>
        {children}
      </section>
    </div>
  );
}
