/**
 * Typed client for the mining governance API.
 *
 * All reads go through `apiFetch`, which gives one place to control caching,
 * error shaping and the timeout. Server components call these directly; client
 * components call the `/api/proxy` route so the browser never needs to know the
 * backend URL.
 */

import type {
  CalendarEntry,
  ComplianceScore,
  DashboardSummary,
  Lease,
  LeaseDocument,
  LeaseFeatureCollection,
  LeaseListItem,
  Licence,
  Mineral,
  ObligationRule,
  Page,
  TimelineEntry,
  ReminderPreview,
  ReminderDelivery,
} from "./types";
import { getSupabaseServerClient } from "./supabase/server";

const SERVER_BASE_URL =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000";

/** Thrown for any non-2xx response, carrying the status for callers to branch on. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type QueryValue = string | number | boolean | undefined | null | (string | number)[];

/** Build a query string, dropping empty values and repeating array entries. */
export function buildQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const entry of value) search.append(key, String(entry));
    } else {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // A hung backend should surface as an error the UI can show, not a page that
  // spins forever.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);

  try {
    let accessToken: string | undefined;
    const supabase = await getSupabaseServerClient();
    if (supabase) {
      const { data } = await supabase.auth.getSession();
      accessToken = data.session?.access_token;
    }
    const response = await fetch(`${SERVER_BASE_URL}/api/v1${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...init?.headers,
      },
      // Compliance state is time-sensitive; a stale cache would show the wrong
      // risk picture. Revalidate briefly instead.
      next: { revalidate: 30 },
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        // Non-JSON error body; the status text is the best we have.
      }
      throw new ApiError(response.status, detail);
    }

    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
export function getDashboardSummary(params: { as_of?: string } = {}) {
  return apiFetch<DashboardSummary>(`/dashboard/summary${buildQuery(params)}`);
}

// ---------------------------------------------------------------------------
// Leases
// ---------------------------------------------------------------------------
export interface LeaseFilters {
  q?: string;
  state?: string;
  district?: string;
  status?: string[];
  lease_type?: string[];
  risk_level?: string[];
  expiring_within_days?: number;
  sort?: string;
  descending?: boolean;
  limit?: number;
  offset?: number;
  as_of?: string;
}

export function getLeases(filters: LeaseFilters = {}) {
  return apiFetch<Page<LeaseListItem>>(`/leases${buildQuery({ limit: 50, ...filters })}`);
}

export function getLease(id: string) {
  return apiFetch<Lease>(`/leases/${id}`);
}

export function getLeaseCompliance(id: string, asOf?: string) {
  return apiFetch<ComplianceScore>(
    `/leases/${id}/compliance${buildQuery({ as_of: asOf })}`,
  );
}

export function getLeaseLicences(id: string, asOf?: string) {
  return apiFetch<Licence[]>(`/leases/${id}/licences${buildQuery({ as_of: asOf })}`);
}

export function getLeaseTimeline(id: string, asOf?: string, limit = 50) {
  return apiFetch<TimelineEntry[]>(
    `/leases/${id}/timeline${buildQuery({ as_of: asOf, limit })}`,
  );
}

export function getLeaseDocuments(id: string, offset = 0, limit = 20) {
  return apiFetch<Page<LeaseDocument>>(
    `/leases/${id}/documents${buildQuery({ offset, limit })}`,
  );
}

export async function uploadLeaseDocument(
  leaseId: string,
  formData: FormData,
): Promise<LeaseDocument> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);

  try {
    const response = await fetch(`${SERVER_BASE_URL}/api/v1/leases/${leaseId}/documents`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
      headers: { Accept: "application/json" },
      next: { revalidate: 30 },
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        // ignore
      }
      throw new ApiError(response.status, detail);
    }

    return (await response.json()) as LeaseDocument;
  } finally {
    clearTimeout(timeout);
  }
}

export function updateLeaseDocument(
  leaseId: string,
  documentId: string,
  payload: { status?: LeaseDocument["status"]; notes?: string },
) {
  return apiFetch<LeaseDocument>(
    `/leases/${leaseId}/documents/${documentId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

/** Leases whose term lapses soon, worst deadline first. */
export function getExpiringLeases(withinDays = 90, asOf?: string) {
  return apiFetch<Lease[]>(
    `/leases/expiring${buildQuery({ within_days: withinDays, as_of: asOf })}`,
  );
}

/**
 * The whole matching register as one GeoJSON FeatureCollection.
 *
 * One request rather than one per lease, and each feature carries its
 * compliance posture so the map can colour itself without a second call.
 */
export function getLeaseGeoJSON(filters: LeaseFilters = {}) {
  return apiFetch<LeaseFeatureCollection>(
    `/leases/geojson${buildQuery({ limit: 1000, ...filters })}`,
  );
}

// ---------------------------------------------------------------------------
// Calendar
// ---------------------------------------------------------------------------
export type EntryState = "overdue" | "due_soon" | "upcoming" | "filed";

export interface CalendarFilters {
  lease_id?: string;
  date_from?: string;
  date_to?: string;
  status?: string[];
  category?: string[];
  lease_type?: string[];
  entry_state?: EntryState;
  state?: string;
  district?: string;
  requires_payment?: boolean;
  overdue_only?: boolean;
  limit?: number;
  offset?: number;
  as_of?: string;
}

export function getCalendar(filters: CalendarFilters = {}) {
  return apiFetch<Page<CalendarEntry>>(`/calendar${buildQuery({ limit: 50, ...filters })}`);
}

export function getReminderPreview(days = 30, limit = 100, asOf?: string) {
  return apiFetch<ReminderPreview[]>(
    `/calendar/reminders/preview${buildQuery({ days, limit, as_of: asOf })}`,
  );
}

export function getReminderHistory(limit = 20) {
  return apiFetch<ReminderDelivery[]>(
    `/calendar/reminders/history${buildQuery({ limit })}`,
  );
}

export function getCalendarWindow(asOf?: string) {
  return apiFetch<{
    window_start: string;
    window_end: string;
    fiscal_year_end_month: number;
  }>(`/calendar/window${buildQuery({ as_of: asOf })}`);
}

// ---------------------------------------------------------------------------
// Reference data
// ---------------------------------------------------------------------------
export function getMinerals(params: { limit?: number; is_active?: boolean } = {}) {
  return apiFetch<Page<Mineral>>(`/minerals${buildQuery({ limit: 100, ...params })}`);
}

export function getObligationRules(params: { limit?: number; is_active?: boolean } = {}) {
  return apiFetch<Page<ObligationRule>>(
    `/obligations${buildQuery({ limit: 100, ...params })}`,
  );
}
