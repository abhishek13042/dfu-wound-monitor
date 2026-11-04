import { describe, expect, it } from "vitest";

import type { Measurement } from "@/lib/api";
import { areaOf, formatDate, signed } from "@/lib/format";

const pixel = { area_px: 5120, perimeter_px: 300, max_feret_px: 110, min_feret_px: 60 } as Measurement["pixel"];

describe("units (REQ-P08-S02-004)", () => {
  it("shows pixels when the photo has no scale, never millimetres", () => {
    const area = areaOf({ pixel, physical: null } as Measurement);
    expect(area.unit).toBe("px²");
    expect(area.value).toBe("5,120");
  });

  it("shows millimetres only from the physical measurement", () => {
    const area = areaOf({ pixel, physical: { area_mm2: 412.3 } } as Measurement);
    expect(area).toEqual({ value: "412.3", unit: "mm²" });
  });
});

describe("formatting", () => {
  it("writes a dash for a missing date", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("2026-03-02T10:00:00Z")).toBe("02 Mar 2026");
  });

  it("signs changes with a true minus", () => {
    expect(signed(-4.25)).toBe("−4.3");
    expect(signed(3)).toBe("+3.0");
    expect(signed(0)).toBe("0.0");
  });
});
