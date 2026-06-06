import { ReactNode } from "react";

export function PageHeader({
  title,
  eyebrow,
  children
}: {
  title: string;
  eyebrow?: string;
  children?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 border-b border-line pb-5 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow ? (
          <p className="mb-1 text-xs font-bold uppercase tracking-wide text-teal">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-2xl font-bold text-ink">{title}</h1>
      </div>
      {children}
    </div>
  );
}
