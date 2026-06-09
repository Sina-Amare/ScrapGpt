import type { CrawlScopeMode } from "../types";

export type ScopeModeInfo = {
  label: string;
  description: string;
  confirmLabel: string;
  warnStrong: boolean;
};

const SCOPE_MODE_INFO: Record<CrawlScopeMode, ScopeModeInfo> = {
  CURRENT_PAGE: {
    label: "This page only",
    description: "Fastest and safest. Links on the page will not be crawled.",
    confirmLabel: "Use this page only",
    warnStrong: false,
  },
  PAGINATION: {
    label: "This list across pages",
    description: "Use this when page 2, page 3, or next links continue the same list.",
    confirmLabel: "Confirm list pages",
    warnStrong: false,
  },
  DATASET: {
    label: "This dataset",
    description: "Use this when item/detail pages belong to the same dataset.",
    confirmLabel: "Confirm dataset scope",
    warnStrong: false,
  },
  FULL_SITE: {
    label: "The whole site",
    description: "Use only when you truly want the website explored broadly.",
    confirmLabel: "Confirm whole-site crawl",
    warnStrong: true,
  },
};

export function scopeModeInfo(mode: string): ScopeModeInfo {
  return (
    SCOPE_MODE_INFO[mode as CrawlScopeMode] ?? {
      label: mode,
      description: "",
      confirmLabel: "Confirm scope",
      warnStrong: false,
    }
  );
}

export function scopeModeLabel(mode: string): string {
  return scopeModeInfo(mode).label;
}

export function requiresConfirmation(mode: string): boolean {
  return mode !== "CURRENT_PAGE";
}

export function isUserConfirmed(status: string | undefined): boolean {
  return status === "USER_CONFIRMED";
}

export const SCOPE_MODE_ORDER: CrawlScopeMode[] = [
  "CURRENT_PAGE",
  "PAGINATION",
  "DATASET",
  "FULL_SITE",
];
