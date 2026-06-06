import { Dialog } from "./Dialog";
import { Button } from "./Button";

export function ConfirmDeleteTaskDialog({
  taskId,
  url,
  onCancel,
  onConfirm,
  submitting
}: {
  taskId: number;
  url: string;
  onCancel: () => void;
  onConfirm: () => void;
  submitting: boolean;
}) {
  return (
    <Dialog title="Delete task" onClose={onCancel}>
      <div className="grid gap-4">
        <p className="text-sm text-muted">
          Are you sure you want to delete Scrape Task <strong className="text-ink">#{taskId}</strong> for <span className="break-all text-ink font-mono">{url}</span>?
          This action is permanent and cannot be undone.
        </p>
        <div className="flex justify-end gap-2 mt-2">
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={submitting}>
            {submitting ? "Deleting..." : "Delete task"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
