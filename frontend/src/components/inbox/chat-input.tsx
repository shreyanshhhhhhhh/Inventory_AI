"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Send, Square } from "lucide-react";

import { CommandMenu } from "@/components/inbox/command-menu";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { filterSlashCommands, SLASH_COMMANDS } from "@/lib/chat/commands";

export function ChatInput({
  disabled,
  running,
  onSend,
  onStop,
}: {
  disabled: boolean;
  running: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const [value, setValue] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const node = areaRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 160)}px`;
  }, [value]);

  function send() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
    setMenuOpen(false);
  }

  const slashQuery = value.startsWith("/") ? value.split(/\s/)[0] ?? value : "";
  const menuItems = menuOpen && value.startsWith("/") ? filterSlashCommands(slashQuery) : [];

  function pickCommand(command: string) {
    setValue(`${command} `);
    setMenuOpen(false);
    setActiveIndex(0);
    areaRef.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Escape") {
      setMenuOpen(false);
      return;
    }
    if (menuItems.length > 0) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((index) => (index + 1) % menuItems.length);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((index) => (index - 1 + menuItems.length) % menuItems.length);
        return;
      }
      if (event.key === "Tab") {
        event.preventDefault();
        const item = menuItems[activeIndex] ?? menuItems[0];
        if (item) pickCommand(item.command);
        return;
      }
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (menuItems.length > 0 && value.trim() !== (menuItems[activeIndex]?.command ?? "")) {
        const item = menuItems[activeIndex] ?? menuItems[0];
        if (item) pickCommand(item.command);
        return;
      }
      if (!disabled) send();
    }
  }

  return (
    <div className="space-y-2">
      {menuOpen && value.startsWith("/") ? (
        <CommandMenu query={slashQuery} activeIndex={activeIndex} onPick={pickCommand} />
      ) : null}
      <div className="flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-sm dark:bg-card/80">
        <label className="sr-only" htmlFor="agent-chat-input">
          Message the inventory assistant
        </label>
        <Textarea
          id="agent-chat-input"
          ref={areaRef}
          rows={1}
          value={value}
          placeholder="Ask about stock, forecasts, or type / for commands"
          className="max-h-40 min-h-9"
          onChange={(event) => {
            const next = event.target.value;
            setValue(next);
            setMenuOpen(next.startsWith("/"));
            setActiveIndex(0);
          }}
          onKeyDown={onKeyDown}
          aria-expanded={menuOpen}
          aria-controls="slash-command-menu"
          aria-autocomplete="list"
        />
        {running ? (
          <Button type="button" variant="destructive" size="icon" aria-label="Stop run" onClick={onStop}>
            <Square />
          </Button>
        ) : (
          <Button type="button" size="icon" aria-label="Send message" disabled={disabled || !value.trim()} onClick={send}>
            <Send />
          </Button>
        )}
      </div>
    </div>
  );
}

export function SuggestedChips({ onPick }: { onPick: (command: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {SLASH_COMMANDS.slice(0, 5).map((item) => (
        <button
          key={item.command}
          type="button"
          className="rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          onClick={() => onPick(item.command)}
        >
          {item.command}
        </button>
      ))}
    </div>
  );
}
