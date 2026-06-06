import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import { ReactNode } from "react";

type AlertTone = "info" | "success" | "danger";

const toneClasses: Record<AlertTone, string> = {
  info: "border-line bg-white text-ink",
  success: "border-green-200 bg-green-50 text-success",
  danger: "border-red-200 bg-red-50 text-danger"
};

const icons = {
  info: Info,
  success: CheckCircle2,
  danger: AlertCircle
};

export function Alert({
  tone = "info",
  children
}: {
  tone?: AlertTone;
  children: ReactNode;
}) {
  const Icon = icons[tone];
  return (
    <div className={`flex gap-3 rounded-md border p-3 text-sm ${toneClasses[tone]}`}>
      <Icon className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}
