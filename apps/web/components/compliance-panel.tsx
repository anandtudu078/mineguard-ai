import type { ComplianceScore } from "@/lib/types";
import { RISK_LABELS } from "@/lib/format";
import { RiskBadge } from "@/components/badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const BAR_STYLES: Record<string, string> = {
  low: "bg-emerald-500",
  medium: "bg-amber-500",
  high: "bg-orange-500",
  critical: "bg-red-500",
};

export function scoreColor(score: number): string {
  if (score >= 85) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 70) return "text-amber-600 dark:text-amber-400";
  if (score >= 50) return "text-orange-600 dark:text-orange-400";
  return "text-red-600 dark:text-red-400";
}

/** Compact score readout for list rows and cards. */
export function ScorePill({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground">—</span>;
  return (
    <span className={cn("font-semibold tabular-nums", scoreColor(score))}>
      {score.toFixed(1)}
    </span>
  );
}

/**
 * Full score breakdown.
 *
 * Every weighted component is listed with its own explanation, including the
 * ones that were excluded. A score nobody can interrogate is a score nobody
 * acts on, so "why" is part of the component rather than an extra screen.
 */
export function CompliancePanel({ data }: { data: ComplianceScore }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Compliance score</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              Derived from clearances and filings, recomputed on every read
            </p>
          </div>
          <RiskBadge level={data.risk_level} />
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="flex items-end gap-3">
          <span
            className={cn(
              "text-4xl font-semibold tabular-nums leading-none sm:text-5xl",
              scoreColor(data.score),
            )}
          >
            {data.score.toFixed(1)}
          </span>
          <span className="pb-1 text-sm text-muted-foreground">
            / 100 · {RISK_LABELS[data.risk_level]} risk
          </span>
        </div>

        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full", BAR_STYLES[data.risk_level])}
            style={{ width: `${Math.max(2, Math.min(100, data.score))}%` }}
          />
        </div>

        <ul className="divide-y divide-border">
          {data.components.map((component) => {
            const share = component.weight > 0 ? component.earned / component.weight : 0;
            return (
              <li key={component.name} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm font-medium capitalize">
                    {component.name.replace(/_/g, " ")}
                  </span>
                  <span className="shrink-0 text-sm tabular-nums text-muted-foreground">
                    {component.applicable
                      ? `${component.earned.toFixed(1)} / ${component.weight}`
                      : "excluded"}
                  </span>
                </div>

                {component.applicable && (
                  <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${Math.max(2, share * 100)}%` }}
                    />
                  </div>
                )}

                <p className="mt-1.5 text-xs text-muted-foreground">{component.detail}</p>
              </li>
            );
          })}
        </ul>

        {data.notes.length > 0 && (
          <ul className="space-y-1.5 rounded-lg bg-muted/50 p-3">
            {data.notes.map((note) => (
              <li key={note} className="flex gap-2 text-xs text-muted-foreground">
                <span aria-hidden className="mt-1.5 size-1 shrink-0 rounded-full bg-current" />
                {note}
              </li>
            ))}
          </ul>
        )}

        <dl className="grid grid-cols-2 gap-3 border-t border-border pt-4 text-sm sm:grid-cols-3">
          <Metric label="Clearances valid" value={`${data.valid_licences} / ${data.total_licences}`} />
          <Metric label="Expiring soon" value={data.expiring_licences} tone={data.expiring_licences > 0 ? "warn" : undefined} />
          <Metric label="Lapsed / revoked" value={data.expired_licences} tone={data.expired_licences > 0 ? "bad" : undefined} />
          <Metric label="Filings submitted" value={data.submitted_obligations} />
          <Metric label="Overdue" value={data.overdue_obligations} tone={data.overdue_obligations > 0 ? "bad" : undefined} />
          <Metric label="Open" value={data.open_obligations} />
        </dl>
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "warn" | "bad";
}) {
  const toneClass =
    tone === "bad"
      ? "text-red-600 dark:text-red-400"
      : tone === "warn"
        ? "text-amber-600 dark:text-amber-400"
        : "text-foreground";

  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("mt-0.5 font-medium tabular-nums", toneClass)}>{value}</dd>
    </div>
  );
}