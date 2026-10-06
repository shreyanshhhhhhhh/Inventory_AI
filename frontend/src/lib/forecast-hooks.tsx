"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type {
  ApiForecastDetail,
  ApiForecastSummary,
  ForecastMethod,
} from "@/lib/api-types";
import { useAuth } from "@/lib/auth-context";

export type ForecastSummary = {
  productId: string;
  sku: string;
  name: string;
  historyUnits: number;
  forecastUnits: number;
  dailyAverage: number;
  method: ForecastMethod;
};

export type ForecastPoint = {
  date: string;
  units: number;
};

export type ForecastDetail = ForecastSummary & {
  history: ForecastPoint[];
  forecast: ForecastPoint[];
};

function mapSummary(item: ApiForecastSummary): ForecastSummary {
  return {
    productId: item.product_id,
    sku: item.sku,
    name: item.product_name,
    historyUnits: Number(item.history_units),
    forecastUnits: Number(item.forecast_units),
    dailyAverage: Number(item.daily_average),
    method: item.method,
  };
}

function mapDetail(item: ApiForecastDetail): ForecastDetail {
  return {
    ...mapSummary(item),
    history: item.history.map((point) => ({
      date: point.date,
      units: Number(point.units),
    })),
    forecast: item.forecast.map((point) => ({
      date: point.date,
      units: Number(point.units),
    })),
  };
}

export function useDemandForecast() {
  const { isAuthenticated } = useAuth();
  const [items, setItems] = useState<ForecastSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ForecastDetail | null>(null);
  const [historyDays, setHistoryDays] = useState(56);
  const [horizonDays, setHorizonDays] = useState(14);
  const [isLoading, setIsLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      setItems([]);
      setSelectedId(null);
      setDetail(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);
    api.insights
      .forecasts()
      .then((payload) => {
        if (cancelled) return;
        setHistoryDays(payload.history_days);
        setHorizonDays(payload.horizon_days);
        setItems(payload.items.map(mapSummary));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Could not load forecasts.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  useEffect(() => {
    if (items.length === 0) {
      setSelectedId(null);
      return;
    }
    if (selectedId && items.some((item) => item.productId === selectedId)) {
      return;
    }
    const preferred = items.find((item) => item.method !== "no_sales") ?? items[0];
    setSelectedId(preferred.productId);
  }, [items, selectedId]);

  useEffect(() => {
    if (!isAuthenticated || !selectedId) {
      setDetail(null);
      setDetailLoading(false);
      setDetailError(null);
      return;
    }

    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    api.insights
      .forecast(selectedId, historyDays, horizonDays)
      .then((payload) => {
        if (!cancelled) setDetail(mapDetail(payload));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setDetail(null);
        setDetailError(err instanceof Error ? err.message : "Could not load this forecast.");
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [historyDays, horizonDays, isAuthenticated, selectedId]);

  return {
    items,
    selectedId,
    setSelectedId,
    detail,
    historyDays,
    horizonDays,
    isLoading,
    detailLoading,
    error,
    detailError,
  };
}
