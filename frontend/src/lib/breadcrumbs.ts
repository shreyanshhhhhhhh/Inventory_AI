import type { NavItem } from "@/lib/nav";

export function getSectionLabel(pathname: string): string {
  if (pathname === "/") return "Home";
  const match = [
    { href: "/catalog", label: "Catalog" },
    { href: "/inventory", label: "Inventory" },
    { href: "/orders", label: "Orders & Suppliers" },
    { href: "/inbox", label: "Agent Inbox" },
    { href: "/insights", label: "Insights" },
    { href: "/accounts", label: "Accounts" },
    { href: "/settings", label: "Settings" },
  ].find(
    (item) =>
      pathname === item.href || pathname.startsWith(`${item.href}/`),
  );
  return match?.label ?? "Inventory";
}

export function isNavActive(pathname: string, href: NavItem["href"]): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
