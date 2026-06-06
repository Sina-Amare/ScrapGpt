import { ReactNode } from "react";
import { X } from "lucide-react";

export function Dialog({
  title,
  children,
  onClose
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/35 p-4">
      <section className="w-full max-w-xl rounded-md border border-line bg-surface shadow-panel flex flex-col max-h-[90vh]">
        <header className="flex shrink-0 items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-porcelain hover:text-ink transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-teal"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="p-5 overflow-y-auto flex-1">{children}</div>
      </section>
    </div>
  );
}
