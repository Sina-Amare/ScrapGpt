import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, RefreshCw, Search, ServerCog, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton } from "../components/ui/Skeleton";
import { StatTile } from "../components/ui/StatTile";
import { Table } from "../components/ui/Table";
import { TaskResultPanel } from "../components/ui/TaskResultPanel";
import { ConfirmDeleteTaskDialog } from "../components/ui/ConfirmDeleteTaskDialog";
import { TaskDetailDialog } from "../components/ui/TaskDetailDialog";
import { ApiError, api } from "../lib/api";
import { shouldPollTask, stateTone } from "../lib/taskPolling";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function truncateUrl(url: string, max = 52): string {
  return url.length > max ? url.slice(0, max) + "…" : url;
}

export function DashboardPage() {
  const [failureCount, setFailureCount] = useState(0);
  const [currentNotFound, setCurrentNotFound] = useState(false);

  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [deleteTaskTarget, setDeleteTaskTarget] = useState<{ id: number; url: string } | null>(null);

  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: api.deleteTask,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["task-history"] });
      void queryClient.invalidateQueries({ queryKey: ["current-task"] });
      setDeleteTaskTarget(null);
    },
    onError: (err) => {
      alert(err instanceof Error ? err.message : "Failed to delete task");
    }
  });

  const task = useQuery({
    queryKey: ["current-task"],
    queryFn: async () => {
      try {
        const response = await api.getCurrentTask();
        setCurrentNotFound(false);
        setFailureCount(0);
        return response;
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          setCurrentNotFound(true);
          return null;
        }
        setFailureCount((count) => count + 1);
        throw error;
      }
    },
    refetchInterval: (query) =>
      shouldPollTask(query.state.data, failureCount, currentNotFound) ? 2000 : false,
    retry: false
  });

  const history = useQuery({
    queryKey: ["task-history"],
    queryFn: api.listTasks,
    retry: false
  });

  return (
    <>
      <PageHeader title="Dashboard" eyebrow="Current work">
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              void task.refetch();
              void history.refetch();
            }}
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Link to="/scrape/new">
            <Button>
              <Search className="h-4 w-4" />
              New scrape
            </Button>
          </Link>
        </div>
      </PageHeader>

      {/* Stat tiles */}
      <div className="grid gap-4 md:grid-cols-3">
        <StatTile
          label="Active task"
          value={task.data ? `#${task.data.task_id}` : "None"}
          icon={<ServerCog className="h-5 w-5" />}
        />
        <StatTile
          label="Task state"
          value={
            task.data ? (
              <Badge tone={stateTone(task.data.state)}>{task.data.state}</Badge>
            ) : (
              <Badge>No active task</Badge>
            )
          }
        />
        <StatTile
          label="Content scraped"
          value={
            task.data?.content_length
              ? `${(task.data.content_length / 1000).toFixed(1)} KB`
              : "—"
          }
        />
      </div>

      {/* Active task detail */}
      <section className="mt-6 rounded-xl border border-line bg-surface p-6 shadow-panel">
        {task.isLoading ? (
          <div className="grid gap-3">
            <Skeleton className="h-8 w-52" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : task.error && failureCount >= 3 ? (
          <Alert tone="danger">
            Task polling paused after repeated failures. Use refresh to try again.
          </Alert>
        ) : !task.data ? (
          <div className="grid gap-3 py-10 text-center">
            <h2 className="text-lg font-bold text-ink">No active scrape task</h2>
            <p className="mx-auto max-w-md text-sm text-muted">
              Start a URL scrape to watch the pipeline move through its backend states.
            </p>
            <div>
              <Link to="/scrape/new">
                <Button>Start scrape</Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid gap-5">
            {/* Header */}
            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div className="min-w-0">
                <h2 className="text-lg font-bold text-ink">
                  Task #{task.data.task_id}
                </h2>
                <p className="mt-0.5 break-all text-sm text-muted">{task.data.url}</p>
              </div>
              <Badge tone={stateTone(task.data.state)}>{task.data.state}</Badge>
            </div>

            {task.data.error ? <Alert tone="danger">{task.data.error}</Alert> : null}

            {/* Content length info */}
            {task.data.content_length ? (
              <div className="rounded-lg border border-line bg-porcelain px-4 py-2.5">
                <p className="text-xs font-semibold text-muted">
                  Scraped{" "}
                  <span className="text-ink">
                    {task.data.content_length.toLocaleString()}
                  </span>{" "}
                  characters of page text
                </p>
              </div>
            ) : null}

            {/* Structured result or raw JSON */}
            {task.data.state === "COMPLETED" && task.data.result ? (
              <div className="rounded-xl border border-line bg-porcelain p-5">
                <p className="mb-4 text-xs font-bold uppercase tracking-widest text-muted">
                  AI Analysis
                </p>
                <TaskResultPanel
                  result={task.data.result}
                  contentLength={task.data.content_length}
                />
              </div>
            ) : task.data.state !== "COMPLETED" && task.data.state !== "FAILED" ? (
              <div className="rounded-xl border border-dashed border-line bg-porcelain p-5 text-center text-sm text-muted">
                Pipeline running — result will appear here when complete.
              </div>
            ) : null}
          </div>
        )}
      </section>

      {/* Task history */}
      <section className="mt-8">
        <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-muted">
          Task history
        </h2>

        {history.isLoading ? (
          <div className="grid gap-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : history.error ? (
          <Alert tone="danger">Could not load task history.</Alert>
        ) : !history.data?.length ? (
          <div className="rounded-xl border border-line bg-surface p-8 text-center shadow-panel">
            <p className="text-sm text-muted">
              No tasks yet. Run your first scrape to see history here.
            </p>
          </div>
        ) : (
          <Table headings={["#", "URL", "State", "Date", "Actions"]}>
            {history.data.map((t) => (
              <tr key={t.task_id} className="transition-colors hover:bg-teal-soft/40">
                <td className="px-4 py-3 font-mono text-sm font-semibold text-ink">
                  {t.task_id}
                </td>
                <td className="max-w-xs px-4 py-3">
                  <span
                    className="block truncate text-sm text-muted"
                    title={t.url}
                  >
                    {truncateUrl(t.url)}
                  </span>
                  {t.error ? (
                    <span
                      className="mt-0.5 block truncate text-xs text-red-500"
                      title={t.error}
                    >
                      {t.error}
                    </span>
                  ) : null}
                </td>
                <td className="px-4 py-3">
                  <Badge tone={stateTone(t.state)}>{t.state}</Badge>
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-sm text-muted">
                  {formatDate(t.created_at)}
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  <div className="flex gap-2">
                    <button
                      onClick={() => setSelectedTaskId(t.task_id)}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line bg-surface text-muted hover:border-teal hover:text-teal hover:bg-teal-soft transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-teal"
                      title="View Details"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => setDeleteTaskTarget({ id: t.task_id, url: t.url })}
                      disabled={t.state !== "COMPLETED" && t.state !== "FAILED"}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line bg-surface text-red-500/70 hover:border-danger hover:text-danger hover:bg-red-50 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-danger disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-surface disabled:hover:border-line disabled:hover:text-red-500/50"
                      title="Delete Task"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </section>

      {/* Task detail viewer dialog */}
      {selectedTaskId !== null ? (
        <TaskDetailDialog
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
        />
      ) : null}

      {/* Delete confirmation dialog */}
      {deleteTaskTarget !== null ? (
        <ConfirmDeleteTaskDialog
          taskId={deleteTaskTarget.id}
          url={deleteTaskTarget.url}
          onCancel={() => setDeleteTaskTarget(null)}
          onConfirm={() => deleteMutation.mutate(deleteTaskTarget.id)}
          submitting={deleteMutation.isPending}
        />
      ) : null}
    </>
  );
}
