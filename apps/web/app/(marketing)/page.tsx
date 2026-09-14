import { ArrowRight, CalendarClock, Gauge, LayoutDashboard, Map } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "MineGuard — Mining compliance made clear",
};

/**
 * Public landing page.
 *
 * The root layout serves this route without the app shell (sidebar, tab bar),
 * so the flow is: landing -> login -> dashboard. The login page shares the
 * same bare wrapper, which keeps the pre-auth experience visually one piece.
 */
export default function LandingPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="grid size-8 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground"
          >
            <svg viewBox="0 0 24 24" className="size-4.5" fill="none" strokeWidth={2.2}>
              <path
                d="M3 20h18M6 20V9l6-5 6 5v11"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span className="text-sm font-semibold">MineGuard</span>
        </div>
        <Link
          href="/login"
          className="inline-flex min-h-11 items-center rounded-lg border border-input bg-background px-4 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          Sign in
        </Link>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center px-4 py-12 sm:px-6">
        <section className="mx-auto w-full max-w-3xl text-center">
          <p className="mb-4 inline-flex items-center rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
            Compliance governance for mineral concessions
          </p>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            Mining compliance, made clear.
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            A single register of leases, statutory clearances and filing
            deadlines — with an explainable risk score for every concession.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/login"
              className="group inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary px-6 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 sm:w-auto"
            >
              Sign in to your dashboard
              <ArrowRight
                className="size-4 transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </Link>
            <a
              href="#features"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-input bg-background px-6 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground sm:w-auto"
            >
              See what&apos;s inside
            </a>
          </div>
        </section>

        <section
          id="features"
          className="mx-auto mt-16 grid w-full max-w-4xl gap-4 sm:grid-cols-2"
        >
          <FeatureCard
            icon={LayoutDashboard}
            title="Portfolio overview"
            body="Health scores, past-due work and expiring permissions across every site, the moment you sign in."
          />
          <FeatureCard
            icon={Map}
            title="Spatial lease register"
            body="Every concession mapped with its boundary, holder, status and compliance position."
          />
          <FeatureCard
            icon={CalendarClock}
            title="Compliance calendar"
            body="Filing obligations derived from the register, grouped by month and flagged before they lapse."
          />
          <FeatureCard
            icon={Gauge}
            title="Explainable risk scoring"
            body="Scores recompute from the underlying records, with each component and its reasoning shown."
          />
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto w-full max-w-6xl px-4 py-6 text-xs leading-relaxed text-muted-foreground sm:px-6">
          Reference data shown is illustrative. Verify rates and deadlines
          against the current statute before relying on them.
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof LayoutDashboard;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <span className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
        <Icon className="size-5" aria-hidden />
      </span>
      <h2 className="mt-3 text-base font-semibold">{title}</h2>
      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{body}</p>
    </div>
  );
}
