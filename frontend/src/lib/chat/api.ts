import { apiBaseUrl } from "@/lib/api";
import { getAccessToken } from "@/lib/auth-storage";
import { appendSseChunk } from "@/lib/chat/sse";
import type { ChatRunDetail, ChatRunResponse, ChatSseEvent } from "@/lib/chat/types";

const API_V1 = "/api/v1";

async function chatRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${apiBaseUrl()}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body: unknown = await response.json();
      if (
        typeof body === "object" &&
        body !== null &&
        "detail" in body &&
        typeof body.detail === "string"
      ) {
        detail = body.detail;
      }
    } catch {
      // keep default
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const chatApi = {
  startRun(message: string): Promise<ChatRunResponse> {
    return chatRequest<ChatRunResponse>(`${API_V1}/chat/runs`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
  },
  getRun(runId: string): Promise<ChatRunDetail> {
    return chatRequest<ChatRunDetail>(`${API_V1}/chat/runs/${runId}`);
  },
  cancel(runId: string): Promise<ChatRunResponse> {
    return chatRequest<ChatRunResponse>(`${API_V1}/chat/runs/${runId}/cancel`, {
      method: "POST",
    });
  },
  resume(
    runId: string,
    body: { action: "run" | "edit" | "cancel"; plan?: Record<string, unknown> },
  ): Promise<ChatRunResponse> {
    return chatRequest<ChatRunResponse>(`${API_V1}/chat/runs/${runId}/resume`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};

export async function streamChatEvents(
  runId: string,
  signal: AbortSignal,
  onEvent: (event: ChatSseEvent) => void,
  onDisconnect: () => void,
): Promise<"closed" | "aborted" | "dropped"> {
  const token = getAccessToken();
  const headers = new Headers({ Accept: "text/event-stream" });
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${API_V1}/chat/runs/${runId}/events`, {
      headers,
      signal,
    });
  } catch {
    if (signal.aborted) return "aborted";
    onDisconnect();
    return "dropped";
  }
  if (!response.ok || !response.body) {
    onDisconnect();
    return "dropped";
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return "closed";
      const chunk = decoder.decode(value, { stream: true });
      const parsed = appendSseChunk(buffer, chunk);
      buffer = parsed.buffer;
      for (const event of parsed.events) onEvent(event);
    }
  } catch {
    if (signal.aborted) return "aborted";
    onDisconnect();
    return "dropped";
  }
}
