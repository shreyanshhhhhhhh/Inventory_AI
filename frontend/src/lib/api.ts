export type HealthResponse = {
  status: string;
};

function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (!configured) {
    throw new Error("NEXT_PUBLIC_API_URL is not set");
  }
  return configured.replace(/\/$/, "");
}

function isHealthResponse(value: unknown): value is HealthResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    typeof value.status === "string"
  );
}

export const api = {
  async health(): Promise<HealthResponse> {
    const response = await fetch(`${apiBaseUrl()}/health`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(`Health check failed (${response.status})`);
    }
    const body: unknown = await response.json();
    if (!isHealthResponse(body)) {
      throw new Error("Health check returned an unexpected payload");
    }
    return body;
  },
};
