import { AlertCircle, CheckCircle2, HelpCircle, XCircle } from "lucide-react";
import type { ExtractionQuality } from "../../types";
import { qualityStateInfo } from "../../lib/qualityCopy";

type Props = {
  quality: ExtractionQuality | null | undefined;
};

function QualityIcon({ overall }: { overall: string }) {
  if (overall === "good") return <CheckCircle2 className="h-5 w-5 text-success" />;
  if (overall === "needs_review") return <AlertCircle className="h-5 w-5 text-warning" />;
  if (overall === "risky") return <XCircle className="h-5 w-5 text-danger" />;
  return <HelpCircle className="h-5 w-5 text-muted" />;
}

export function TrustSummaryPanel({ quality }: Props) {
  if (!quality) {
    return (
      <div className="rounded-lg border border-line bg-porcelain p-4 text-sm text-muted">
        Quality not available yet. Run extraction to see trust signals.
      </div>
    );
  }

  const info = qualityStateInfo(quality.overall);
  const fieldNames = Object.keys(quality.field_success_rates);

  return (
    <div className="grid gap-4">
      <div className={[
        "flex items-center gap-3 rounded-lg border px-4 py-3",
        info.tone === "success" ? "border-success/40 bg-success/10" :
        info.tone === "warning" ? "border-warning/40 bg-warning/10" :
        info.tone === "danger" ? "border-danger/40 bg-danger/10" :
        "border-line bg-porcelain",
      ].join(" ")}>
        <QualityIcon overall={quality.overall} />
        <span className="font-semibold text-ink">{info.label}</span>
      </div>

      {fieldNames.length ? (
        <div>
          <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">Field coverage</h4>
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-porcelain text-left text-xs font-bold uppercase tracking-wide text-muted">
                  <th className="px-4 py-2">Field</th>
                  <th className="px-4 py-2">Found on records</th>
                  <th className="px-4 py-2">Missing from records</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface">
                {fieldNames.map((field) => {
                  const success = quality.field_success_rates[field] ?? 0;
                  const missing = quality.missing_field_rates[field] ?? 0;
                  const successPct = Math.round(success * 100);
                  const missingPct = Math.round(missing * 100);
                  const isLow = success < 0.7;
                  return (
                    <tr key={field} className="hover:bg-teal-soft/20">
                      <td className="px-4 py-2.5 font-medium text-ink">{field}</td>
                      <td className={["px-4 py-2.5", isLow ? "text-warning" : "text-success"].join(" ")}>
                        {successPct}%
                      </td>
                      <td className={["px-4 py-2.5", missingPct > 30 ? "text-warning" : "text-muted"].join(" ")}>
                        {missingPct}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-muted/70">
            Quality is based on extracted records. It may not detect pages that were skipped or
            records that could not be formed.
          </p>
        </div>
      ) : null}

      {quality.warnings.length ? (
        <div>
          <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">Warnings</h4>
          <ul className="grid gap-1">
            {quality.warnings.map((w, i) => (
              <li key={i} className="flex items-start gap-2 rounded-md bg-porcelain px-3 py-2 text-sm text-muted">
                <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-warning" />
                {String((w as { message?: unknown }).message ?? JSON.stringify(w))}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
