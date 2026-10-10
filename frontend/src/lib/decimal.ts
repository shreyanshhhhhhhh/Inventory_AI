/** The API stores money and quantity as Numeric(…, 4); send at most 4 places, never exponent notation. */
export const DECIMAL_PLACES = 4;

export function toDecimalString(value: number, places: number = DECIMAL_PLACES): string {
  if (!Number.isFinite(value)) return "0";
  const fixed = value.toFixed(places);
  const trimmed = fixed.includes(".") ? fixed.replace(/\.?0+$/, "") : fixed;
  return trimmed === "-0" ? "0" : trimmed;
}

export function parseDecimal(value: string | null | undefined): number {
  if (value === null || value === undefined || value === "") return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
