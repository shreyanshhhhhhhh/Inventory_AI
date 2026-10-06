"use client";

import { filterSlashCommands } from "@/lib/chat/commands";

export function CommandMenu({
  query,
  activeIndex,
  onPick,
}: {
  query: string;
  activeIndex: number;
  onPick: (command: string) => void;
}) {
  const items = filterSlashCommands(query);
  if (items.length === 0) {
    return (
      <p className="rounded-lg border bg-popover px-3 py-2 text-xs text-muted-foreground">
        No matching commands.
      </p>
    );
  }
  return (
    <ul
      id="slash-command-menu"
      className="max-h-64 overflow-auto rounded-lg border bg-popover p-1 shadow-md"
      role="listbox"
      aria-label="Slash commands"
    >
      {items.map((item, index) => (
        <li key={item.command} role="option" aria-selected={index === activeIndex}>
          <button
            type="button"
            className={
              index === activeIndex
                ? "flex w-full flex-col rounded-md bg-muted px-2 py-1.5 text-left"
                : "flex w-full flex-col rounded-md px-2 py-1.5 text-left hover:bg-muted"
            }
            onMouseDown={(event) => {
              event.preventDefault();
              onPick(item.command);
            }}
          >
            <span className="text-sm font-medium">{item.command}</span>
            <span className="text-xs text-muted-foreground">{item.description}</span>
            <span className="text-[11px] text-muted-foreground">{item.hint}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
