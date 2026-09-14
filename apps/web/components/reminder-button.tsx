"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

export function ReminderButton({
  title,
  siteName,
  dueDate,
}: {
  title: string;
  siteName: string;
  dueDate: string;
}) {
  const [copied, setCopied] = useState(false);
  const message = `Reminder: ${title} for ${siteName} is due on ${dueDate}. Please review and upload proof when complete.`;

  async function copyReminder() {
    await navigator.clipboard.writeText(message);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <button
      type="button"
      onClick={copyReminder}
      className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-border bg-background px-3 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
      aria-label={`Copy reminder for ${title}`}
    >
      {copied ? <Check className="size-4 text-emerald-600" aria-hidden /> : <Copy className="size-4" aria-hidden />}
      {copied ? "Copied" : "Copy reminder"}
    </button>
  );
}
