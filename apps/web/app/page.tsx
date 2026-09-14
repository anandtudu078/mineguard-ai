import {
  ArrowUpRight,
  AlertTriangle,
  CalendarClock,
  ClipboardCheck,
  FileWarning,
  Gauge,
  MapPinned,
  Layers,
} from "lucide-react";
import Link from "next/link";

import { RiskBadge } from "@/components/badges";
import { ApiErrorState, EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getDashboardSummary } from "@/lib/api";
import { OBLIGATION_CATEGORY_LABELS, formatArea, formatDate } from "@/lib/format";
import { load } from "@/lib/load";
import type { RiskLevel } from "@/lib/types";
import { cn } from "@/lib/utils";

export const revalidate = 30;

export default async function DashboardPage() {
  const result = await load(() => getDashboardSummary());

  if (!result.ok) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <ApiErrorState detail={result.error} status={result.status} />
      </>
    );
  }

  const { totals, risk_buckets, by_state, overdue_by_category } = result.data;

  return (
    <>
      <PageHeader
        title="Your compliance overview"
        description={
          <>
            Last checked {formatDate(result.data.as_of)} · {totals.leases_total}{" "}
            {totals.leases_total === 1 ? "mining site" : "mining sites"} being tracked
          </>
        }
      />

      <section className="relative mb-5 overflow-hidden rounded-2xl bg-primary px-5 py-5 text-primary-foreground shadow-[0_18px_45px_-28px_oklch(0.25_0.08_169)] sm:px-6 sm:py-6">
        <div className="absolute -right-12 -top-16 size-48 rounded-full border-[18px] border-primary-foreground/8" />
        <div className="absolute -bottom-20 right-24 size-40 rounded-full border-[12px] border-primary-foreground/6" />
        <div className="relative grid gap-5 lg:grid-cols-[1fr_auto] lg:items-center">
          <div className="max-w-2xl">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-primary-foreground/65">
              <ClipboardCheck className="size-4" aria-hidden />
              Start here
            </div>
            <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
              Here is what needs your attention.
            </h2>
            <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-primary-foreground/75">
              Select any item below to see the details and what to do next.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <Link
              href="/calendar?entry_state=overdue"
              className="group rounded-xl bg-primary-foreground/12 px-3 py-3 text-left transition-colors hover:bg-primary-foreground/20"
            >
              <span className="block text-2xl font-semibold tabular-nums">{totals.obligations_overdue}</span>
              <span className="mt-0.5 flex items-center gap-1 text-xs text-primary-foreground/70">
                Past due <ArrowUpRight className="size-3 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden />
              </span>
            </Link>
            <Link
              href="/leases?expiring_within_days=90"
              className="group rounded-xl bg-primary-foreground/12 px-3 py-3 text-left transition-colors hover:bg-primary-foreground/20"
            >
              <span className="block text-2xl font-semibold tabular-nums">{totals.licences_expiring_soon}</span>
              <span className="mt-0.5 flex items-center gap-1 text-xs text-primary-foreground/70">
                Expiring soon <ArrowUpRight className="size-3 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden />
              </span>
            </Link>
          </div>
        </div>
      </section>

        <h2 className="mb-3 text-lg font-semibold sm:text-xl">At a glance</h2>

        {/* Two columns on a phone: these tiles are short, and stacking them would
          push everything else several screens down. */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
        <StatCard
          label="Overall health"
          value={totals.average_compliance_score.toFixed(1)}
          hint="Across all mining sites"
          icon={Gauge}
          tone={
            totals.average_compliance_score >= 85
              ? "good"
              : totals.average_compliance_score >= 70
                ? "warn"
                : "bad"
          }
        />
        <StatCard
          label="Past-due work"
          value={totals.obligations_overdue}
          hint="Needs attention now"
          icon={AlertTriangle}
          tone={totals.obligations_overdue > 0 ? "bad" : "good"}
        />
        <StatCard
          label="Due this month"
          value={totals.obligations_due_within_30_days}
          hint="Plan ahead"
          icon={CalendarClock}
          tone={totals.obligations_due_within_30_days > 0 ? "warn" : "neutral"}
        />
        <StatCard
          label="Expired permissions"
          value={totals.licences_expired}
          hint="Check these first"
          icon={FileWarning}
          tone={totals.licences_expired > 0 ? "bad" : "good"}
        />
        <StatCard
          label="Permissions expiring"
          value={totals.licences_expiring_soon}
          hint="Within the next 90 days"
          icon={FileWarning}
          tone={totals.licences_expiring_soon > 0 ? "warn" : "good"}
        />
        <StatCard
          label="Active mining sites"
          value={totals.leases_active}
          hint={`of ${totals.leases_total} sites tracked`}
          icon={Layers}
        />
        <StatCard
          label="Sites ending soon"
          value={totals.leases_expiring_within_90_days}
          hint="Ending within 90 days"
          icon={CalendarClock}
          tone={totals.leases_expiring_within_90_days > 0 ? "warn" : "neutral"}
        />
        <StatCard
          label="Total area"
          value={formatArea(totals.total_area_hectares)}
          hint="Land being tracked"
          icon={MapPinned}
        />
      </section>

      {totals.leases_total === 0 && (
        <div className="mt-6">
          <EmptyState
            title="No concessions on the register yet"
            description="Load the reference pack and demo data to populate the dashboard."
          />
        </div>
      )}

      <div className="mt-5 grid gap-4 lg:mt-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Risk distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <RiskDistribution buckets={risk_buckets} />
            <Link
              href="/leases?risk_level=critical&risk_level=high"
              className="mt-4 inline-block text-sm font-medium text-primary hover:underline"
            >
              View high-risk leases →
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Overdue by category</CardTitle>
          </CardHeader>
          <CardContent>
            {overdue_by_category.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No obligations scheduled yet.
              </p>
            ) : (
              <ul className="space-y-3">
                {overdue_by_category.map((row) => (
                  <li
                    key={row.category}
                    className="flex items-baseline justify-between gap-3 text-sm"
                  >
                    <span className="font-medium">
                      {OBLIGATION_CATEGORY_LABELS[row.category]}
                    </span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {row.overdue > 0 && (
                        <span className="font-medium text-red-600 dark:text-red-400">
                          {row.overdue} overdue
                        </span>
                      )}
                      {row.overdue > 0 && row.due_soon > 0 && " · "}
                      {row.due_soon > 0 && `${row.due_soon} due soon`}
                      {row.overdue === 0 && row.due_soon === 0 && "none"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <Link
              href="/calendar?entry_state=overdue"
              className="mt-4 inline-block text-sm font-medium text-primary hover:underline"
            >
              Open the calendar →
            </Link>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Register by state</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y divide-border">
            {by_state.map((row) => (
              <li
                key={row.state}
                className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
              >
                <Link
                  href={`/leases?state=${encodeURIComponent(row.state)}`}
                  className="truncate text-sm font-medium hover:underline"
                >
                  {row.state}
                </Link>
                <span className="shrink-0 text-sm tabular-nums text-muted-foreground">
                  {row.lease_count} {row.lease_count === 1 ? "lease" : "leases"} ·{" "}
                  {formatArea(row.area_hectares)}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </>
  );
}

const BAR: Record<RiskLevel, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-amber-500",
  low: "bg-emerald-500",
};

function RiskDistribution({
  buckets,
}: {
  buckets: { risk_level: RiskLevel; lease_count: number }[];
}) {
  const total = buckets.reduce((sum, bucket) => sum + bucket.lease_count, 0);

  if (total === 0) {
    return <p className="text-sm text-muted-foreground">No leases to assess yet.</p>;
  }

  return (
    <ul className="space-y-3">
      {buckets.map((bucket) => (
        <li key={bucket.risk_level}>
          <div className="flex items-center justify-between gap-3">
            <RiskBadge level={bucket.risk_level} />
            <span className="text-sm tabular-nums text-muted-foreground">
              {bucket.lease_count}
            </span>
          </div>
          {/* Bar scaled to the whole register, so the proportions read at a
              glance on a phone. */}
          <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full", BAR[bucket.risk_level])}
              style={{ width: `${(bucket.lease_count / total) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
