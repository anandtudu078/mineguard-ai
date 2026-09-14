"use client";

/**
 * Authenticated fetch for client components.
 *
 * `lib/api.ts` targets server components (it reads cookies through
 * `next/headers`), so client pages that mutate — invites, filings — use this
 * instead: same base URL, plus the Supabase access token when a session
 * exists.
 */

import { getSupabaseBrowserClient } from "@/lib/supabase/browser";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ClientApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ClientApiError";
  }
}

export async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const client = getSupabaseBrowserClient();
  let accessToken: string | undefined;
  if (client) {
    const { data } = await client.auth.getSession();
    accessToken = data.session?.access_token;
  }

  // The browser must set Content-Type itself for multipart bodies so the
  // form boundary is included; pre-setting it breaks the upload.
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;

  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body; status text is the best we have.
    }
    throw new ClientApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
