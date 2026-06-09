export type QualityState = "good" | "needs_review" | "risky" | "unknown";

export type QualityStateInfo = {
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
};

const QUALITY_STATE_INFO: Record<QualityState, QualityStateInfo> = {
  good: { label: "Looks reliable", tone: "success" },
  needs_review: { label: "Review before using", tone: "warning" },
  risky: { label: "Results may be incomplete", tone: "danger" },
  unknown: { label: "Quality not available yet", tone: "neutral" },
};

export function qualityStateInfo(overall: string): QualityStateInfo {
  return QUALITY_STATE_INFO[overall as QualityState] ?? QUALITY_STATE_INFO.unknown;
}

export function isScopeNotConfirmedError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const detail = (error as { detail?: unknown }).detail;
  if (detail && typeof detail === "object") {
    const nested = (detail as Record<string, unknown>).detail;
    if (nested && typeof nested === "object") {
      return (nested as Record<string, unknown>).error_code === "SCOPE_NOT_CONFIRMED";
    }
    return (detail as Record<string, unknown>).error_code === "SCOPE_NOT_CONFIRMED";
  }
  return false;
}
