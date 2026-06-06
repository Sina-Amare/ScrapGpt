import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton } from "../components/ui/Skeleton";
import { api } from "../lib/api";

const checks = [
  { key: "health", label: "Health", path: "/health" as const },
  { key: "live", label: "Live", path: "/health/live" as const },
  { key: "ready", label: "Ready", path: "/health/ready" as const }
];

function HealthCard({ check }: { check: (typeof checks)[number] }) {
  const query = useQuery({
    queryKey: ["health", check.key],
    queryFn: () => api.getHealth(check.path),
    retry: 1
  });

  return (
    <section className="rounded-md border border-line bg-surface p-5 shadow-panel">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-bold text-ink">{check.label}</h2>
        <Badge tone={query.isSuccess ? "success" : query.isError ? "danger" : "warning"}>
          {query.isSuccess ? "OK" : query.isError ? "Failed" : "Loading"}
        </Badge>
      </div>
      {query.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <pre className="max-h-80 overflow-auto rounded-md border border-line bg-porcelain p-4 text-xs leading-6 text-ink">
          {JSON.stringify(query.data ?? query.error, null, 2)}
        </pre>
      )}
    </section>
  );
}

export function HealthPage() {
  const queryClient = useQueryClient();
  return (
    <>
      <PageHeader title="Health" eyebrow="Backend status">
        <Button
          variant="secondary"
          onClick={() => queryClient.invalidateQueries({ queryKey: ["health"] })}
        >
          <RefreshCw className="h-4 w-4" />
          Refresh all
        </Button>
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-3">
        {checks.map((check) => (
          <HealthCard key={check.key} check={check} />
        ))}
      </div>
    </>
  );
}
