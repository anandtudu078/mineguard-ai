/**
 * Formatting helpers and human labels for the API's controlled vocabularies.
 *
 * Dates are parsed and rendered in UTC deliberately. A bare "2026-03-12" is
 * midnight UTC, so formatting it in the runtime's local zone would render
 * 11 March for anyone west of Greenwich - and produce a server/client hydration
 * mismatch, since the server's zone is not the viewer's.
 */

import type {
  LeaseStatus,
  LeaseType,
  LicenceStatus,
  LicenceType,
  MineralCategory,
  ObligationCategory,
  ObligationStatus,
  RiskLevel,
} from "./types";

/** Convert an API decimal (serialised as a string) into a number. */
export function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseISODate(iso: string): Date {
  return new Date(iso.length <= 10 ? `${iso}T00:00:00Z` : iso);
}

const SHORT_DATE = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

const DAY_MONTH = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  timeZone: "UTC",
});

const MONTH_YEAR = new Intl.DateTimeFormat("en-GB", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return SHORT_DATE.format(parseISODate(iso));
}

/** Compact form for dense table columns, omitting the year when it is current. */
export function formatDateCompact(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = parseISODate(iso);
  return date.getUTCFullYear() === new Date().getUTCFullYear()
    ? DAY_MONTH.format(date)
    : SHORT_DATE.format(date);
}

export function formatMonthYear(iso: string): string {
  return MONTH_YEAR.format(parseISODate(iso));
}

/** Area in hectares, thousand-separated. */
export function formatArea(hectares: string | number | null | undefined): string {
  const value = toNumber(hectares);
  if (value === null) return "—";
  return `${value.toLocaleString("en-GB", { maximumFractionDigits: 1 })} ha`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("en-GB");
}

export function formatPercent(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined) return "—";
  return `${Math.round(ratio * 100)}%`;
}

/**
 * Turn a signed day offset into something an operator reads at a glance.
 * Negative means overdue.
 */
export function formatDaysUntil(days: number | null | undefined): string {
  if (days === null || days === undefined) return "—";
  if (days < 0) {
    const overdue = Math.abs(days);
    return overdue === 1 ? "1 day overdue" : `${overdue} days overdue`;
  }
  if (days === 0) return "Due today";
  if (days === 1) return "Due tomorrow";
  return `Due in ${days} days`;
}

/** Short variant for table cells and badges. */
export function formatDaysUntilShort(days: number | null | undefined): string {
  if (days === null || days === undefined) return "—";
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return "today";
  return `in ${days}d`;
}

// ---------------------------------------------------------------------------
// Labels
// ---------------------------------------------------------------------------
export const LEASE_TYPE_LABELS: Record<LeaseType, string> = {
  prospecting_licence: "Prospecting licence",
  mining_lease: "Mining lease",
  quarry_lease: "Quarry lease",
  composite_licence: "Composite licence",
};

export const LEASE_STATUS_LABELS: Record<LeaseStatus, string> = {
  pending: "Pending",
  active: "Active",
  pending_renewal: "Pending renewal",
  suspended: "Suspended",
  expired: "Expired",
  surrendered: "Surrendered",
  revoked: "Revoked",
};

export const LICENCE_TYPE_LABELS: Record<LicenceType, string> = {
  environmental_clearance: "Environmental clearance",
  forest_clearance: "Forest clearance",
  consent_to_operate: "Consent to operate",
  mining_plan_approval: "Mining plan approval",
  ground_water_ntoc: "Ground water NOC",
  explosive_licence: "Explosive licence",
  drone_survey_approval: "Drone survey approval",
  lease_deed: "Lease deed",
};

export const LICENCE_STATUS_LABELS: Record<LicenceStatus, string> = {
  pending: "Pending",
  valid: "Valid",
  expiring_soon: "Expiring soon",
  expired: "Expired",
  revoked: "Revoked",
};

export const OBLIGATION_STATUS_LABELS: Record<ObligationStatus, string> = {
  pending: "Pending",
  in_progress: "In progress",
  submitted: "Filed",
  overdue: "Overdue",
  waived: "Waived",
  not_applicable: "Not applicable",
};

export const OBLIGATION_CATEGORY_LABELS: Record<ObligationCategory, string> = {
  return_filing: "Return filing",
  payment: "Payment",
  inspection: "Inspection",
  safety: "Safety",
  environment: "Environment",
  social: "Social",
  reporting: "Reporting",
};

export const MINERAL_CATEGORY_LABELS: Record<MineralCategory, string> = {
  major: "Major mineral",
  minor: "Minor mineral",
};

export const RISK_LABELS: Record<RiskLevel, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export function titleCase(value: string): string {
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
