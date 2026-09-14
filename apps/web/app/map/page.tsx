import { MapPinned } from "lucide-react";
import Link from "next/link";

import { LeaseFilters } from "@/components/lease-filters";
import { RiskBadge } from "@/components/badges";
import { ScorePill } from "@/components/compliance-panel";
import { ApiErrorState, EmptyState } from "@/components/empty-state";
import { LeaseMap, type MapLease } from "@/components/lease-map";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
import { getDashboardSummary, getLeaseGeoJSON } from "@/lib/api";
import { formatArea, formatNumber } from "@/lib/format";
import { load } from "@/lib/load";

export const revalidate = 30;

export const metadata = { title: "Site map" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function MapPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const params = await searchParams;

  const filters = {
    q: first(params.q),
    state: first(params.state),
    status: first(params.status) ? [first(params.status)!] : undefined,
    lease_type: first(params.lease_type) ? [first(params.lease_type)!] : undefined,
    risk_level: first(params.risk_level) ? [first(params.risk_level)!] : undefined,
  };

  const result = await load(() =>
    Promise.all([getLeaseGeoJSON(filters), getDashboardSummary()]),
  );

  if (!result.ok) {
    return (
      <>
        <PageHeader title="Site map" />
        <ApiErrorState detail={result.error} status={result.status} />
      </>
    );
  }

  const [collection, summary] = result.data;

  const leases: MapLease[] = collection.features.map((feature) => ({
    id: feature.properties.id,
    name: feature.properties.name,
    lease_number: feature.properties.lease_number,
    // The API falls back to the centroid server-side, so geometry is always
    // present for a lease that appears in the collection.
    geometry: feature.geometry,
  }));

  const states = summary.by_state.map((row) => row.state).sort();

  return (
      <>
        <PageHeader
          title="Site map"
          description={
            collection.features.length === 0
              ? "No concessions match the current filters"
              : `${formatNumber(collection.features.length)} concessions plotted · tap a site for its compliance status`
          }
        />

        <LeaseFilters states={states} />

        {leases.length === 0 ? (
          <EmptyState
            icon={MapPinned}
            title="Nothing to plot"
            description="No concessions match the current filters."
          />
        ) : (
          // Side by side once there is room; stacked on a phone with the map
          // first, since the map is what the page is for.
          <div className="grid gap-4 lg:grid-cols-[1fr_22rem] xl:grid-cols-[1fr_26rem]">
            <LeaseMap
              leases={leases}
              className="h-72 sm:h-96 lg:h-[calc(100dvh-18rem)] lg:min-h-96"
            />

            <Card className="overflow-hidden p-0 lg:h-[calc(100dvh-18rem)] lg:min-h-96">
              <div className="border-b border-border px-4 py-2.5">
                <p className="text-xs font-medium text-muted-foreground">
                  {collection.features.length} plotted
                </p>
              </div>
              <ul className="max-h-96 divide-y divide-border overflow-y-auto lg:max-h-none lg:h-[calc(100%-2.75rem)]">
                {collection.features.map((feature) => (
                  <li key={feature.properties.id}>
                    <Link
                      href={`/leases/${feature.properties.id}`}
                      className="block px-4 py-3 transition-colors hover:bg-muted/50"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {feature.properties.name}
                          </p>
                          <p className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
                            {feature.properties.lease_number}
                          </p>
                        </div>
                        <ScorePill score={feature.properties.compliance_score} />
                      </div>

                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <RiskBadge level={feature.properties.risk_level} />
                        <span className="truncate">
                          {feature.properties.mineral_name} ·{" "}
                          {formatArea(feature.properties.area_hectares)}
                        </span>
                      </div>

                      {feature.properties.overdue_obligations > 0 && (
                        <p className="mt-1.5 text-xs font-medium text-red-600 dark:text-red-400">
                          {feature.properties.overdue_obligations} overdue
                        </p>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        )}
      </>
    );
}
