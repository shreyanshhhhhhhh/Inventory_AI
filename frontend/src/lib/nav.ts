import {
  ChartLine,
  House,
  Inbox,
  Package,
  Settings,
  Truck,
  Wallet,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href:
    | "/"
    | "/catalog"
    | "/inventory"
    | "/orders"
    | "/inbox"
    | "/insights"
    | "/accounts"
    | "/settings";
  label: string;
  icon: LucideIcon;
};

export const navItems: NavItem[] = [
  { href: "/", label: "Home", icon: House },
  { href: "/catalog", label: "Catalog", icon: Package },
  { href: "/inventory", label: "Inventory", icon: Warehouse },
  { href: "/orders", label: "Orders & Suppliers", icon: Truck },
  { href: "/inbox", label: "Agent Inbox", icon: Inbox },
  { href: "/insights", label: "Insights", icon: ChartLine },
  { href: "/accounts", label: "Accounts", icon: Wallet },
  { href: "/settings", label: "Settings", icon: Settings },
];
