"use client";

import { Loader2, UserPlus, UsersRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authedFetch, ClientApiError } from "@/lib/client-api";
import { usePrincipal } from "@/lib/use-principal";
import type { AppUser, Holder } from "@/lib/types";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  inspector: "Inspector",
  operator: "Site operator",
};

interface PrincipalWithPermissions {
  permissions?: string[];
}

export default function UsersPage() {
  const { principal, loading: principalLoading, isAdmin } = usePrincipal();

  const [users, setUsers] = useState<AppUser[] | null>(null);
  const [holders, setHolders] = useState<Holder[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "inspector" | "operator">("inspector");
  const [inviteHolder, setInviteHolder] = useState<string>("");
  const [inviteBusy, setInviteBusy] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteDone, setInviteDone] = useState<string | null>(null);

  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  const canManage = useMemo(() => {
    if (!principal) return false;
    if (!principal.auth_enabled) return true; // dev principal
    const perms = (principal as PrincipalWithPermissions).permissions;
    return perms ? perms.includes("user:manage") : isAdmin;
  }, [principal, isAdmin]);

  const refreshUsers = useCallback(async () => {
    try {
      setUsers(await authedFetch<AppUser[]>(`/users`));
      setError(null);
    } catch {
      setError("Could not load users.");
    }
  }, []);

  useEffect(() => {
    if (!canManage || users !== null) return;
    let cancelled = false;

    async function initialLoad() {
      const [usersResult, holdersResult] = await Promise.all([
        authedFetch<AppUser[]>(`/users`),
        authedFetch<{ items: Holder[] }>(`/holders?limit=200`).catch(() => ({ items: [] })),
      ]);
      if (cancelled) return;
      setUsers(usersResult);
      setHolders(holdersResult.items);
    }

    initialLoad().catch(() => {
      if (!cancelled) setError("Could not load users.");
    });

    return () => {
      cancelled = true;
    };
  }, [canManage, users]);

  async function submitInvite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setInviteBusy(true);
    setInviteError(null);
    setInviteDone(null);
    try {
      const created = await authedFetch<AppUser>(`/users/invite`, {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail.trim(),
          full_name: inviteName.trim() || undefined,
          role: inviteRole,
          holder_id: inviteHolder || null,
        }),
      });
      setInviteDone(`Invite sent to ${created.email}. They will set a password via the email link.`);
      setInviteEmail("");
      setInviteName("");
      setShowInvite(false);
      await refreshUsers();
    } catch (err) {
      setInviteError(err instanceof ClientApiError ? err.message : "Could not send the invite.");
    } finally {
      setInviteBusy(false);
    }
  }

  async function toggleActive(user: AppUser) {
    setBusyUserId(user.id);
    try {
      await authedFetch(`/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      await refreshUsers();
    } catch {
      setError("Could not update the user.");
    } finally {
      setBusyUserId(null);
    }
  }

  if (principalLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
        <Loader2 className="size-5 animate-spin" aria-hidden />
      </div>
    );
  }

  if (!canManage) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>Administrators only</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          User management is restricted to administrators.{" "}
          <Link href="/dashboard" className="text-primary hover:underline">
            Back to the dashboard
          </Link>
          .
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Users</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Invite colleagues and manage what they can see and do.
          </p>
        </div>
        <Button onClick={() => setShowInvite((v) => !v)} className="min-h-11">
          <UserPlus className="size-4" aria-hidden />
          Invite user
        </Button>
      </div>

      {showInvite && (
        <Card className="mb-5">
          <CardHeader>
            <CardTitle>Invite a colleague</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submitInvite} className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="invite-email">Email address</Label>
                <Input
                  id="invite-email"
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="h-11"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="invite-name">Full name</Label>
                <Input
                  id="invite-name"
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  placeholder="Optional"
                  className="h-11"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="invite-role">Role</Label>
                <select
                  id="invite-role"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as typeof inviteRole)}
                  className="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm"
                >
                  <option value="inspector">Inspector — read-only oversight</option>
                  <option value="operator">Site operator — scoped to one holder</option>
                  <option value="admin">Administrator — full control</option>
                </select>
              </div>
              {inviteRole === "operator" && (
                <div className="space-y-1.5">
                  <Label htmlFor="invite-holder">Lease holder (organisation)</Label>
                  <select
                    id="invite-holder"
                    required
                    value={inviteHolder}
                    onChange={(e) => setInviteHolder(e.target.value)}
                    className="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm"
                  >
                    <option value="">Select a holder…</option>
                    {holders.map((holder) => (
                      <option key={holder.id} value={holder.id}>
                        {holder.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
                <Button type="submit" disabled={inviteBusy} className="min-h-11">
                  {inviteBusy ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                  ) : (
                    <UserPlus className="size-4" aria-hidden />
                  )}
                  Send invite
                </Button>
                {inviteError && <p className="text-sm text-red-600 dark:text-red-400">{inviteError}</p>}
                {inviteDone && <p className="text-sm text-emerald-700 dark:text-emerald-400">{inviteDone}</p>}
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {error && (
        <p role="alert" className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UsersRound className="size-4.5 text-muted-foreground" aria-hidden />
            {users ? `${users.length} user${users.length === 1 ? "" : "s"}` : "Users"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {users === null ? (
            <div className="flex justify-center py-8">
              <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
            </div>
          ) : users.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No users yet. Invite the first colleague to get started.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {users.map((user) => (
                <li key={user.id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {user.full_name || user.email || user.id}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {user.email}
                      {user.last_seen_at
                        ? ` · last seen ${new Date(user.last_seen_at).toLocaleDateString()}`
                        : " · not signed in yet"}
                    </p>
                  </div>
                  <Badge variant="outline">{ROLE_LABELS[user.role] ?? user.role}</Badge>
                  {user.holder_id && (
                    <Badge variant="secondary" className="max-w-40 truncate">
                      {holders.find((h) => h.id === user.holder_id)?.name ?? "Holder"}
                    </Badge>
                  )}
                  <Badge variant={user.is_active ? "default" : "destructive"}>
                    {user.is_active ? "Active" : "Disabled"}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="min-h-9"
                    disabled={busyUserId === user.id}
                    onClick={() => void toggleActive(user)}
                  >
                    {busyUserId === user.id ? (
                      <Loader2 className="size-4 animate-spin" aria-hidden />
                    ) : user.is_active ? (
                      "Disable"
                    ) : (
                      "Enable"
                    )}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </>
  );
}
