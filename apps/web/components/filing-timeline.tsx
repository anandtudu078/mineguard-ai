import { CircleDollarSign } from "lucide-react";

import { DueBadge, ObligationStatusBadge } from "@/components/badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OBLIGATION_CATEGORY_LABELS, formatDate } from "@/lib/format";
import type { TimelineEntry } from "@/lib/types";

/**
 * Every dated obligation for a lease, in due order.
 *
 * Overdue items float to the top regardless of date, because the list is used
 * to decide what to work on next, not to browse history.
 */
export function FilingTimeline({ entries }: { entries: TimelineEntry[] }) {
  const overdue = entries.filter((entry) => entry.status === "overdue");
  const rest = entries.filter((entry) => entry.status !== "overdue");
  const ordered = [...overdue, ...rest];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Compliance calendar</CardTitle>
        <p className="text-xs text-muted-foreground">
          {entries.length === 0
            ? "No obligations scheduled"
            : overdue.length > 0
              ? `${overdue.length} overdue · ${entries.length} scheduled in total`
              : `${entries.length} scheduled, none overdue`}
        </p>
      </CardHeader>

      <CardContent className="px-0">
        {entries.length === 0 ? (
          <p className="px-6 text-sm text-muted-foreground">
            Generate the calendar from the obligation rules to schedule this lease&apos;s
            filings.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {ordered.map((entry) => (
              <li key={entry.id} className="flex gap-3 px-6 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">{entry.title ?? entry.code}</p>
                    {entry.requires_payment && (
                      <CircleDollarSign
                        className="size-3.5 shrink-0 text-muted-foreground"
                        aria-label="Involves a payment"
                      />
                    )}
                  </div>

                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span>Due {formatDate(entry.due_date)}</span>
                    {entry.category && <span>{OBLIGATION_CATEGORY_LABELS[entry.category]}</span>}
                    {entry.period_start && entry.period_end && (
                      <span>
                        Period {formatDate(entry.period_start)} –{" "}
                        {formatDate(entry.period_end)}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex shrink-0 flex-col items-end gap-1">
                  <ObligationStatusBadge status={entry.status} />
                  <DueBadge days={entry.days_until_due} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
