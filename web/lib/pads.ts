import type { Analysis, ReasonCode } from "@/lib/api";

export type PadState = "pass" | "fail" | "none";

export interface Pad {
  key: string;
  name: string;
  short: string;
  reason: ReasonCode;
  reads: string;
  limit: string;
}

// Fixed order. The thresholds are configs/quality/quality_gate_v1.json, version p03-s02-v1.
export const PADS: Pad[] = [
  { key: "decode", name: "Decode", short: "Decode", reason: "UNREADABLE", reads: "The file opens as an image", limit: "Readable" },
  { key: "size", name: "Size", short: "Size", reason: "TOO_SMALL", reads: "Shortest side", limit: "≥ 128 px" },
  { key: "aspect", name: "Aspect", short: "Aspect", reason: "BAD_ASPECT_RATIO", reads: "Width to height", limit: "≤ 4.0" },
  { key: "content", name: "Content", short: "Content", reason: "INSUFFICIENT_CONTENT", reads: "Non-empty area, entropy", limit: "≥ 0.30, 3.0" },
  { key: "sharpness", name: "Sharpness", short: "Sharp", reason: "BLURRY", reads: "Laplacian variance", limit: "≥ 8.0" },
  { key: "under", name: "Underexposure", short: "Under", reason: "UNDEREXPOSED", reads: "Mean luminance, dark share", limit: "≥ 30, ≤ 0.70" },
  { key: "over", name: "Overexposure", short: "Over", reason: "OVEREXPOSED", reads: "Mean luminance, bright share", limit: "≤ 220, ≤ 0.50" },
  { key: "contrast", name: "Contrast", short: "Contrast", reason: "LOW_CONTRAST", reads: "Luminance deviation", limit: "≥ 10" },
  { key: "glare", name: "Glare", short: "Glare", reason: "GLARE", reads: "Glare share", limit: "≤ 0.40" },
];

export function padStates(quality: Analysis["quality"] | undefined): PadState[] {
  if (!quality || quality.status === "PENDING") return PADS.map(() => "none");
  if (quality.status === "ACCEPTED") return PADS.map(() => "pass");
  // An unreadable file stops the gate, so nothing after decode was read.
  if (quality.reason_codes.includes("UNREADABLE")) return PADS.map((_, index) => (index === 0 ? "fail" : "none"));
  return PADS.map((pad) => (quality.reason_codes.includes(pad.reason) ? "fail" : "pass"));
}

export function failedNames(states: PadState[]): string[] {
  return PADS.filter((_, index) => states[index] === "fail").map((pad) => pad.name);
}
