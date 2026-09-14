"use client";

/**
 * Landing point for Supabase invite links.
 *
 * The invite email sends the recipient here with session tokens in the URL
 * fragment, which only the browser client can read (the middleware deliberately
 * exempts this path). Supabase's browser client consumes the fragment and
 * establishes a session; the person then sets their password and continues to
 * the dashboard.
 */

import { AlertCircle, Loader2, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getSupabaseBrowserClient } from "@/lib/supabase/browser";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // The browser client picks up the fragment tokens as it initialises, which
  // can land just after this effect runs; poll briefly before giving up.
  useEffect(() => {
    let cancelled = false;
    const client = getSupabaseBrowserClient();

    async function waitForSession() {
      for (let attempt = 0; attempt < 10; attempt++) {
        if (!client) break;
        const { data } = await client.auth.getSession();
        if (data.session && !cancelled) {
          setReady(true);
          setChecking(false);
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 400));
      }
      if (!cancelled) {
        setChecking(false);
      }
    }

    void waitForSession();
    return () => {
      cancelled = true;
    };
  }, []);

  async function setPassword_(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);

    const client = getSupabaseBrowserClient();
    if (!client) {
      setError("Authentication is not configured on the client.");
      setBusy(false);
      return;
    }

    const { error: updateError } = await client.auth.updateUser({ password });
    if (updateError) {
      setError(updateError.message);
      setBusy(false);
      return;
    }

    router.replace("/dashboard");
    router.refresh();
  }

  return (
    <main className="grid min-h-dvh place-items-center px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl sm:p-8">
        <div className="mb-7 flex items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground">
            <ShieldCheck className="size-6" aria-hidden />
          </span>
          <div>
            <h1 className="text-2xl font-semibold">Set your password</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Finish setting up your MineGuard account.
            </p>
          </div>
        </div>

        {checking && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Verifying your invitation…
          </p>
        )}

        {!checking && !ready && (
          <div className="space-y-3">
            <p role="alert" className="flex items-start gap-2 rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300">
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
              This invitation link is invalid or has expired. Ask an administrator to send a
              new invite.
            </p>
          </div>
        )}

        {ready && (
          <form onSubmit={setPassword_} className="space-y-4">
            <label className="block space-y-1.5 text-sm font-medium">
              New password
              <input
                required
                type="password"
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base outline-none focus:ring-2 focus:ring-ring"
                autoComplete="new-password"
              />
            </label>
            <label className="block space-y-1.5 text-sm font-medium">
              Confirm password
              <input
                required
                type="password"
                minLength={8}
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base outline-none focus:ring-2 focus:ring-ring"
                autoComplete="new-password"
              />
            </label>
            {error && (
              <p role="alert" className="flex items-start gap-2 rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300">
                <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={busy}
              className="min-h-11 w-full rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Saving…" : "Save password and continue"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
