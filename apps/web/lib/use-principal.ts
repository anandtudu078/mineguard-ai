"use client";

/**
 * Client-side identity, resolved once from the API's `/auth/me`.
 *
 * When authentication is disabled on the server (development), the dev
 * principal comes back with `auth_enabled: false`; the server grants that
 * identity everything, so admin pages treat it as allowed too.
 */

import { useEffect, useState } from "react";

import type { AppRole } from "@/lib/types";
import { getSupabaseBrowserClient } from "@/lib/supabase/browser";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface Principal {
  user_id: string;
  email: string | null;
  label: string;
  role: AppRole | null;
  holder_id: string | null;
  is_authenticated: boolean;
  auth_enabled: boolean;
}

export function usePrincipal() {
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [loading, setLoading] = useState(true);

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
      .catch(() => setPrincipal(null))
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, []);

  const isAdmin =
    principal !== null && (principal.role === "admin" || !principal.auth_enabled);

  return { principal, loading, isAdmin };
}
