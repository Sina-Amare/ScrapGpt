import { useQuery } from "@tanstack/react-query";
import { Calendar, ExternalLink, FileText, Globe } from "lucide-react";
import { Alert } from "./Alert";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { Skeleton } from "./Skeleton";
import { TaskResultPanel } from "./TaskResultPanel";
import { api } from "../../lib/api";
import { stateTone } from "../../lib/taskPolling";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function TaskDetailDialog({
  taskId,
  onClose
}: {
  taskId: number;
  onClose: () => void;
}) {
  const { data: task, isLoading, error } = useQuery({
    queryKey: ["task-detail", taskId],
    queryFn: () => api.getTask(taskId),
    retry: false
  });

  return (
    <Dialog title={`Task #${taskId} Details`} onClose={onClose}>
      <div className="grid gap-5">
        {isLoading ? (
          <div className="grid gap-4 py-4">
            <div className="flex items-center gap-2">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-6 w-16" />
            </div>
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : error || !task ? (
          <div className="grid gap-4">
            <Alert tone="danger">
              {error instanceof Error ? error.message : "Failed to load task details."}
            </Alert>
            <div className="flex justify-end">
              <Button variant="secondary" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid gap-5">
            {/* Metadata Summary */}
            <div className="rounded-lg border border-line bg-porcelain p-4">
              <div className="grid gap-3 text-sm md:grid-cols-2">
                <div className="flex items-start gap-2.5 min-w-0">
                  <Globe className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                  <div className="min-w-0">
                    <span className="block text-xs font-semibold text-muted">Target URL</span>
                    <a
                      href={task.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 break-all text-xs font-medium text-teal hover:underline"
                    >
                      {task.url}
                      <ExternalLink className="h-3 w-3 shrink-0" />
                    </a>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <Calendar className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                  <div>
                    <span className="block text-xs font-semibold text-muted">Created Date</span>
                    <span className="text-xs text-ink">{formatDate(task.created_at)}</span>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                  <div>
                    <span className="block text-xs font-semibold text-muted">Raw Page Content</span>
                    <span className="text-xs text-ink">
                      {task.content_length
                        ? `${task.content_length.toLocaleString()} characters`
                        : "—"}
                    </span>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <div className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <span className="block text-xs font-semibold text-muted mb-1">State</span>
                    <Badge tone={stateTone(task.state)}>{task.state}</Badge>
                  </div>
                </div>
              </div>
            </div>

            {/* Error Message if failed */}
            {task.error ? (
              <div className="grid gap-1">
                <span className="text-xs font-bold uppercase tracking-widest text-muted">
                  Failure Reason
                </span>
                <Alert tone="danger">{task.error}</Alert>
              </div>
            ) : null}

            {/* Results Block */}
            {task.state === "COMPLETED" && task.result ? (
              <div className="rounded-xl border border-line bg-porcelain p-5">
                <p className="mb-4 text-xs font-bold uppercase tracking-widest text-muted">
                  AI Analysis Results
                </p>
                <TaskResultPanel
                  result={task.result}
                  contentLength={task.content_length}
                />
              </div>
            ) : task.state !== "COMPLETED" && task.state !== "FAILED" ? (
              <div className="rounded-xl border border-dashed border-line bg-porcelain p-6 text-center text-sm text-muted">
                Pipeline is active. The AI analysis will render once completed.
              </div>
            ) : !task.error ? (
              <div className="rounded-xl border border-dashed border-line bg-porcelain p-6 text-center text-sm text-muted">
                No analysis results available for this task.
              </div>
            ) : null}

            {/* Footer actions */}
            <div className="flex justify-end mt-2 pt-4 border-t border-line">
              <Button variant="secondary" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        )}
      </div>
    </Dialog>
  );
}
