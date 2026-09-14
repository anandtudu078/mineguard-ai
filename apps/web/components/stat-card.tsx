import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "good" | "warn" | "bad";

const TONE_STYLES: Record<Tone, string> = {
  neutral: "text-foreground",
  good: "text-emerald-600 dark:text-emerald-400",
  warn: "text-amber-600 dark:text-amber-400",
  bad: "text-red-600 dark:text-red-400",
};

/**
 * A single headline figure.
 *
 * Two columns on a phone rather than one: these tiles are short, and stacking
 * them full width would push the rest of the dashboard several screens down.
 */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  tone?: Tone;
}) {
  return (
    <Card className="gap-0 border-transparent bg-card/85 p-3.5 shadow-[0_10px_30px_-24px_oklch(0.25_0.06_170)] ring-1 ring-foreground/8 transition-transform duration-200 hover:-translate-y-0.5 hover:ring-primary/25 sm:p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-muted-foreground sm:text-base">{label}</p>
        {Icon && (
          <Icon className="size-4 shrink-0 text-primary/70" aria-hidden />
        )}
      </div>

      <p
        className={cn(
          "mt-1.5 text-2xl font-semibold tabular-nums leading-none sm:text-3xl",
          TONE_STYLES[tone],
        )}
      >
        {value}
      </p>

      {hint && <p className="mt-1.5 text-xs text-muted-foreground">{hint}</p>}
    </Card>
  );
}
