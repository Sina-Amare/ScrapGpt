import type { FieldSpec } from "../types";

/**
 * Produce a stable column list for the results table.
 *
 * Priority:
 * 1. Selected field names from the spec (stable, spec-ordered).
 * 2. Extra keys seen in the current page rows that are not already in the spec.
 *
 * This prevents the column set from jumping around as users page through
 * records, and keeps expected fields visible even when a page has no values
 * for them.
 */
export function buildColumns(
  specFields: FieldSpec[] | undefined | null,
  pageColumns: string[]
): string[] {
  const specNames: string[] = [];
  const specSet = new Set<string>();

  for (const field of specFields ?? []) {
    if (!field.selected) continue;
    const name = field.user_label ?? field.label ?? field.name ?? "";
    if (name && !specSet.has(name)) {
      specNames.push(name);
      specSet.add(name);
    }
  }

  const extras = pageColumns.filter((col) => !specSet.has(col));
  return [...specNames, ...extras];
}
