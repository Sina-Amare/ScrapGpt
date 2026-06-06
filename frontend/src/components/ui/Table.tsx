import { ReactNode } from "react";

export function Table({
  headings,
  children
}: {
  headings: string[];
  children: ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-porcelain text-xs uppercase text-muted">
          <tr>
            {headings.map((heading) => (
              <th key={heading} className="px-4 py-3 font-bold">
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}
