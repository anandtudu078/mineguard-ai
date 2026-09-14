import { notFound } from "next/navigation";

import { LeaseStatusBadge, RiskBadge } from "@/components/badges";
import { CompliancePanel } from "@/components/compliance-panel";
import { ApiErrorState } from "@/components/empty-state";
import { FilingTimeline } from "@/components/filing-timeline";
import { LeaseMap } from "@/components/lease-map";
import { LicenceList, NoLicencesWarning } from "@/components/licence-list";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DocumentUpload } from "@/components/document-upload";
import { DocumentReview } from "@/components/document-review";
import { InspectionsPanel } from "@/components/inspections-panel";
import {
  getLease,
  getLeaseCompliance,
  getLeaseDocuments,
  getLeaseLicences,
  getLeaseTimeline,
} from "@/lib/api";
import {
  LEASE_TYPE_LABELS,
  MINERAL_CATEGORY_LABELS,
  formatArea,
  formatDate,
  formatNumber,
  titleCase,
} from "@/lib/format";
import { load } from "@/lib/load";

export const revalidate = 30;

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  const result = await load(() => getLease(id));
  return {
    title: result.ok ? `${result.data.name} (${result.data.lease_number})` : "Lease",
  };
}

export default async function LeaseDetailPage({ params }: { params: Params }) {
  const { id } = await params;

  const result = await load(() =>
    Promise.all([
      getLease(id),
      getLeaseCompliance(id),
      getLeaseLicences(id),
      getLeaseTimeline(id),
      getLeaseDocuments(id, 0, 20),
    ]),
  );

  if (!result.ok) {
    // 404 is a genuinely missing lease. 422 means the id in the URL is not even
    // a UUID - also "no such lease", and better rendered as a not-found page
    // than as an API failure.
    if (result.status === 404 || result.status === 422) notFound();
    return (
      <>
        <PageHeader backHref="/leases" backLabel="Lease register" title="Lease" />
        <ApiErrorState detail={result.error} status={result.status} />
      </>
    );
  }

  const [lease, compliance, licences, timeline, documents] = result.data;

  // Only surfaced when the gap is material. Sub-1% differences are normal noise
  // between a deed figure and a survey; a large one is a finding.
  const areaGap =
    lease.area_hectares !== null && lease.surveyed_area_hectares !== null
      ? Math.abs((lease.surveyed_area_hectares / Number(lease.area_hectares) - 1) * 100)
      : null;

  return (
    <>
      <PageHeader
        backHref="/leases"
        backLabel="Lease register"
        title={lease.name}
        description={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-mono">{lease.lease_number}</span>
            <span aria-hidden>·</span>
            <span>{LEASE_TYPE_LABELS[lease.lease_type]}</span>
            <span aria-hidden>·</span>
            <span>
              {lease.district}, {lease.state}
            </span>
          </span>
        }
        actions={
          <>
            <LeaseStatusBadge status={lease.status} />
            <RiskBadge level={compliance.risk_level} />
          </>
        }
      />

      {/* Full width above the columns: the map is the fastest way to orient
          yourself, and on a phone it should not be squeezed beside text. */}
      <LeaseMap
        leases={[
          {
            id: lease.id,
            name: lease.name,
            lease_number: lease.lease_number,
            boundary: lease.boundary,
            centroid: lease.centroid,
          },
        ]}
        className="mb-4 h-56 sm:h-72 lg:h-80"
      />

      {areaGap !== null && areaGap >= 2 && (
        <div className="mb-4 rounded-lg border border-amber-600/30 bg-amber-500/5 p-3 text-sm">
          <span className="font-medium">Boundary does not match the deed.</span>{" "}
          <span className="text-muted-foreground">
            The deed states {formatArea(lease.area_hectares)}, but the surveyed boundary
            measures {formatArea(lease.surveyed_area_hectares)} — a{" "}
            {areaGap.toFixed(1)}% difference.
          </span>
        </div>
      )}

      {licences.length === 0 && (
        <div className="mb-4">
          <NoLicencesWarning />
        </div>
      )}

      {/* Single column on phones; the score moves alongside the detail once
          there is width for two columns. */}
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Lease particulars</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-3">
                <Field label="Held by" value={lease.holder?.name ?? "—"} />
                <Field
                  label="Holder type"
                  value={lease.holder ? titleCase(lease.holder.entity_type) : "—"}
                />
                <Field
                  label="Mineral"
                  value={lease.mineral?.name ?? "—"}
                  hint={
                    lease.mineral
                      ? MINERAL_CATEGORY_LABELS[lease.mineral.category]
                      : undefined
                  }
                />
                <Field
                  label="Royalty"
                  value={
                    lease.mineral
                      ? `${lease.mineral.royalty_rate} ${lease.mineral.royalty_unit ?? ""}`.trim()
                      : "—"
                  }
                  hint={lease.mineral ? titleCase(lease.mineral.royalty_basis) : undefined}
                />
                <Field label="Granted area" value={formatArea(lease.area_hectares)} />
                <Field
                  label="Surveyed area"
                  value={formatArea(lease.surveyed_area_hectares)}
                  hint="Measured by PostGIS from the boundary"
                />
                <Field label="Grant date" value={formatDate(lease.grant_date)} />
                <Field label="Term from" value={formatDate(lease.effective_from)} />
                <Field label="Term to" value={formatDate(lease.effective_to)} />
                <Field
                  label="Annual production"
                  value={
                    lease.annual_production_tonnes
                      ? `${formatNumber(Number(lease.annual_production_tonnes))} t`
                      : "—"
                  }
                />
                <Field label="Village" value={lease.village ?? "—"} />
                <Field label="Country" value={lease.country} />
              </dl>

              {lease.notes && (
                <p className="mt-4 border-t border-border pt-4 text-sm text-muted-foreground">
                  {lease.notes}
                </p>
              )}
            </CardContent>
          </Card>

          <LicenceList licences={licences} />
          <InspectionsPanel leaseId={lease.id} />
          <DocumentUpload leaseId={lease.id} />
          <Card>
            <CardHeader>
              <CardTitle>Document review</CardTitle>
            </CardHeader>
            <CardContent>
              <DocumentReview leaseId={lease.id} documents={documents.items} />
            </CardContent>
          </Card>
          <FilingTimeline entries={timeline} />
        </div>

        <div className="xl:col-span-1">
          <div className="xl:sticky xl:top-6">
            <CompliancePanel data={compliance} />
          </div>
        </div>
      </div>
    </>
  );
}

function Field({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium">{value}</dd>
      {hint && <p className="mt-0.5 truncate text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
