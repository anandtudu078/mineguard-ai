"use client";

/**
 * Public self-registration page.
 *
 * Creates the Supabase auth user, then calls POST /auth/session so the API
 * provisions the `app_users` profile immediately (role comes from the server's
 * SELF_REGISTRATION_ROLE). The server decides the role - this page never
 * requests one.
 */

import { AlertCircle, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { getSupabaseBrowserClient } from "@/lib/supabase/browser";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function signUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");

    const client = getSupabaseBrowserClient();
    if (!client) {
      setError("Authentication is not configured on the client.");
      setBusy(false);
      return;
    }

    const { data, error: signUpError } = await client.auth.signUp({
      email,
      password,
      options: { data: { full_name: fullName || undefined } },
    });
    if (signUpError) {
      setError(signUpError.message);
      setBusy(false);
      return;
    }

    // Email confirmation on: no session yet - tell the person to check inbox.
    if (!data.session) {
      router.replace(`/login?registered=1`);
      return;
    }

    // Session immediately available (confirmation off): provision + enter.
    if (data.session.access_token) {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
      try {
        await fetch(`${apiBase}/api/v1/auth/session`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${data.session.access_token}`,
          },
        });
      } catch {
        // Provisioning happens on the first API call anyway; do not block.
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
            <h1 className="text-2xl font-semibold">Create your account</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Register to view mining sites and compliance deadlines.
            </p>
          </div>
        </div>
        <form onSubmit={signUp} className="space-y-4">
          <label className="block space-y-1.5 text-sm font-medium">
            Full name
            <input
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base outline-none focus:ring-2 focus:ring-ring"
              autoComplete="name"
            />
          </label>
          <label className="block space-y-1.5 text-sm font-medium">
            Email address
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base outline-none focus:ring-2 focus:ring-ring"
              autoComplete="email"
            />
          </label>
          <label className="block space-y-1.5 text-sm font-medium">
            Password
            <input
              required
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base outline-none focus:ring-2 focus:ring-ring"
              autoComplete="new-password"
              minLength={8}
            />
          </label>
          {error && (
            <p
              role="alert"
              className="flex items-start gap-2 rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300"
            >
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="min-h-11 w-full rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Creating account..." : "Create account"}
          </button>
        </form>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </section>
    </main>
  );
}
