import { ReactNode } from "react";

export function StatTile({
  label,
  value,
  icon
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="rounded-md border border-line bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-muted">{label}</p>
        {icon ? <div className="text-teal">{icon}</div> : null}
      </div>
      <div className="mt-2 text-xl font-bold text-ink">{value}</div>
    </div>
  );
}
