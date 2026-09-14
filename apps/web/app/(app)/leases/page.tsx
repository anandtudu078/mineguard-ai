import { PageHeader } from "@/components/page-header";
import { ApiErrorState, EmptyState } from "@/components/empty-state";
import { LeaseFilters } from "@/components/lease-filters";
import { LeaseResults } from "@/components/lease-results";
import { buttonVariants } from "@/components/ui/button";
import { getDashboardSummary, getLeases } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { load } from "@/lib/load";
import { cn } from "@/lib/utils";
import Link from "next/link";

export const revalidate = 30;

export const metadata = { title: "Lease register" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const PAGE_SIZE = 25;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function LeasesPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const params = await searchParams;
  const offset = Math.max(0, Number(first(params.offset) ?? 0) || 0);

  const result = await load(() =>
    Promise.all([
      getLeases({
        q: first(params.q),
        state: first(params.state),
        status: first(params.status) ? [first(params.status)!] : undefined,
        lease_type: first(params.lease_type) ? [first(params.lease_type)!] : undefined,
        risk_level: first(params.risk_level) ? [first(params.risk_level)!] : undefined,
        expiring_within_days: first(params.expiring_within_days)
          ? Number(first(params.expiring_within_days))
          : undefined,
        sort: first(params.sort) ?? "lease_number",
        descending: first(params.descending) === "true",
        limit: PAGE_SIZE,
        offset,
      }),
      // The dashboard rollup already carries the state list, so the filter is
      // seeded from it rather than a second, near-identical query.
      getDashboardSummary(),
    ]),
  );

  if (!result.ok) {
    return (
      <>
        <PageHeader title="Lease register" />
        <ApiErrorState detail={result.error} status={result.status} />
      </>
    );
  }

  const [page, summary] = result.data;
  const states = summary.by_state.map((row) => row.state).sort();
  const showingFrom = page.total === 0 ? 0 : offset + 1;
  const showingTo = Math.min(offset + PAGE_SIZE, page.total);

  return (
    <>
      <PageHeader
        title="Lease register"
        description={
          page.total === 0
            ? "No concessions match the current filters"
            : `Showing ${formatNumber(showingFrom)}–${formatNumber(showingTo)} of ${formatNumber(page.total)} concessions`
        }
      />

      <LeaseFilters states={states} />

      {page.items.length === 0 ? (
        <EmptyState
          title="No leases match"
          description="Try widening the filters, or clear them to see the whole register."
        />
      ) : (
        <LeaseResults leases={page.items} />
      )}

      <Pagination offset={offset} limit={PAGE_SIZE} total={page.total} params={params} />
    </>
  );
}

function Pagination({
  offset,
  limit,
  total,
  params,
}: {
  offset: number;
  limit: number;
  total: number;
  params: Record<string, string | string[] | undefined>;
}) {
  if (total <= limit) return null;

  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  const hrefFor = (nextOffset: number) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (key === "offset" || value === undefined) continue;
      if (Array.isArray(value)) value.forEach((entry) => query.append(key, entry));
      else query.set(key, value);
    }
    if (nextOffset > 0) query.set("offset", String(nextOffset));
    const queryString = query.toString();
    return queryString ? `/leases?${queryString}` : "/leases";
  };

  // Styled links rather than <Button>: a disabled Button wrapping an anchor
  // still navigates, so the unavailable state has to be handled here.
  const pageClass = (enabled: boolean) =>
    cn(
      buttonVariants({ variant: "outline" }),
      // h-11 on phones so the target is thumb-sized rather than desktop-tiny.
      "h-11 sm:h-9",
      !enabled && "pointer-events-none opacity-50",
    );

  return (
    <nav className="mt-5 flex items-center justify-between gap-3" aria-label="Pagination">
      <Link
        href={hrefFor(Math.max(0, offset - limit))}
        aria-disabled={!hasPrev}
        className={pageClass(hasPrev)}
      >
        Previous
      </Link>

      <span className="text-xs text-muted-foreground sm:text-sm">
        Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}
      </span>

      <Link
        href={hrefFor(offset + limit)}
        aria-disabled={!hasNext}
        className={pageClass(hasNext)}
      >
        Next
      </Link>
    </nav>
  );
}
