import { getSupabaseBrowserClient } from "@/lib/supabase/browser";
import type { LeaseDocument } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function accessToken() {
  const client = getSupabaseBrowserClient();
  if (!client) return undefined;
  const { data } = await client.auth.getSession();
  return data.session?.access_token;
}

export async function uploadLeaseDocument(leaseId: string, formData: FormData) {
  const token = await accessToken();
  const response = await fetch(`${API_BASE_URL}/api/v1/leases/${leaseId}/documents`, {
    method: "POST",
    body: formData,
    headers: { Accept: "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
  return (await response.json()) as LeaseDocument;
}

export async function updateLeaseDocument(
  leaseId: string,
  documentId: string,
  payload: { status?: LeaseDocument["status"]; notes?: string },
) {
  const token = await accessToken();
  const response = await fetch(`${API_BASE_URL}/api/v1/leases/${leaseId}/documents/${documentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
  return (await response.json()) as LeaseDocument;
}
