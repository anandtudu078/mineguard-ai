/**
 * Status, risk and deadline badges.
 *
 * Colour classes are written out in full rather than composed from variables,
 * because Tailwind scans source text for class names at build time and would
 * drop anything assembled at runtime.
 */

import { cn } from "@/lib/utils";
import {
  LEASE_STATUS_LABELS,
  LICENCE_STATUS_LABELS,
  OBLIGATION_STATUS_LABELS,
  RISK_LABELS,
  formatDaysUntilShort,
} from "@/lib/format";
import type {
  LeaseStatus,
  LicenceStatus,
  ObligationStatus,
  RiskLevel,
} from "@/lib/types";

const BASE =
  "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium whitespace-nowrap";

const RISK_STYLES: Record<RiskLevel, string> = {
  low: "border-emerald-600/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  medium: "border-amber-600/25 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  high: "border-orange-600/30 bg-orange-500/12 text-orange-700 dark:text-orange-400",
  critical: "border-red-600/30 bg-red-500/12 text-red-700 dark:text-red-400",
};

const LEASE_STATUS_STYLES: Record<LeaseStatus, string> = {
  active: "border-emerald-600/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  pending: "border-border bg-muted text-muted-foreground",
  pending_renewal: "border-amber-600/25 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  suspended: "border-orange-600/30 bg-orange-500/12 text-orange-700 dark:text-orange-400",
  expired: "border-red-600/30 bg-red-500/12 text-red-700 dark:text-red-400",
  surrendered: "border-border bg-muted text-muted-foreground",
  revoked: "border-red-600/30 bg-red-500/12 text-red-700 dark:text-red-400",
};

const LICENCE_STATUS_STYLES: Record<LicenceStatus, string> = {
  valid: "border-emerald-600/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  expiring_soon: "border-amber-600/25 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  expired: "border-red-600/30 bg-red-500/12 text-red-700 dark:text-red-400",
  revoked: "border-red-600/30 bg-red-500/12 text-red-700 dark:text-red-400",
  pending: "border-border bg-muted text-muted-foreground",
};

const OBLIGATION_STATUS_STYLES: Record<ObligationStatus, string> = {
  submitted: "border-emerald-600/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  pending: "border-border bg-muted text-muted-foreground",
  in_progress: "border-sky-600/25 bg-sky-500/10 text-sky-700 dark:text-sky-400",
  overdue: "border-red-600/30 bg-red-500/12 text-red-700 dark:text-red-400",
  waived: "border-violet-600/25 bg-violet-500/10 text-violet-700 dark:text-violet-400",
  not_applicable: "border-border bg-muted text-muted-foreground",
};

export function RiskBadge({
  level,
  className,
}: {
  level: RiskLevel | null;
  className?: string;
}) {
  if (!level) return <span className="text-muted-foreground">—</span>;
  return (
    <span className={cn(BASE, RISK_STYLES[level], className)}>
      {RISK_LABELS[level]}
    </span>
  );
}

export function LeaseStatusBadge({
  status,
  className,
}: {
  status: LeaseStatus;
  className?: string;
}) {
  return (
    <span className={cn(BASE, LEASE_STATUS_STYLES[status], className)}>
      {LEASE_STATUS_LABELS[status]}
    </span>
  );
}

export function LicenceStatusBadge({ status }: { status: LicenceStatus }) {
  return (
    <span className={cn(BASE, LICENCE_STATUS_STYLES[status])}>
      {LICENCE_STATUS_LABELS[status]}
    </span>
  );
}

export function ObligationStatusBadge({ status }: { status: ObligationStatus }) {
  return (
    <span className={cn(BASE, OBLIGATION_STATUS_STYLES[status])}>
      {OBLIGATION_STATUS_LABELS[status]}
    </span>
  );
}

/** Deadline relative to today, escalating visually as it approaches or lapses. */
export function DueBadge({ days }: { days: number | null | undefined }) {
  if (days === null || days === undefined) return null;

  const style =
    days < 0
      ? RISK_STYLES.critical
      : days <= 14
        ? RISK_STYLES.high
        : days <= 30
          ? RISK_STYLES.medium
          : "border-border bg-muted text-muted-foreground";

  return <span className={cn(BASE, style)}>{formatDaysUntilShort(days)}</span>;
}
