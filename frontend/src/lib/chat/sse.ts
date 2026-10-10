import { CHAT_EVENT_TYPES, type ChatEventType, type ChatSseEvent } from "@/lib/chat/types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isEventType(value: string): value is ChatEventType {
  return (CHAT_EVENT_TYPES as readonly string[]).includes(value);
}

export function eventKey(event: ChatSseEvent): string {
  const step = typeof event.payload.step_id === "string" ? event.payload.step_id : "";
  const text = typeof event.payload.text === "string" ? event.payload.text : "";
  return `${event.type}:${event.ts}:${step}:${text}`;
}

export function normalizeChatEvent(
  type: string,
  data: Record<string, unknown>,
): ChatSseEvent | null {
  if (!isEventType(type)) return null;
  const runId = data.run_id;
  const ts = data.ts;
  if (typeof runId !== "string" || typeof ts !== "string") return null;
  const payload: Record<string, unknown> = { ...data };
  delete payload.run_id;
  delete payload.ts;
  if (isRecord(data.payload)) {
    return {
      type,
      run_id: runId,
      ts,
      payload: { ...data.payload },
    };
  }
  return { type, run_id: runId, ts, payload };
}

export function storedEventToSse(raw: unknown): ChatSseEvent | null {
  if (!isRecord(raw)) return null;
  const type = typeof raw.type === "string" ? raw.type : "";
  return normalizeChatEvent(type, raw);
}

export function parseSseBlock(block: string): ChatSseEvent | null {
  let eventType = "";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!eventType || dataLines.length === 0) return null;
  try {
    const parsed: unknown = JSON.parse(dataLines.join("\n"));
    if (!isRecord(parsed)) return null;
    return normalizeChatEvent(eventType, parsed);
  } catch {
    return null;
  }
}

export function appendSseChunk(
  buffer: string,
  chunk: string,
): { buffer: string; events: ChatSseEvent[] } {
  const combined = `${buffer}${chunk}`.replace(/\r\n/g, "\n");
  const parts = combined.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: ChatSseEvent[] = [];
  for (const block of parts) {
    const event = parseSseBlock(block);
    if (event) events.push(event);
  }
  return { buffer: rest, events };
}
