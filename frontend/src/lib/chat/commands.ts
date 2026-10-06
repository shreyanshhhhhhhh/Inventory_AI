export type SlashCommand = {
  command: string;
  label: string;
  description: string;
  hint: string;
};

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    command: "/stock",
    label: "Stock",
    description: "Show on-hand by SKU and location",
    hint: "/stock [sku or name]",
  },
  {
    command: "/forecast",
    label: "Forecast",
    description: "14-day demand forecast from sales",
    hint: "/forecast [sku]",
  },
  {
    command: "/scan",
    label: "Scan",
    description: "Scan for stock and order problems",
    hint: "/scan",
  },
  {
    command: "/reorder",
    label: "Reorder",
    description: "Recommend reorder quantities",
    hint: "/reorder",
  },
  {
    command: "/draft-po",
    label: "Draft PO",
    description: "Draft a purchase-order suggestion",
    hint: "/draft-po [supplier]",
  },
  {
    command: "/email",
    label: "Email",
    description: "Draft supplier emails (does not send)",
    hint: "/email [supplier]",
  },
  {
    command: "/explain",
    label: "Explain",
    description: "Explain the latest inventory figures",
    hint: "/explain",
  },
  {
    command: "/quality",
    label: "Data quality",
    description: "Check catalog and ledger quality",
    hint: "/quality",
  },
];

export function intentToCommand(intent: string): string {
  if (intent.startsWith("/")) return intent;
  const map: Record<string, string> = {
    get_stock: "/stock",
    forecast: "/forecast",
    scan_exceptions: "/scan",
    reorder: "/reorder",
    draft_po: "/draft-po",
    draft_email: "/email",
    explain: "/explain",
    data_quality: "/quality",
  };
  return map[intent] ?? `/${intent.replaceAll("_", "-")}`;
}

export function filterSlashCommands(query: string): SlashCommand[] {
  const needle = query.trim().replace(/^\//, "").toLowerCase();
  if (!needle) return SLASH_COMMANDS;
  return SLASH_COMMANDS.filter(
    (item) =>
      item.command.slice(1).startsWith(needle) ||
      item.label.toLowerCase().includes(needle) ||
      item.description.toLowerCase().includes(needle),
  );
}
