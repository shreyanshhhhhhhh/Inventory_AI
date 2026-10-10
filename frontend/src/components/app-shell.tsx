"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  ChevronRight,
  LogOut,
  Menu,
  User,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth-context";
import { getSectionLabel, isNavActive } from "@/lib/breadcrumbs";
import { navItems } from "@/lib/nav";
import { cn } from "@/lib/utils";

function Brand() {
  return (
    <div className="px-3 py-2">
      <p className="text-sm font-semibold tracking-tight text-sidebar-foreground">
        Inventory
      </p>
      <p className="text-xs text-sidebar-foreground/65">Shop stock</p>
    </div>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { isOwner } = useAuth();

  return (
    <nav className="flex flex-col gap-1" aria-label="Primary">
      {navItems.filter((item) => isOwner || !item.ownerOnly).map((item) => {
        const Icon = item.icon;
        const active = isNavActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              active && "bg-sidebar-accent text-sidebar-accent-foreground",
            )}
          >
            <Icon className="size-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarFooter({ onNavigate }: { onNavigate?: () => void }) {
  const { user, business, logout } = useAuth();
  const router = useRouter();

  return (
    <div className="mt-auto border-t border-sidebar-border p-3">
      <p className="truncate px-3 text-xs font-medium text-sidebar-foreground">
        {business?.name ?? "Your business"}
      </p>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              className="mt-2 w-full justify-start gap-2 px-3 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            />
          }
        >
          <User className="size-4" />
          <span className="truncate text-sm">
            {user?.full_name ?? "Account"}
          </span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-48">
          <DropdownMenuItem
            onClick={() => {
              onNavigate?.();
              router.push("/accounts");
            }}
          >
            <User />
            Profile
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => void logout()}>
            <LogOut />
            Logout
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function MobileSidebarContent({ onNavigate }: { onNavigate: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <SheetHeader>
        <SheetTitle className="text-sidebar-foreground">Inventory</SheetTitle>
      </SheetHeader>
      <div className="px-2 py-2">
        <NavLinks onNavigate={onNavigate} />
      </div>
      <SidebarFooter onNavigate={onNavigate} />
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const sectionLabel = getSectionLabel(pathname);

  return (
    <div className="flex min-h-full flex-1">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
        <div className="p-3">
          <Brand />
        </div>
        <div className="flex-1 px-2 pb-4">
          <NavLinks />
        </div>
        <SidebarFooter />
      </aside>

      <div className="app-canvas flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-sidebar-border bg-sidebar text-sidebar-foreground">
          <div className="flex items-center gap-3 px-4 py-3 md:px-6">
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground md:hidden"
                    aria-label="Open navigation"
                  />
                }
              >
                <Menu />
              </SheetTrigger>
              <SheetContent
                side="left"
                className="w-72 border-sidebar-border bg-sidebar p-0 text-sidebar-foreground [&_[data-slot=sheet-close]]:text-sidebar-foreground [&_[data-slot=sheet-close]]:hover:bg-sidebar-accent"
              >
                <MobileSidebarContent onNavigate={() => setOpen(false)} />
              </SheetContent>
            </Sheet>

            <nav
              aria-label="Breadcrumb"
              className="flex min-w-0 items-center gap-1.5 text-sm text-sidebar-foreground/70"
            >
              <span className="hidden font-medium text-sidebar-foreground sm:inline">
                Inventory
              </span>
              <ChevronRight className="hidden size-4 text-sidebar-foreground/50 sm:inline" />
              <span className="truncate font-medium text-sidebar-foreground">
                {sectionLabel}
              </span>
            </nav>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 md:px-6 md:py-8">{children}</main>
      </div>
    </div>
  );
}
