import { useEffect } from "react";
import type { MouseEvent, ReactNode } from "react";
import { X } from "lucide-react";

interface ModalProps {
  title: string;
  subtitle?: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  width?: number;
  footer?: ReactNode;
}

export function Modal({ title, subtitle, open, onClose, children, width = 680, footer }: ModalProps) {
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
      <section className="modal" style={{ width: `min(${width}px, calc(100vw - 32px))` }} role="dialog" aria-modal="true" aria-label={title}>
        <header className="modal-header">
          <div>
            <h2 className="card-title">{title}</h2>
            {subtitle && <p className="tiny">{subtitle}</p>}
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-footer">{footer}</footer>}
      </section>
    </div>
  );
}
