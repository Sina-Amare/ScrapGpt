import { Badge } from "./Badge";

// ---------------------------------------------------------------------------
// Type guard for the ContentAnalysisResult schema produced by llm_processor
// ---------------------------------------------------------------------------

type ContentAnalysisResult = {
  summary: string;
  key_points: string[];
  data_type: string;
  word_count: number;
};

function isContentAnalysis(
  r: Record<string, unknown>
): r is ContentAnalysisResult {
  return (
    typeof r.summary === "string" &&
    Array.isArray(r.key_points) &&
    typeof r.data_type === "string" &&
    typeof r.word_count === "number"
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TaskResultPanel({
  result,
  contentLength
}: {
  result: Record<string, unknown> | null;
  contentLength?: number | null;
}) {
  if (!result) return null;

  if (isContentAnalysis(result)) {
    return (
      <div className="grid gap-5">
        {/* Meta stats */}
        <div className="flex flex-wrap items-center gap-3">
          <Badge>{result.data_type}</Badge>
          {result.word_count > 0 ? (
            <span className="text-xs text-muted">
              {result.word_count.toLocaleString()} words analyzed
            </span>
          ) : null}
          {contentLength ? (
            <span className="text-xs text-muted">
              · {contentLength.toLocaleString()} chars scraped
            </span>
          ) : null}
        </div>

        {/* Summary */}
        <div>
          <p className="mb-1.5 text-xs font-bold uppercase tracking-widest text-muted">
            Summary
          </p>
          <p className="text-sm leading-7 text-ink">{result.summary}</p>
        </div>

        {/* Key points */}
        {result.key_points.length > 0 ? (
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-widest text-muted">
              Key Points
            </p>
            <ul className="grid gap-2">
              {result.key_points.map((point, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-ink">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-teal" />
                  <span className="leading-6">{point}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    );
  }

  // Fallback: unknown schema — render raw JSON
  return (
    <pre className="max-h-72 overflow-auto rounded-xl border border-line bg-porcelain p-4 text-xs leading-6 text-ink">
      {JSON.stringify(result, null, 2)}
    </pre>
  );
}
