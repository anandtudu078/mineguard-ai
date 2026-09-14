import { CalendarX2, ShieldCheck } from "lucide-react";

import { DueBadge, LicenceStatusBadge } from "@/components/badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LICENCE_TYPE_LABELS, formatDate } from "@/lib/format";
import type { Licence } from "@/lib/types";
import { cn } from "@/lib/utils";

export function LicenceList({ licences }: { licences: Licence[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-muted-foreground" aria-hidden />
          Statutory clearances
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {licences.length === 0
            ? "None recorded"
            : `${licences.length} recorded · operating without a current clearance is a breach`}
        </p>
      </CardHeader>

      <CardContent className="px-0">
        {licences.length === 0 ? (
          <p className="px-6 text-sm text-muted-foreground">
            No clearances have been recorded against this lease.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {licences.map((licence) => (
              <li key={licence.id} className="px-6 py-3.5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {LICENCE_TYPE_LABELS[licence.licence_type] ?? licence.licence_type}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {licence.authority}
                      {licence.reference_number && ` · ${licence.reference_number}`}
                    </p>
                  </div>
                  <LicenceStatusBadge status={licence.status} />
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
                  <span>
                    Valid to{" "}
                    <span className={cn(licence.is_expired && "font-medium text-red-600 dark:text-red-400")}>
                      {formatDate(licence.valid_to)}
                    </span>
                  </span>

                  {licence.valid_from && <span>From {formatDate(licence.valid_from)}</span>}

                  <DueBadge days={licence.days_until_expiry} />

                  {licence.is_mandatory && (
                    <span className="rounded border border-border px-1.5 py-px">
                      Mandatory
                    </span>
                  )}
                </div>

                {licence.notes && (
                  <p className="mt-1.5 text-xs text-muted-foreground">{licence.notes}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/** Shown for a lease with no clearances at all, which is itself a finding. */
export function NoLicencesWarning() {
  return (
    <div className="flex gap-3 rounded-lg border border-amber-600/30 bg-amber-500/5 p-3">
      <CalendarX2 className="size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden />
      <p className="text-sm text-muted-foreground">
        No clearances are recorded against this lease. Its score excludes clearance
        validity entirely, so it may look healthier than it is.
      </p>
    </div>
  );
}
