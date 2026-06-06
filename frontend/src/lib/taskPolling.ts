import { TaskResponse } from "../types";

export const terminalTaskStates = new Set(["COMPLETED", "FAILED"]);

export function isTerminalTask(task: TaskResponse | null | undefined): boolean {
  return Boolean(task && terminalTaskStates.has(task.state));
}

export function shouldPollTask(
  task: TaskResponse | null | undefined,
  consecutiveFailures: number,
  currentTaskNotFound = false
): boolean {
  if (currentTaskNotFound) return false;
  if (consecutiveFailures >= 3) return false;
  if (!task) return true;
  return !isTerminalTask(task);
}

export function stateTone(state: string): "success" | "danger" | "warning" | "neutral" {
  if (state === "COMPLETED") return "success";
  if (state === "FAILED") return "danger";
  if (state === "PERMISSION_GRANTED") return "warning";
  return "neutral";
}
