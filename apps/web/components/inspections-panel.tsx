"use client";

/**
 * Inspection & action tracking for one lease (the demo-arc UI).
 *
 * Photo in: an operator or inspector drops a site photo, the API runs Gemini
 * vision and records findings. Each finding can be acknowledged, assigned a
 * corrective action, escalated, and resolved — and resolving it recovers the
 * lease's compliance score, which the adjacent panel re-renders on refresh.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  Eye,
  Loader2,
  ShieldAlert,
  Siren,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authedFetch } from "@/lib/client-api";
import type {
  AnalyzeResponse,
  EscalationStats,
  InspectionFinding,
} from "@/lib/types";

const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;

const ANALYZE_RUNNING = "Analysing photo…";
const EMPTY_FINDINGS = "No findings recorded yet for this lease.";
const SWEEP_NOTHING = "Nothing stale enough to escalate right now.";
const SWEEP_LABEL = "Run 48h escalation sweep";
const FINDING_ACTION_LABELS = {
  acknowledge: "Acknowledge",
  assign: "Assign action",
  resolve: "Resolve",
} as const;

const SEVERITY_STYLES: Record<string, string> = {
  critical: "border-destructive/40 bg-destructive/5",
  high: "border-amber-600/40 bg-amber-500/5",
  medium: "border-border bg-muted/30",
  low: "border-border",
};

export function InspectionsPanel({ leaseId }: { leaseId: string }) {
  const [findings, setFindings] = useState<InspectionFinding[] | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [sweeping, setSweeping] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadFindings = useCallback(async () => {
    try {
      const data = await authedFetch<{ items: InspectionFinding[] }>(
        `/leases/${leaseId}/findings?limit=100`,
      );
      setFindings(
        [...data.items].sort(
          (a, b) =>
            SEVERITY_ORDER.indexOf(a.severity as (typeof SEVERITY_ORDER)[number]) -
            SEVERITY_ORDER.indexOf(b.severity as (typeof SEVERITY_ORDER)[number]),
        ),
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    }
  }, [leaseId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await authedFetch<{ items: InspectionFinding[] }>(
          `/leases/${leaseId}/findings?limit=100`,
        );
        if (!cancelled) {
          setFindings(
            [...data.items].sort(
              (a, b) =>
                SEVERITY_ORDER.indexOf(a.severity as (typeof SEVERITY_ORDER)[number]) -
                SEVERITY_ORDER.indexOf(b.severity as (typeof SEVERITY_ORDER)[number]),
            ),
          );
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : String(loadError));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leaseId]);

  async function handleAnalyze(event: React.FormEvent) {
    event.preventDefault();
    if (!file || analyzing) return;
    setAnalyzing(true);
    setError(null);
    setAnalysis(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("auto_alert", "true");
      const result = await authedFetch<AnalyzeResponse>(
        `/leases/${leaseId}/findings/analyze`,
        { method: "POST", body: form },
      );
      setAnalysis(result);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadFindings();
    } catch (analyzeError) {
      setError(analyzeError instanceof Error ? analyzeError.message : String(analyzeError));
    } finally {
      setAnalyzing(false);
    }
  }

  async function act(finding: InspectionFinding, action: string, body?: unknown) {
    setBusyId(finding.id);
    setError(null);
    try {
      const path = `/leases/${leaseId}/findings/${finding.id}`;
      const method = action === "update" ? "PATCH" : "POST";
      const suffix =
        action === "update"
          ? ""
          : action === "acknowledge"
            ? "/acknowledge"
            : "/resolve";
      await authedFetch<InspectionFinding>(`${path}${suffix}`, {
        method,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      await loadFindings();
    } catch (actError) {
      setError(actError instanceof Error ? actError.message : String(actError));
    } finally {
      setBusyId(null);
    }
  }

  async function runSweep() {
    setSweeping(true);
    setError(null);
    try {
      const stats = await authedFetch<EscalationStats>(
        `/leases/${leaseId}/findings/escalation-sweep`,
        { method: "POST" },
      );
      if (stats.escalated > 0) {
        await loadFindings();
      } else {
        setError(SWEEP_NOTHING);
      }
    } catch (sweepError) {
      setError(sweepError instanceof Error ? sweepError.message : String(sweepError));
    } finally {
      setSweeping(false);
    }
  }

  const openCount = (findings ?? []).filter(
    (f) => f.status === "open" || f.status === "in_progress",
  ).length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Camera className="size-4" aria-hidden />
            Inspections &amp; AI findings
          </span>
          {openCount > 0 ? (
            <Badge variant="destructive">
              {openCount} open
            </Badge>
          ) : (
            <Badge variant="outline">All clear</Badge>
          )}
        </CardTitle>
        <CardDescription>
          Drop a site photo — the vision model flags safety and environmental
          violations, alerts the holder, and tracks remediation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleAnalyze} className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="site-photo">Site photo</Label>
            <Input
              id="site-photo"
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <Button type="submit" disabled={!file || analyzing}>
            {analyzing ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden />
                {ANALYZE_RUNNING}
              </>
            ) : (
              <>
                <ShieldAlert className="size-4" aria-hidden />
                Detect violations
              </>
            )}
          </Button>
        </form>

        {error && (
          <p className="rounded-md border border-destructive/30 bg-destructive/5 p-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {analysis?.summary && (
          <div className="rounded-md border bg-muted/40 p-3 text-sm">
            <p className="font-medium">Vision summary</p>
            <p className="mt-1 text-muted-foreground">{analysis.summary}</p>
          </div>
        )}

        {findings === null ? (
          <p className="text-sm text-muted-foreground">Loading findings…</p>
        ) : findings.length === 0 ? (
          <p className="text-sm text-muted-foreground">{EMPTY_FINDINGS}</p>
        ) : (
          <ul className="space-y-3">
            {findings.map((finding) => (
              <li
                key={finding.id}
                className={`rounded-lg border p-3 ${
                  finding.status === "resolved" || finding.status === "false_positive"
                    ? "opacity-60"
                    : SEVERITY_STYLES[finding.severity]
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="capitalize">
                    {finding.severity}
                  </Badge>
                  <span className="text-sm font-medium">{finding.title}</span>
                  {finding.source === "ai_vision" && finding.confidence !== null && (
                    <span className="ml-auto text-xs text-muted-foreground">
                      {Math.round(finding.confidence * 100)}% · {finding.ai_model}
                    </span>
                  )}
                </div>

                {finding.description && (
                  <p className="mt-1.5 text-sm text-muted-foreground">{finding.description}</p>
                )}
                {finding.corrective_action && (
                  <p className="mt-1.5 text-sm">
                    <span className="font-medium">Action: </span>
                    {finding.corrective_action}
                  </p>
                )}
                {finding.escalation_level > 0 && (
                  <p className="mt-1.5 flex items-center gap-1 text-xs text-amber-700">
                    <Siren className="size-3" aria-hidden />
                    Escalated {finding.escalation_level}×
                    {finding.last_escalated_at
                      ? ` · ${new Date(finding.last_escalated_at).toLocaleString()}`
                      : null}
                  </p>
                )}
                {finding.status === "resolved" && finding.resolution_note && (
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    Resolved: {finding.resolution_note}
                  </p>
                )}

                <div className="mt-2.5 flex flex-wrap gap-2">
                  {finding.status === "open" && !finding.acknowledged_at && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busyId === finding.id}
                      onClick={() => act(finding, "acknowledge")}
                    >
                      <Eye className="size-3.5" aria-hidden />
                      {FINDING_ACTION_LABELS.acknowledge}
                    </Button>
                  )}
                  {(finding.status === "open" || finding.status === "in_progress") && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busyId === finding.id}
                        onClick={() =>
                          act(finding, "update", {
                            corrective_action:
                              finding.corrective_action ?? "Remediate and verify on site",
                          })
                        }
                      >
                        <AlertTriangle className="size-3.5" aria-hidden />
                        {FINDING_ACTION_LABELS.assign}
                      </Button>
                      <Button
                        size="sm"
                        disabled={busyId === finding.id}
                        onClick={() =>
                          act(finding, "resolve", {
                            resolution_note: "Verified closed by operator.",
                          })
                        }
                      >
                        <CheckCircle2 className="size-3.5" aria-hidden />
                        {FINDING_ACTION_LABELS.resolve}
                      </Button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}

        <div className="border-t border-border pt-3">
          <Button size="sm" variant="ghost" onClick={runSweep} disabled={sweeping}>
            {sweeping ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <Siren className="size-3.5" aria-hidden />
            )}
            {SWEEP_LABEL}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
