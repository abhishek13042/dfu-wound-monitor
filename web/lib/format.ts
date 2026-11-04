import type { Measurement } from "@/lib/api";

// A missing date reads as a dash rather than an invented one.
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(iso));
}

// A fixed number of decimals, so values in one column read at the same precision.
export function formatNumber(value: number, digits = 1): string {
  return new Intl.NumberFormat("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

export function signed(value: number, digits = 1): string {
  const text = formatNumber(Math.abs(value), digits);
  if (value === 0) return text;
  return `${value > 0 ? "+" : "−"}${text}`;
}

export function areaOf(measurement: Measurement): { value: string; unit: string } {
  return measurement.physical
    ? { value: formatNumber(measurement.physical.area_mm2), unit: "mm²" }
    : { value: formatNumber(measurement.pixel.area_px, 0), unit: "px²" };
}
