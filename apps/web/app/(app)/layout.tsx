import { AppShell } from "@/components/app-shell";

/**
 * Layout for the signed-in app: dashboard, register, map, calendar, actions.
 * The `(app)` route group keeps this wrapper off the public landing and login
 * pages, which live in `(marketing)` and render their own full-height flow.
 */
export default function AppGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
