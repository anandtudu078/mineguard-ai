import { CircleDollarSign } from "lucide-react";
import Link from "next/link";

import { DueBadge, ObligationStatusBadge } from "@/components/badges";
import { OBLIGATION_CATEGORY_LABELS, formatDate, formatMonthYear } from "@/lib/format";
import type { CalendarEntry } from "@/lib/types";

/**
 * Calendar entries grouped by the month they fall due.
 *
 * A compliant operator thinks in months ("what is filing in October?"), not in
 * a flat sorted list, so the grouping is the primary structure rather than a
 * decoration. Month headers stick on scroll so the group stays identifiable in
 * a long list on a phone.
 */
export function CalendarList({ entries }: { entries: CalendarEntry[] }) {
  const groups = new Map<string, CalendarEntry[]>();

  for (const entry of entries) {
    const key = entry.due_date.slice(0, 7); // YYYY-MM
    const bucket = groups.get(key);
    if (bucket) bucket.push(entry);
    else groups.set(key, [entry]);
  }

  return (
    <div className="space-y-6">
      {[...groups.entries()].map(([month, group]) => {
        const overdue = group.filter((entry) => entry.status === "overdue").length;

        return (
          <section key={month}>
            <header className="sticky top-14 z-10 -mx-4 mb-2 flex items-center justify-between gap-3 border-b border-border bg-background/95 px-4 py-2 backdrop-blur sm:-mx-6 sm:px-6 lg:top-0 lg:-mx-0 lg:px-0">
              <h2 className="text-sm font-semibold">
                {formatMonthYear(`${month}-01`)}
              </h2>
              <span className="text-xs text-muted-foreground">
                {group.length} {group.length === 1 ? "filing" : "filings"}
                {overdue > 0 && (
                  <span className="ml-2 font-medium text-red-600 dark:text-red-400">
                    {overdue} overdue
                  </span>
                )}
              </span>
            </header>

            <ul className="space-y-2">
              {group.map((entry) => (
                <li key={entry.id}>
                  <CalendarRow entry={entry} />
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function CalendarRow({ entry }: { entry: CalendarEntry }) {
  const overdue = entry.status === "overdue";

  return (
    <div
      className={`rounded-xl border bg-card p-3.5 transition-colors ${
        overdue ? "border-red-600/30" : "border-border"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-medium">{entry.title ?? entry.code}</p>
            {entry.requires_payment && (
              <CircleDollarSign
                className="size-3.5 shrink-0 text-muted-foreground"
                aria-label="Involves a payment"
              />
            )}
          </div>

          {entry.lease_id && (
            <Link
              href={`/leases/${entry.lease_id}`}
              className="mt-1 block truncate text-xs text-muted-foreground hover:text-foreground hover:underline"
            >
              {entry.lease_name} · <span className="font-mono">{entry.lease_number}</span>
            </Link>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1">
          <ObligationStatusBadge status={entry.status} />
          <DueBadge days={entry.days_until_due} />
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className={overdue ? "font-medium text-red-600 dark:text-red-400" : ""}>
          Due {formatDate(entry.due_date)}
        </span>
        {entry.category && <span>{OBLIGATION_CATEGORY_LABELS[entry.category]}</span>}
        {entry.period_start && entry.period_end && (
          <span>
            Covers {formatDate(entry.period_start)} – {formatDate(entry.period_end)}
          </span>
        )}
        {entry.district && (
          <span>
            {entry.district}, {entry.state}
          </span>
        )}
      </div>

      {entry.legal_reference && (
        <p className="mt-2 border-t border-border pt-2 text-xs text-muted-foreground">
          {entry.legal_reference}
        </p>
      )}

      {entry.status === "waived" && entry.waiver_reason && (
        <p className="mt-2 border-t border-border pt-2 text-xs text-muted-foreground">
          Waived — {entry.waiver_reason}
        </p>
      )}

      {overdue && entry.penalty_note && (
        <p className="mt-2 border-t border-red-600/20 pt-2 text-xs text-red-600 dark:text-red-400">
          {entry.penalty_note}
        </p>
      )}
    </div>
  );
}
