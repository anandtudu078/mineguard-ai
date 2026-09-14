"use client";

import { AlertCircle, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { getSupabaseBrowserClient } from "@/lib/supabase/browser";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");

    const client = getSupabaseBrowserClient();
    if (!client) {
      setError("Authentication is not configured on the client.");
      setBusy(false);
      return;
    }

    const { data: signInData, error: signInError } = await client.auth.signInWithPassword({
      email,
      password,
    });
    if (signInError) {
      setError(signInError.message);
      setBusy(false);
      return;
    }

    if (signInData.session?.access_token) {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
      try {
        await fetch(`${apiBase}/api/v1/auth/session`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${signInData.session.access_token}`,
          },
        });
      } catch {
        // Audit record is best-effort on login; do not block user navigation.
      }
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
            <h1 className="text-2xl font-semibold">Welcome to MineGuard</h1>
            <p className="mt-1 text-sm text-muted-foreground">Sign in to view your mining sites and deadlines.</p>
          </div>
        </div>
        <form onSubmit={signIn} className="space-y-4">
          <label className="block space-y-1.5 text-sm font-medium">
            Email address
            <input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base outline-none focus:ring-2 focus:ring-ring" autoComplete="email" />
          </label>
          <label className="block space-y-1.5 text-sm font-medium">
            Password
            <input required type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base outline-none focus:ring-2 focus:ring-ring" autoComplete="current-password" />
          </label>
          {error && <p role="alert" className="flex items-start gap-2 rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300"><AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="min-h-11 w-full rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          New here?{" "}
          <Link href="/register" className="font-medium text-primary hover:underline">
            Create an account
          </Link>
        </p>
      </section>
    </main>
  );
}
