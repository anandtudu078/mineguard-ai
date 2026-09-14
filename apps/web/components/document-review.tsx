"use client";

import { Check, CircleAlert, FileText } from "lucide-react";
import { useState } from "react";

import { updateLeaseDocument } from "@/lib/api-client";
import type { DocumentStatus, LeaseDocument } from "@/lib/types";

const STATUS_LABELS: Record<DocumentStatus, string> = {
  pending_review: "Needs review",
  accepted: "Accepted",
  needs_attention: "Needs attention",
  rejected: "Rejected",
};

export function DocumentReview({ leaseId, documents }: { leaseId: string; documents: LeaseDocument[] }) {
  const [items, setItems] = useState(documents);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function setStatus(documentId: string, status: DocumentStatus) {
    try {
      setBusyId(documentId);
      setError("");
      const updated = await updateLeaseDocument(leaseId, documentId, { status });
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Could not update this document.");
    } finally {
      setBusyId(null);
    }
  }

  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">No compliance documents uploaded yet.</p>;
  }

  return (
    <div>
      <ul className="space-y-3 text-sm">
        {items.map((document) => {
          const reviewPending = document.status === "pending_review";
          return (
            <li key={document.id} className="rounded-xl border border-border bg-background/45 p-3.5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-2.5">
                  <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
                    <FileText className="size-4" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{document.title}</p>
                    <p className="mt-0.5 truncate text-muted-foreground">{document.file_name}</p>
                  </div>
                </div>
                <span className="shrink-0 rounded-full bg-muted px-2.5 py-1 text-xs font-medium">
                  {STATUS_LABELS[document.status]}
                </span>
              </div>

              {document.extracted_expiry_date && (
                <p className="mt-3 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
                  This document says it ends on {document.extracted_expiry_date}.
                </p>
              )}

              {(document.extracted_authority || document.extracted_reference_number) && (
                <dl className="mt-3 grid gap-2 rounded-lg bg-primary/5 p-3 sm:grid-cols-2">
                  {document.extracted_authority && (
                    <div>
                      <dt className="text-xs text-muted-foreground">Authority</dt>
                      <dd className="font-medium">{document.extracted_authority}</dd>
                    </div>
                  )}
                  {document.extracted_reference_number && (
                    <div>
                      <dt className="text-xs text-muted-foreground">Reference number</dt>
                      <dd className="font-medium">{document.extracted_reference_number}</dd>
                    </div>
                  )}
                </dl>
              )}

              {reviewPending && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setStatus(document.id, "accepted")}
                    disabled={busyId === document.id}
                    className="inline-flex min-h-10 items-center gap-1.5 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
                  >
                    <Check className="size-4" aria-hidden />
                    Looks correct
                  </button>
                  <button
                    type="button"
                    onClick={() => setStatus(document.id, "needs_attention")}
                    disabled={busyId === document.id}
                    className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-amber-600/35 px-3 text-sm font-semibold text-amber-800 hover:bg-amber-500/10 disabled:opacity-50 dark:text-amber-300"
                  >
                    <CircleAlert className="size-4" aria-hidden />
                    Check this later
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}
