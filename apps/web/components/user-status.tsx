"use client";

import { LogOut, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { AppRole } from "@/lib/types";
import { getSupabaseBrowserClient } from "@/lib/supabase/browser";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const ROLE_LABELS: Record<AppRole, string> = {
  admin: "Administrator",
  inspector: "Inspector",
  operator: "Site operator",
};

interface Principal {
  label: string;
  email: string | null;
  role: AppRole | null;
  auth_enabled: boolean;
}

export function UserStatus({ compact = false }: { compact?: boolean }) {
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const router = useRouter();

  useEffect(() => {
    const controller = new AbortController();
    const client = getSupabaseBrowserClient();
    const sessionPromise = client
      ? client.auth.getSession()
      : Promise.resolve({ data: { session: null } });

    sessionPromise
      .then(({ data }: { data: { session: { access_token: string } | null } }) =>
        fetch(`${API_BASE_URL}/api/v1/auth/me`, {
          headers: {
            Accept: "application/json",
            ...(data?.session ? { Authorization: `Bearer ${data.session.access_token}` } : {}),
          },
          signal: controller.signal,
        }),
      )
      .then((response: Response) => (response.ok ? response.json() : null))
      .then((value: Principal | null) => setPrincipal(value))
      .catch(() => setPrincipal(null));
    return () => controller.abort();
  }, []);

  if (!principal) return null;

  const role = principal.role ? ROLE_LABELS[principal.role] : "Signed-in user";
  return (
    <div className={compact ? "flex items-center gap-2" : "flex items-center gap-2.5"}>
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-sidebar-primary/20 text-sidebar-primary">
        {principal.auth_enabled ? (
          <ShieldCheck className="size-4" aria-hidden />
        ) : (
          <UserRound className="size-4" aria-hidden />
        )}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold">{principal.label}</span>
        <span className="block truncate text-xs text-sidebar-foreground/60">{role}</span>
      </span>
      <button
        type="button"
        onClick={async () => {
          const client = getSupabaseBrowserClient();
          if (client) await client.auth.signOut();
          router.replace("/login");
          router.refresh();
        }}
        className="ml-auto rounded-md p-1.5 text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-foreground"
        aria-label="Sign out"
        title="Sign out"
      >
        <LogOut className="size-4" aria-hidden />
      </button>
    </div>
  );
}
