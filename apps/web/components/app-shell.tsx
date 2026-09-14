"use client";

/**
 * Responsive application shell.
 *
 * Two navigation models, not one that stretches:
 *   - desktop (lg+): a fixed left sidebar, which is where a data-dense
 *     compliance tool wants its navigation - out of the way and always visible
 *   - phone/tablet (< lg): a sticky header plus a bottom tab bar, which keeps
 *     every destination within thumb reach instead of hidden behind a hamburger
 *
 * Content is padded at the bottom on small screens so the fixed tab bar never
 * covers the last row of a list.
 */

import {
  CalendarClock,
  FileText,
  ListChecks,
  LayoutDashboard,
  Map,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { UserStatus } from "@/components/user-status";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  /** Shorter label for the cramped bottom bar. */
  shortLabel: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { href: "/", label: "Overview", shortLabel: "Home", icon: LayoutDashboard },
  { href: "/leases", label: "Mining sites", shortLabel: "Sites", icon: FileText },
  { href: "/map", label: "Site map", shortLabel: "Map", icon: Map },
  { href: "/calendar", label: "Deadlines", shortLabel: "Due dates", icon: CalendarClock },
  { href: "/actions", label: "Needs attention", shortLabel: "Actions", icon: ListChecks },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function Brand() {
  return (
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
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold leading-tight">
          MineGuard
        </span>
        <span className="block truncate text-xs text-muted-foreground leading-tight">
          Mining compliance made clear
        </span>
      </span>
    </div>
  );
}

function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-border bg-sidebar lg:flex">
      <div className="flex h-16 shrink-0 items-center border-b border-sidebar-border px-5">
        <Brand />
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Main">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground",
              )}
            >
              <item.icon className="size-4.5 shrink-0" aria-hidden />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="shrink-0 border-t border-sidebar-border p-4">
        <UserStatus />
        <p className="text-xs leading-relaxed text-sidebar-foreground/55">
          Reference data shown is illustrative. Verify rates and deadlines against
          the current statute before relying on them.
        </p>
      </div>
    </aside>
  );
}

function MobileHeader() {
  const pathname = usePathname();
  const current = NAV.find((item) => isActive(pathname, item.href));

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80 lg:hidden">
      <Brand />
      {current && current.href !== "/" && (
        <span className="ml-auto shrink-0 text-xs font-medium text-muted-foreground">
          {current.shortLabel}
        </span>
      )}
      <UserStatus compact />
    </header>
  );
}

function TabBar() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85 lg:hidden"
      // Keeps the bar clear of the iOS home indicator.
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="grid grid-cols-4">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  // min-h-14 keeps each target comfortably above the 44px
                  // minimum for a thumb, which a desktop-sized 32px row is not.
                  "flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 py-2 text-[0.6875rem] font-medium transition-colors",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              >
                <item.icon
                  className={cn("size-5 shrink-0", active && "stroke-[2.4]")}
                  aria-hidden
                />
                <span className="truncate">{item.shortLabel}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-background">
      <Sidebar />
      <MobileHeader />

      <div className="lg:pl-64">
        <main className="mx-auto w-full max-w-[1600px] px-4 pt-5 pb-28 sm:px-6 lg:px-8 lg:pt-8 lg:pb-12">
          {children}
        </main>
      </div>

      <TabBar />
    </div>
  );
}
