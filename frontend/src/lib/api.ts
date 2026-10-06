import { toast } from "sonner";

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "@/lib/auth-storage";
import type {
  ApiCategory,
  ApiDashboardActivityItem,
  ApiAccountsBySupplierRow,
  ApiAccountsSummary,
  ApiAutonomyRules,
  ApiDashboardSummary,
  ApiSettingsLocation,
  ApiTeamUser,
  ApiDemoSeedResult,
  ApiMovementsOverTime,
  ApiForecastDetail,
  ApiForecastList,
  ApiTopSellers,
  ApiNeedsAttentionItem,
  ApiImportResult,
  ApiProduct,
  ApiProductList,
  ApiProductWrite,
  ApiMovementList,
  ApiMovementWrite,
  ApiMovement,
  ApiLocation,
  ApiPurchaseOrder,
  ApiPurchaseOrderList,
  ApiPurchaseOrderTransition,
  ApiPurchaseOrderWrite,
  ApiStockList,
  ApiSupplier,
  ApiSupplierWrite,
  ApiTokenResponse,
} from "@/lib/api-types";

export type HealthResponse = {
  status: string;
};

export type ApiErrorBody = {
  detail: string;
  code: string;
};

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export class ImportCsvError extends Error {
  result: ApiImportResult;

  constructor(result: ApiImportResult) {
    super(
      result.error_count === 1
        ? "1 row could not be imported."
        : `${result.error_count} rows could not be imported.`,
    );
    this.result = result;
  }
}

const API_V1 = "/api/v1";

export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (!configured) {
    throw new Error("NEXT_PUBLIC_API_URL is not set");
  }
  return configured.replace(/\/$/, "");
}

export function sampleCsvUrl(path: string): string {
  return `${apiBaseUrl()}${path}`;
}

function isImportResult(value: unknown): value is ApiImportResult {
  return (
    typeof value === "object" &&
    value !== null &&
    "imported_count" in value &&
    "errors" in value &&
    Array.isArray(value.errors)
  );
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      const code =
        "code" in body && typeof body.code === "string"
          ? body.code
          : "error";
      return new ApiError(body.detail, response.status, code);
    }
  } catch {
    // fall through
  }
  return new ApiError(`Request failed (${response.status})`, response.status, "error");
}

