"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

type Status = "loading" | "ok" | "error";

export function ApiStatus() {
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((body) => {
        if (!cancelled) {
          setStatus(body.status === "ok" ? "ok" : "error");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const label =
    status === "loading"
      ? "Checking the API…"
      : status === "ok"
        ? "API is reachable"
        : "API is not reachable";

  return (
    <p className="text-sm text-muted-foreground" role="status">
      {label}
    </p>
  );
}
