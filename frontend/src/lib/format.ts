function buildCurrencyFormatter(currencyCode: string): Intl.NumberFormat {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  } catch {
    return buildCurrencyFormatter("USD");
  }
}

let displayCurrency = "USD";
let currencyFormatter = buildCurrencyFormatter(displayCurrency);

/** Called by the auth provider once the business is loaded; amounts are always in the business currency. */
export function setDisplayCurrency(currencyCode: string): void {
  const code = currencyCode.toUpperCase();
  if (code === displayCurrency) return;
  displayCurrency = code;
  currencyFormatter = buildCurrencyFormatter(code);
}

export function formatCurrency(value: number): string {
  return currencyFormatter.format(value);
}

export function formatQuantity(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