export function showApiErrorToast(error: unknown): void {
  if (error instanceof ApiError) {
    toast.error(error.message);
    return;
  }
  if (error instanceof Error) {
    toast.error(error.message);
    return;
  }
  toast.error("Something went wrong.");
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  const response = await fetch(`${apiBaseUrl()}${API_V1}/auth/refresh`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    clearTokens();
    return false;
  }
  const body = (await response.json()) as ApiTokenResponse;
  setTokens(body.access_token, body.refresh_token);
  return true;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers,
  });

  if (response.status === 401 && token) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      headers.set("Authorization", `Bearer ${getAccessToken()}`);
      response = await fetch(`${apiBaseUrl()}${path}`, {
        ...init,
        headers,
      });
    }
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function uploadCsvFile(
  path: string,
  file: File,
  options?: { skipErrors?: boolean },
): Promise<ApiImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  const query = options?.skipErrors ? "?skip_errors=true" : "";

  const headers = new Headers();
  headers.set("Accept", "application/json");
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response = await fetch(`${apiBaseUrl()}${path}${query}`, {
    method: "POST",
    body: formData,
    headers,
  });

  if (response.status === 401 && token) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      headers.set("Authorization", `Bearer ${getAccessToken()}`);
      response = await fetch(`${apiBaseUrl()}${path}${query}`, {
        method: "POST",
        body: formData,
        headers,
      });
    }
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(`Request failed (${response.status})`, response.status, "error");
  }

  if (isImportResult(body)) {
    if (!response.ok || (!body.success && !options?.skipErrors)) {
      throw new ImportCsvError(body);
    }
    return body;
  }

  if (!response.ok) {
    throw await parseError(
      new Response(JSON.stringify(body), {
        status: response.status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }

  throw new ApiError("Import returned an unexpected payload", response.status, "error");
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

  auth: {
    signup(body: {
      email: string;
      password: string;
      full_name: string;
      business_name: string;
    }): Promise<ApiTokenResponse> {
      return request<ApiTokenResponse>(`${API_V1}/auth/signup`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    login(body: {
      email: string;
      password: string;
    }): Promise<ApiTokenResponse> {
      return request<ApiTokenResponse>(`${API_V1}/auth/login`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    refresh(refreshToken: string): Promise<ApiTokenResponse> {
      return request<ApiTokenResponse>(`${API_V1}/auth/refresh`, {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    },
    logout(refreshToken: string): Promise<void> {
      return request<void>(`${API_V1}/auth/logout`, {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    },
    me(): Promise<{
      id: string;
      email: string;
      full_name: string;
      role: string;
      business_id: string;
    }> {
      return request(`${API_V1}/auth/me`);
    },
  },

  business: {
    current(): Promise<{
      id: string;
      name: string;
      currency_code: string;
    }> {
      return request(`${API_V1}/businesses/current`);
    },
  },

  categories: {
    list(): Promise<ApiCategory[]> {
      return request<ApiCategory[]>(`${API_V1}/categories`);
    },
    create(name: string): Promise<ApiCategory> {
      return request<ApiCategory>(`${API_V1}/categories`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
    },
    update(id: string, name: string): Promise<ApiCategory> {
      return request<ApiCategory>(`${API_V1}/categories/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
    },
    delete(id: string): Promise<void> {
      return request<void>(`${API_V1}/categories/${id}`, { method: "DELETE" });
    },
  },

  suppliers: {
    list(): Promise<ApiSupplier[]> {
      return request<ApiSupplier[]>(`${API_V1}/suppliers`);
    },
    create(body: ApiSupplierWrite): Promise<ApiSupplier> {
      return request<ApiSupplier>(`${API_V1}/suppliers`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    update(id: string, body: ApiSupplierWrite): Promise<ApiSupplier> {
      return request<ApiSupplier>(`${API_V1}/suppliers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    archive(id: string): Promise<ApiSupplier> {
      return request<ApiSupplier>(`${API_V1}/suppliers/${id}`, {
        method: "DELETE",
      });
    },
  },

  products: {
    list(params: {
      search?: string;
      category_id?: string;
      page?: number;
      page_size?: number;
    }): Promise<ApiProductList> {
      const query = new URLSearchParams();
      if (params.search) query.set("search", params.search);
      if (params.category_id) query.set("category_id", params.category_id);
      if (params.page) query.set("page", String(params.page));
      if (params.page_size) query.set("page_size", String(params.page_size));
      const suffix = query.toString() ? `?${query.toString()}` : "";
      return request<ApiProductList>(`${API_V1}/products${suffix}`);
    },
    create(body: ApiProductWrite): Promise<ApiProduct> {
      return request<ApiProduct>(`${API_V1}/products`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    update(id: string, body: ApiProductWrite): Promise<ApiProduct> {
      return request<ApiProduct>(`${API_V1}/products/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    archive(id: string): Promise<ApiProduct> {
      return request<ApiProduct>(`${API_V1}/products/${id}`, {
        method: "DELETE",
      });
    },
    importCsv(file: File, options?: { skipErrors?: boolean }): Promise<ApiImportResult> {
      return uploadCsvFile(`${API_V1}/products/import-csv`, file, options);
    },
    sampleCsvHref: `${API_V1}/products/sample-csv`,
  },

  sales: {
    importCsv(file: File, options?: { skipErrors?: boolean }): Promise<ApiImportResult> {
      return uploadCsvFile(`${API_V1}/sales/import-csv`, file, options);
    },
    sampleCsvHref: `${API_V1}/sales/sample-csv`,
  },

  onboarding: {
    loadDemoData(): Promise<ApiDemoSeedResult> {
      return request<ApiDemoSeedResult>(`${API_V1}/onboarding/load-demo-data`, {
        method: "POST",
      });
    },
  },

  inventory: {
    locations(): Promise<ApiLocation[]> {
      return request<ApiLocation[]>(`${API_V1}/inventory/locations`);
    },
    stock(params: {
      search?: string;
      location_id?: string;
      low_only?: boolean;
      page?: number;
      page_size?: number;
    }): Promise<ApiStockList> {
      const query = new URLSearchParams();
      if (params.search) query.set("search", params.search);
      if (params.location_id) query.set("location_id", params.location_id);
      if (params.low_only) query.set("low_only", "true");
      if (params.page) query.set("page", String(params.page));
      if (params.page_size) query.set("page_size", String(params.page_size));
      const suffix = query.toString() ? `?${query.toString()}` : "";
      return request<ApiStockList>(`${API_V1}/inventory/stock${suffix}`);
    },
    movements(params: {
      type?: string;
      product_id?: string;
      date_from?: string;
      date_to?: string;
      page?: number;
      page_size?: number;
    }): Promise<ApiMovementList> {
      const query = new URLSearchParams();
      if (params.type) query.set("type", params.type);
      if (params.product_id) query.set("product_id", params.product_id);
      if (params.date_from) query.set("date_from", params.date_from);
      if (params.date_to) query.set("date_to", params.date_to);
      if (params.page) query.set("page", String(params.page));
      if (params.page_size) query.set("page_size", String(params.page_size));
      const suffix = query.toString() ? `?${query.toString()}` : "";
      return request<ApiMovementList>(`${API_V1}/inventory/movements${suffix}`);
    },
    recordMovement(body: ApiMovementWrite): Promise<ApiMovement> {
      return request<ApiMovement>(`${API_V1}/inventory/movements`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
  },

  purchaseOrders: {
    list(params: {
      status?: string;
      supplier_id?: string;
      page?: number;
      page_size?: number;
    }): Promise<ApiPurchaseOrderList> {
      const query = new URLSearchParams();
      if (params.status) query.set("status", params.status);
      if (params.supplier_id) query.set("supplier_id", params.supplier_id);
      if (params.page) query.set("page", String(params.page));
      if (params.page_size) query.set("page_size", String(params.page_size));
      const suffix = query.toString() ? `?${query.toString()}` : "";
      return request<ApiPurchaseOrderList>(`${API_V1}/purchase-orders${suffix}`);
    },
    get(id: string): Promise<ApiPurchaseOrder> {
      return request<ApiPurchaseOrder>(`${API_V1}/purchase-orders/${id}`);
    },
    create(body: ApiPurchaseOrderWrite): Promise<ApiPurchaseOrder> {
      return request<ApiPurchaseOrder>(`${API_V1}/purchase-orders`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    transition(id: string, body: ApiPurchaseOrderTransition): Promise<ApiPurchaseOrder> {
      return request<ApiPurchaseOrder>(`${API_V1}/purchase-orders/${id}/transition`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
  },

  dashboard: {
    summary(): Promise<ApiDashboardSummary> {
      return request<ApiDashboardSummary>(`${API_V1}/dashboard/summary`);
    },
    needsAttention(): Promise<{ items: ApiNeedsAttentionItem[] }> {
      return request<{ items: ApiNeedsAttentionItem[] }>(
        `${API_V1}/dashboard/needs-attention`,
      );
    },
    activity(): Promise<{ items: ApiDashboardActivityItem[] }> {
      return request<{ items: ApiDashboardActivityItem[] }>(
        `${API_V1}/dashboard/activity`,
      );
    },
  },

  insights: {
    movementsOverTime(days = 30): Promise<ApiMovementsOverTime> {
      return request<ApiMovementsOverTime>(
        `${API_V1}/insights/movements-over-time?days=${days}`,
      );
    },
    topSellers(days = 30, limit = 5): Promise<ApiTopSellers> {
      return request<ApiTopSellers>(
        `${API_V1}/insights/top-sellers?days=${days}&limit=${limit}`,
      );
    },
    forecasts(historyDays = 56, horizonDays = 14): Promise<ApiForecastList> {
      return request<ApiForecastList>(
        `${API_V1}/insights/forecasts?history_days=${historyDays}&horizon_days=${horizonDays}`,
      );
    },
    forecast(
      productId: string,
      historyDays = 56,
      horizonDays = 14,
    ): Promise<ApiForecastDetail> {
      return request<ApiForecastDetail>(
        `${API_V1}/insights/forecasts/${productId}?history_days=${historyDays}&horizon_days=${horizonDays}`,
      );
    },
  },

  accounts: {
    summary(): Promise<ApiAccountsSummary> {
      return request<ApiAccountsSummary>(`${API_V1}/accounts/summary`);
    },
    bySupplier(): Promise<{ items: ApiAccountsBySupplierRow[] }> {
      return request<{ items: ApiAccountsBySupplierRow[] }>(
        `${API_V1}/accounts/by-supplier`,
      );
    },
  },

  settings: {
    business: {
      update(body: {
        name?: string;
        currency_code?: string;
      }): Promise<{ id: string; name: string; currency_code: string }> {
        return request(`${API_V1}/settings/business`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      },
    },
    locations: {
      list(): Promise<ApiSettingsLocation[]> {
        return request<ApiSettingsLocation[]>(`${API_V1}/settings/locations`);
      },
      create(body: {
        name: string;
        address?: string | null;
        is_default?: boolean;
      }): Promise<ApiSettingsLocation> {
        return request<ApiSettingsLocation>(`${API_V1}/settings/locations`, {
          method: "POST",
          body: JSON.stringify(body),
        });
      },
      update(
        id: string,
        body: {
          name?: string;
          address?: string | null;
          is_default?: boolean;
        },
      ): Promise<ApiSettingsLocation> {
        return request<ApiSettingsLocation>(`${API_V1}/settings/locations/${id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      },
      archive(id: string): Promise<void> {
        return request<void>(`${API_V1}/settings/locations/${id}`, {
          method: "DELETE",
        });
      },
    },
    users: {
      list(): Promise<ApiTeamUser[]> {
        return request<ApiTeamUser[]>(`${API_V1}/settings/users`);
      },
      create(body: {
        full_name: string;
        email: string;
        temporary_password: string;
      }): Promise<ApiTeamUser> {
        return request<ApiTeamUser>(`${API_V1}/settings/users`, {
          method: "POST",
          body: JSON.stringify(body),
        });
      },
      updateRole(
        userId: string,
        body: { role: "owner" | "staff" },
      ): Promise<ApiTeamUser> {
        return request<ApiTeamUser>(`${API_V1}/settings/users/${userId}/role`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      },
    },
    autonomyRules: {
      get(): Promise<ApiAutonomyRules> {
        return request<ApiAutonomyRules>(`${API_V1}/settings/autonomy-rules`);
      },
      update(body: {
        auto_approve_below_amount: string | null;
        exception_scan_enabled?: boolean;
        exception_scan_hour_utc?: number;
      }): Promise<ApiAutonomyRules> {
        return request<ApiAutonomyRules>(`${API_V1}/settings/autonomy-rules`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      },
    },
  },
};
