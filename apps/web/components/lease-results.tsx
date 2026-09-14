import { MapPin } from "lucide-react";
import Link from "next/link";

import { LeaseStatusBadge, RiskBadge } from "@/components/badges";
import { ScorePill } from "@/components/compliance-panel";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatArea, formatDateCompact } from "@/lib/format";
import type { LeaseListItem } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Lease results, rendered two ways.
 *
 * A nine-column register table is unusable on a phone, and a card list wastes
 * the width on a desktop. So: cards below `lg`, table at `lg` and above. Both
 * read from the same data and link to the same detail route.
 *
 * Both are in the DOM (hidden with CSS) rather than swapped in JavaScript, so
 * there is no layout shift on resize and no client component needed for it.
 */
export function LeaseResults({ leases }: { leases: LeaseListItem[] }) {
  return (
    <>
      <LeaseCardList leases={leases} className="lg:hidden" />
      <LeaseTable leases={leases} className="hidden lg:block" />
    </>
  );
}

function LeaseCardList({
  leases,
  className,
}: {
  leases: LeaseListItem[];
  className?: string;
}) {
  return (
    <ul className={cn("space-y-3", className)}>
      {leases.map((lease) => (
        <li key={lease.id}>
          <Link
            href={`/leases/${lease.id}`}
            className="block rounded-xl border border-border bg-card transition-colors active:bg-muted/60 hover:border-foreground/20"
          >
            <div className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold">{lease.name}</p>
                  <p className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
                    {lease.lease_number}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <ScorePill score={lease.compliance_score} />
                  <p className="mt-0.5 text-[0.6875rem] text-muted-foreground">score</p>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <LeaseStatusBadge status={lease.status} />
                <RiskBadge level={lease.risk_level} />
              </div>

              <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
                <MapPin className="size-3.5 shrink-0" aria-hidden />
                <span className="truncate">
                  {lease.district}, {lease.state}
                </span>
              </div>

              <dl className="mt-3 grid grid-cols-3 gap-2 border-t border-border pt-3 text-xs">
                <Stat label="Mineral" value={lease.mineral_name ?? "—"} />
                <Stat label="Area" value={formatArea(lease.area_hectares)} />
                <Stat
                  label="Expires"
                  value={formatDateCompact(lease.effective_to)}
                />
              </dl>

              {(lease.overdue_obligations > 0 || lease.expired_licences > 0) && (
                <div className="mt-3 flex flex-wrap gap-2 border-t border-border pt-3 text-xs">
                  {lease.overdue_obligations > 0 && (
                    <span className="font-medium text-red-600 dark:text-red-400">
                      {lease.overdue_obligations} overdue
                    </span>
                  )}
                  {lease.expired_licences > 0 && (
                    <span className="font-medium text-red-600 dark:text-red-400">
                      {lease.expired_licences} clearance
                      {lease.expired_licences === 1 ? "" : "s"} lapsed
                    </span>
                  )}
                  {lease.expiring_licences > 0 && (
                    <span className="font-medium text-amber-600 dark:text-amber-400">
                      {lease.expiring_licences} expiring
                    </span>
                  )}
                </div>
              )}
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 truncate font-medium">{value}</dd>
    </div>
  );
}

function LeaseTable({
  leases,
  className,
}: {
  leases: LeaseListItem[];
  className?: string;
}) {
  return (
    <Card className={cn("overflow-hidden p-0", className)}>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Lease</TableHead>
              <TableHead>Mineral</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Area</TableHead>
              <TableHead>Expires</TableHead>
              <TableHead className="text-right">Open issues</TableHead>
              <TableHead className="text-right">Score</TableHead>
              <TableHead>Risk</TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {leases.map((lease) => (
              <TableRow key={lease.id} className="group">
                <TableCell>
                  <Link href={`/leases/${lease.id}`} className="block">
                    <span className="font-medium group-hover:underline">
                      {lease.name}
                    </span>
                    <span className="mt-0.5 block font-mono text-xs text-muted-foreground">
                      {lease.lease_number}
                    </span>
                  </Link>
                </TableCell>

                <TableCell className="text-muted-foreground">
                  {lease.mineral_name ?? "—"}
                </TableCell>

                <TableCell className="text-muted-foreground">
                  {lease.district}, {lease.state}
                </TableCell>

                <TableCell>
                  <LeaseStatusBadge status={lease.status} />
                </TableCell>

                <TableCell className="text-right tabular-nums text-muted-foreground">
                  {formatArea(lease.area_hectares)}
                </TableCell>

                <TableCell className="tabular-nums text-muted-foreground">
                  {formatDateCompact(lease.effective_to)}
                </TableCell>

                <TableCell className="text-right">
                  <IssueCount lease={lease} />
                </TableCell>

                <TableCell className="text-right">
                  <ScorePill score={lease.compliance_score} />
                </TableCell>

                <TableCell>
                  <RiskBadge level={lease.risk_level} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}

function IssueCount({ lease }: { lease: LeaseListItem }) {
  const total =
    lease.overdue_obligations + lease.expired_licences + lease.expiring_licences;

  if (total === 0) {
    return <span className="text-muted-foreground">—</span>;
  }

  return (
    <span className="inline-flex items-center gap-2 tabular-nums">
      {lease.overdue_obligations > 0 && (
        <span className="font-medium text-red-600 dark:text-red-400">
          {lease.overdue_obligations} overdue
        </span>
      )}
      {lease.expired_licences > 0 && (
        <span className="font-medium text-red-600 dark:text-red-400">
          {lease.expired_licences} lapsed
        </span>
      )}
      {lease.expiring_licences > 0 && (
        <span className="font-medium text-amber-600 dark:text-amber-400">
          {lease.expiring_licences} expiring
        </span>
      )}
    </span>
  );
}
