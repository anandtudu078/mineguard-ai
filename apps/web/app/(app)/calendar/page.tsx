import Link from "next/link";

import { CalendarList } from "@/components/calendar-list";
import { ApiErrorState, EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { getCalendar, getDashboardSummary, type EntryState } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import { load } from "@/lib/load";
import { cn } from "@/lib/utils";

export const revalidate = 30;

export const metadata = { title: "Compliance calendar" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const PAGE_SIZE = 100;

const STATES: { value: EntryState | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "overdue", label: "Overdue" },
  { value: "due_soon", label: "Due in 30 days" },
  { value: "upcoming", label: "Upcoming" },
  { value: "filed", label: "Filed" },
];

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function CalendarPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const params = await searchParams;
  const state = (first(params.entry_state) ?? "all") as EntryState | "all";

  const result = await load(() =>
    Promise.all([
      getCalendar({
        entry_state: state === "all" ? undefined : state,
        limit: PAGE_SIZE,
      }),
      getDashboardSummary(),
    ]),
  );

  if (!result.ok) {
    return (
      <>
        <PageHeader title="Compliance calendar" />
        <ApiErrorState detail={result.error} status={result.status} />
      </>
    );
  }

  const [page, summary] = result.data;

  const counts: Record<string, number | undefined> = {
    overdue: summary.totals.obligations_overdue,
    due_soon: summary.totals.obligations_due_within_30_days,
  };

  return (
      <>
        <PageHeader
          title="Compliance calendar"
          description={
            page.total === 0
              ? "No obligations match the current view"
              : `${formatNumber(page.total)} ${page.total === 1 ? "filing" : "filings"} · assessed as at ${formatDate(summary.as_of)}`
          }
        />

        <StateChips active={state} counts={counts} />

        {page.items.length === 0 ? (
          <EmptyState
            title="Nothing scheduled here"
            description="Generate a lease's calendar from the obligation rules to populate it."
          />
        ) : (
          <>
            <CalendarList entries={page.items} />
            {page.total > page.items.length && (
              <p className="mt-5 text-center text-xs text-muted-foreground">
                Showing the first {formatNumber(page.items.length)} of{" "}
                {formatNumber(page.total)}. Narrow the view with a filter to see the
                rest.
              </p>
            )}
          </>
        )}
      </>
    );
}

/**
 * Quick state filters as links rather than buttons, so each view is a real URL
 * that can be shared and bookmarked.
 */
function StateChips({
  active,
  counts,
}: {
  active: EntryState | "all";
  counts: Record<string, number | undefined>;
}) {
  return (
    <div className="-mx-4 mb-4 overflow-x-auto px-4 sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0">
      <ul className="flex w-max gap-2 lg:w-auto lg:flex-wrap">
        {STATES.map((option) => {
          const isActive = option.value === active;
          const count = counts[option.value];
          const href =
            option.value === "all"
              ? "/calendar"
              : `/calendar?entry_state=${option.value}`;

          return (
            <li key={option.value}>
              <Link
                href={href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  // min-h-11 keeps these tappable on a phone; they are the main
                  // way to navigate this page.
                  "inline-flex min-h-11 items-center gap-2 rounded-full border px-4 text-sm font-medium transition-colors lg:min-h-9 lg:px-3",
                  isActive
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-muted-foreground hover:text-foreground",
                )}
              >
                {option.label}
                {count !== undefined && count > 0 && (
                  <span
                    className={cn(
                      "rounded-full px-1.5 py-px text-xs tabular-nums",
                      isActive ? "bg-primary-foreground/20" : "bg-muted",
                    )}
                  >
                    {count}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
