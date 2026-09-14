import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Inbox } from "lucide-react";

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
}: {
  title: string;
  description?: string;
  icon?: LucideIcon;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border px-6 py-12 text-center">
      <Icon className="size-8 text-muted-foreground" aria-hidden />
      <p className="mt-3 text-sm font-medium">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/**
 * Shown when a read fails.
 *
 * Distinguishes the two causes, because they need different responses from the
 * reader. A missing `status` means the request never got an answer - almost
 * always the backend not running in local development - so it names the command
 * to start it. A status means the API answered and rejected the request, so
 * telling someone to start the server would send them the wrong way.
 */
export function ApiErrorState({
  detail,
  status,
}: {
  detail?: string;
  status?: number;
}) {
  const reached = status !== undefined;

  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
      <div className="flex gap-3">
        <AlertTriangle className="size-5 shrink-0 text-destructive" aria-hidden />
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {reached ? "The compliance API rejected this request" : "Could not reach the compliance API"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {reached
              ? `${status} ${detail ?? ""}`.trim()
              : (detail ??
                "Start it with: cd services/api && uv run uvicorn app.main:app --port 8000")}
          </p>
        </div>
      </div>
    </div>
  );
}
