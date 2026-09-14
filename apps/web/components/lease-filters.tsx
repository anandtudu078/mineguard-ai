"use client";

/**
 * Lease register filters.
 *
 * Native `<select>` elements rather than a custom dropdown on purpose: on a
 * phone the OS renders its own picker, which is far easier to use with a thumb
 * than a popover, and it needs no extra JavaScript.
 *
 * State lives in the URL, so a filtered view is shareable and survives a
 * refresh - which matters when someone sends a colleague "the overdue leases in
 * Odisha" rather than describing how to reproduce it.
 */

import { Search, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  LEASE_STATUS_LABELS,
  LEASE_TYPE_LABELS,
  RISK_LABELS,
} from "@/lib/format";
import type { LeaseStatus, LeaseType, RiskLevel } from "@/lib/types";

const SELECT_CLASS =
  // min-h-11 keeps controls at a comfortable 44px touch target on phones while
  // staying visually dense on desktop.
  "flex h-11 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-xs outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40 disabled:opacity-50 sm:h-9";

const SORTS = [
  { value: "lease_number", label: "Lease number" },
  { value: "name", label: "Name" },
  { value: "state", label: "State" },
  { value: "effective_to", label: "Expiry date" },
  { value: "area_hectares", label: "Area" },
  { value: "compliance_score", label: "Compliance score" },
] as const;

export function LeaseFilters({ states }: { states: string[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const q = searchParams.get("q") ?? "";
  const [search, setSearch] = useState(q);
  const [lastSyncedQ, setLastSyncedQ] = useState(q);

  // React's "adjust state when a prop changes" pattern, done during render
  // rather than in an effect. This keeps the input in step when the URL changes
  // from elsewhere (clear filters, back button, or a link into a filtered view)
  // without an extra commit and without the cascading render an effect causes.
  if (q !== lastSyncedQ) {
    setLastSyncedQ(q);
    setSearch(q);
  }

  function apply(changes: Record<string, string | undefined>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (!value) params.delete(key);
      else params.set(key, value);
    }
    // Any filter change invalidates the current page offset.
    params.delete("offset");
    startTransition(() => {
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    });
  }

  // Debounce typing so each keystroke is not its own navigation.
  useEffect(() => {
    if (search === q) return;
    const timer = setTimeout(() => apply({ q: search || undefined }), 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const activeCount = ["q", "state", "status", "lease_type", "risk_level", "expiring_within_days"].filter(
    (key) => searchParams.get(key),
  ).length;

  return (
    <div
      className="mb-4 rounded-xl border border-border bg-card p-3 sm:p-4"
      data-pending={isPending || undefined}
    >
      <div className="grid gap-3 lg:grid-cols-12">
        {/* Search spans the full width on phones before the selects reflow. */}
        <div className="lg:col-span-4">
          <Label htmlFor="lease-search" className="mb-1.5 block text-xs">
            Search
          </Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              id="lease-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Lease number, name or village"
              className="h-11 pl-9 sm:h-9"
              autoComplete="off"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:col-span-8 lg:grid-cols-4">
          <FilterSelect
            id="filter-state"
            label="State"
            value={searchParams.get("state") ?? ""}
            onChange={(value) => apply({ state: value || undefined })}
            placeholder="All states"
            options={states.map((state) => ({ value: state, label: state }))}
          />

          <FilterSelect
            id="filter-status"
            label="Status"
            value={searchParams.get("status") ?? ""}
            onChange={(value) => apply({ status: value || undefined })}
            placeholder="Any status"
            options={(Object.keys(LEASE_STATUS_LABELS) as LeaseStatus[]).map((key) => ({
              value: key,
              label: LEASE_STATUS_LABELS[key],
            }))}
          />

          <FilterSelect
            id="filter-risk"
            label="Risk"
            value={searchParams.get("risk_level") ?? ""}
            onChange={(value) => apply({ risk_level: value || undefined })}
            placeholder="Any risk"
            options={(Object.keys(RISK_LABELS) as RiskLevel[]).map((key) => ({
              value: key,
              label: RISK_LABELS[key],
            }))}
          />

          <FilterSelect
            id="filter-type"
            label="Lease type"
            value={searchParams.get("lease_type") ?? ""}
            onChange={(value) => apply({ lease_type: value || undefined })}
            placeholder="Any type"
            options={(Object.keys(LEASE_TYPE_LABELS) as LeaseType[]).map((key) => ({
              value: key,
              label: LEASE_TYPE_LABELS[key],
            }))}
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-border pt-3">
        <div className="flex items-center gap-2">
          <Label htmlFor="filter-sort" className="text-xs">
            Sort
          </Label>
          <select
            id="filter-sort"
            value={searchParams.get("sort") ?? "lease_number"}
            onChange={(event) => apply({ sort: event.target.value })}
            className={`${SELECT_CLASS} h-9 w-auto min-w-40`}
          >
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={searchParams.get("descending") === "true"}
            onChange={(event) =>
              apply({ descending: event.target.checked ? "true" : undefined })
            }
            className="size-4 rounded border-input accent-primary"
          />
          Descending
        </label>

        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={searchParams.get("expiring_within_days") === "90"}
            onChange={(event) =>
              apply({
                expiring_within_days: event.target.checked ? "90" : undefined,
              })
            }
            className="size-4 rounded border-input accent-primary"
          />
          Expiring in 90 days
        </label>

        {activeCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => startTransition(() => router.replace(pathname, { scroll: false }))}
          >
            <X className="size-3.5" aria-hidden />
            Clear filters ({activeCount})
          </Button>
        )}
      </div>
    </div>
  );
}

function FilterSelect({
  id,
  label,
  value,
  onChange,
  options,
  placeholder,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
}) {
  return (
    <div className="min-w-0">
      <Label htmlFor={id} className="mb-1.5 block text-xs">
        {label}
      </Label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={SELECT_CLASS}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
