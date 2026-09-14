import { AlertTriangle, ArrowRight, CalendarClock, FileCheck2, History } from "lucide-react";
import Link from "next/link";

import { ApiErrorState, EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { ReminderButton } from "@/components/reminder-button";
import { getCalendar, getDashboardSummary, getExpiringLeases, getReminderHistory } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { load } from "@/lib/load";
import type { CalendarEntry } from "@/lib/types";

export const revalidate = 30;
export const metadata = { title: "Needs attention" };

export default async function ActionsPage() {
  const result = await load(() =>
    Promise.all([
      getCalendar({ entry_state: "overdue", limit: 12 }),
      getCalendar({ entry_state: "due_soon", limit: 12 }),
      getExpiringLeases(90, undefined),
      getDashboardSummary(),
      getReminderHistory(10),
    ]),
  );

  if (!result.ok) {
    return (
      <>
        <PageHeader title="Needs attention" />
        <ApiErrorState detail={result.error} status={result.status} />
      </>
    );
  }

  const [overdue, dueSoon, expiringSites, summary, reminderHistory] = result.data;
  const hasWork = overdue.items.length > 0 || dueSoon.items.length > 0 || expiringSites.length > 0;

  return (
    <>
      <PageHeader
        title="Needs attention"
        description={`A short list of the work that matters most today · checked ${formatDate(summary.as_of)}`}
      />

      {!hasWork ? (
        <EmptyState
          title="Everything is up to date"
          description="There are no overdue filings, urgent deadlines, or sites ending soon."
        />
      ) : (
        <div className="space-y-6">
          {overdue.items.length > 0 && (
            <ActionGroup
              title="Do these first"
              description="These deadlines have already passed."
              icon={AlertTriangle}
              tone="danger"
              entries={overdue.items}
            />
          )}

          {dueSoon.items.length > 0 && (
            <ActionGroup
              title="Coming up soon"
              description="Plan these tasks before they become overdue."
              icon={CalendarClock}
              tone="warning"
              entries={dueSoon.items}
            />
          )}

          {expiringSites.length > 0 && (
            <section>
              <SectionHeading
                title="Permissions to check"
                description="These mining sites have permissions ending within 90 days."
                icon={FileCheck2}
              />
              <div className="grid gap-3 md:grid-cols-2">
                {expiringSites.map((site) => (
                  <Link
                    key={site.id}
                    href={`/leases/${site.id}`}
                    className="group rounded-xl border border-amber-600/25 bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-amber-600/50 hover:shadow-md"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold">{site.name}</h3>
                        <p className="mt-1 text-sm text-muted-foreground">{site.lease_number}</p>
                      </div>
                      <ArrowRight className="size-5 text-muted-foreground transition-transform group-hover:translate-x-1" aria-hidden />
                    </div>
                    <p className="mt-3 text-sm text-amber-700 dark:text-amber-400">
                      Site term ends {site.effective_to ? formatDate(site.effective_to) : "soon"}
                    </p>
                  </Link>
                ))}
              </div>
            </section>
          )}

          <section>
            <SectionHeading
              title="Recent reminders"
              description="See what the system prepared or sent recently."
              icon={History}
            />
            {reminderHistory.length === 0 ? (
              <p className="rounded-xl border border-dashed border-border bg-card p-4 text-sm text-muted-foreground">
                No reminders have been prepared yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {reminderHistory.map((delivery) => (
                  <li key={delivery.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-3.5 text-sm">
                    <span className="min-w-0 truncate text-muted-foreground">
                      {delivery.recipient_email ?? "No email address"}
                    </span>
                    <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium capitalize">
                      {delivery.status.replaceAll("_", " ")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </>
  );
}

function ActionGroup({
  title,
  description,
  icon: Icon,
  tone,
  entries,
}: {
  title: string;
  description: string;
  icon: typeof AlertTriangle;
  tone: "danger" | "warning";
  entries: CalendarEntry[];
}) {
  return (
    <section>
      <SectionHeading title={title} description={description} icon={Icon} />
      <div className="space-y-3">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className={`group block rounded-xl border bg-card p-4 transition-all hover:-translate-y-0.5 hover:shadow-md ${
              tone === "danger" ? "border-red-600/30 hover:border-red-600/55" : "border-amber-600/30 hover:border-amber-600/55"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h3 className="font-semibold">{entry.title ?? entry.code}</h3>
                <p className="mt-1 truncate text-sm text-muted-foreground">
                  {entry.lease_name ?? "Mining site"} · {entry.lease_number ?? ""}
                </p>
              </div>
              <Link href={entry.lease_id ? `/leases/${entry.lease_id}` : "/calendar"} aria-label={`Open ${entry.title ?? entry.code}`}>
                <ArrowRight className="size-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1" aria-hidden />
              </Link>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
              <span className={tone === "danger" ? "font-medium text-red-700 dark:text-red-400" : "font-medium text-amber-700 dark:text-amber-400"}>
                Due {formatDate(entry.due_date)}
              </span>
              {entry.category && <span className="text-muted-foreground">{entry.category.replaceAll("_", " ")}</span>}
            </div>
            <div className="mt-3">
              <ReminderButton
                title={entry.title ?? entry.code ?? "Compliance task"}
                siteName={entry.lease_name ?? "the mining site"}
                dueDate={formatDate(entry.due_date)}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function SectionHeading({
  title,
  description,
  icon: Icon,
}: {
  title: string;
  description: string;
  icon: typeof AlertTriangle;
}) {
  return (
    <div className="mb-3 flex items-start gap-3">
      <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
        <Icon className="size-5" aria-hidden />
      </span>
      <div>
        <h2 className="text-lg font-semibold sm:text-xl">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}