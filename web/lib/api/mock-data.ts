// Constructed demonstration records. None of this is patient data, and every screen that shows it says so.

import type { Analysis, Case, Comparison, Correction, Readiness, Trend } from "./types";

const MODEL = "spec-02-03-resnet34-unet-512-v1";
const QC = "p03-s02-v1";

const pixel = (area: number, perimeter: number, max: number, min: number, components = 1) => ({
  measurement_basis: "PIXEL_BASED" as const,
  pixel: { area_px: area, perimeter_px: perimeter, max_feret_px: max, min_feret_px: min, component_count: components },
  physical: null,
});

const calibrated = (area: number, perimeter: number, max: number, min: number, scale: number) => ({
  measurement_basis: "PHYSICALLY_CALIBRATED" as const,
  pixel: {
    area_px: Math.round(area * scale * scale),
    perimeter_px: Math.round(perimeter * scale),
    max_feret_px: Math.round(max * scale),
    min_feret_px: Math.round(min * scale),
    component_count: 1,
  },
  physical: { area_mm2: area, perimeter_mm: perimeter, max_feret_mm: max, min_feret_mm: min },
  calibration: { pixels_per_mm: scale, method: "ARUCO_MARKER", source: "aruco DICT_4X4_50 id 7", uncertainty_pct: 1.2 },
});

const accepted = { status: "ACCEPTED" as const, reason_codes: [], config_version: QC };
const noPixelScale = {
  code: "PIXEL_SCALE_NOT_CONTROLLED",
  message: "No calibration: pixel changes also reflect camera distance and zoom",
};

function completed(
  id: string,
  caseId: string,
  examinationId: string,
  capturedAt: string,
  measurement: Analysis["measurement"],
  filename: string,
): Analysis {
  return {
    analysis_id: id,
    case_id: caseId,
    examination_id: examinationId,
    status: "COMPLETED",
    filename,
    captured_at: capturedAt,
    image: { width: 1600, height: 1200, sha256: `${id}9f3c1ab07de24c55` },
    quality: accepted,
    model_version: MODEL,
    threshold: 0.4,
    measurement,
    inference: { duration_ms: 5812, device: "cpu" },
    uncertainty: { tta_disagreement: 0.0184, method: "flip_tta_v1", region: "MASK_AND_BAND", empty_mask: false, summary_shown: true },
    warnings: measurement?.measurement_basis === "PIXEL_BASED" ? [noPixelScale] : [],
  };
}

export const analyses: Analysis[] = [
  completed("a1d04e", "c-0007", "e-0701", "2026-09-02T09:40:00Z", calibrated(412.6, 86.2, 31.4, 19.8, 8.1), "visit-01.png"),
  completed("a1d052", "c-0007", "e-0702", "2026-09-16T10:05:00Z", calibrated(388.1, 82.9, 30.1, 18.9, 8.1), "visit-02.png"),
  completed("a1d079", "c-0007", "e-0704", "2026-10-14T09:15:00Z", calibrated(341.7, 77.5, 28.2, 17.6, 8.1), "visit-04.png"),
  completed("a1d093", "c-0007", "e-0705", "2026-10-28T09:50:00Z", calibrated(322.4, 75.1, 27.3, 17.0, 8.1), "visit-05.png"),
  {
    analysis_id: "a1d066",
    case_id: "c-0007",
    examination_id: "e-0703",
    status: "QUALITY_REJECTED",
    filename: "visit-03.jpg",
    captured_at: "2026-09-30T09:30:00Z",
    image: { width: 1600, height: 1200, sha256: "a1d0669f3c1ab07de24c55" },
    quality: { status: "REJECTED", reason_codes: ["BLURRY", "GLARE"], config_version: QC },
    model_version: MODEL,
    threshold: 0.4,
    measurement: null,
    inference: null,
    warnings: [],
  },
  completed("b2e011", "c-0012", "e-1201", "2026-10-06T14:20:00Z", pixel(58214, 1184, 402, 217), "photo-a.png"),
  completed("b2e018", "c-0012", "e-1202", "2026-10-20T14:10:00Z", pixel(51327, 1102, 381, 204), "photo-b.png"),
  completed("b2e031", "c-0015", "e-1501", "2026-10-22T11:00:00Z", pixel(23906, 744, 262, 141, 2), "single.png"),
  {
    analysis_id: "c3f0a1",
    case_id: "c-0019",
    examination_id: "e-1901",
    status: "RUNNING",
    filename: "intake.png",
    captured_at: "2026-10-31T16:02:00Z",
    image: { width: 2048, height: 1536, sha256: "c3f0a19f3c1ab07de24c55" },
    quality: { status: "ACCEPTED", reason_codes: [], config_version: QC },
    model_version: MODEL,
    threshold: 0.4,
    measurement: null,
    inference: null,
    warnings: [],
  },
  {
    analysis_id: "c3f0b7",
    case_id: "c-0021",
    examination_id: "e-2101",
    status: "QUEUED",
    filename: "intake-2.png",
    captured_at: "2026-10-31T16:04:00Z",
    image: { width: 2048, height: 1536, sha256: "c3f0b79f3c1ab07de24c55" },
    quality: { status: "PENDING", reason_codes: [], config_version: QC },
    model_version: MODEL,
    threshold: 0.4,
    measurement: null,
    inference: null,
    warnings: [],
  },
  {
    analysis_id: "c3f0c9",
    case_id: "c-0023",
    examination_id: "e-2301",
    status: "FAILED",
    filename: "intake-3.png",
    captured_at: "2026-10-30T12:40:00Z",
    image: { width: 1600, height: 1200, sha256: "c3f0c99f3c1ab07de24c55" },
    quality: accepted,
    model_version: MODEL,
    threshold: 0.4,
    measurement: null,
    inference: null,
    warnings: [],
    failure: {
      category: "INFRASTRUCTURE_FAILURE",
      failure_class: "SERVICE",
      code: "WORKER_LOST",
      request_id: "req_7be21d04",
      retry: 3,
    },
  },
];

const exam = (id: string, at: string, source: Case["examinations"][number]["timestamp_source"], notes: string, analysis: string) => ({
  examination_id: id,
  captured_at: at,
  timestamp_source: source,
  notes,
  analysis_id: analysis,
});

export const cases: Case[] = [
  {
    case_id: "c-0007",
    label: "Constructed series A, left plantar",
    identity_status: "VERIFIED",
    external_reference: "DEMO-A",
    data_source: "Constructed demonstration",
    created_at: "2026-09-02T09:30:00Z",
    examinations: [
      exam("e-0701", "2026-09-02T09:40:00Z", "EXIF", "First examination. Ruler in frame.", "a1d04e"),
      exam("e-0702", "2026-09-16T10:05:00Z", "EXIF", "", "a1d052"),
      exam("e-0703", "2026-09-30T09:30:00Z", "USER_ENTERED", "Retake was not possible at this visit.", "a1d066"),
      exam("e-0704", "2026-10-14T09:15:00Z", "EXIF", "", "a1d079"),
      exam("e-0705", "2026-10-28T09:50:00Z", "EXIF", "Same room and lighting as earlier visits.", "a1d093"),
    ],
  },
  {
    case_id: "c-0012",
    label: "Constructed series B, right heel",
    changed: true,
    identity_status: "UNVERIFIED",
    external_reference: null,
    data_source: "Constructed demonstration",
    created_at: "2026-10-06T14:10:00Z",
    examinations: [
      exam("e-1201", "2026-10-06T14:20:00Z", "DEVICE", "", "b2e011"),
      exam("e-1202", "2026-10-20T14:10:00Z", "DEVICE", "", "b2e018"),
    ],
  },
  {
    case_id: "c-0015",
    label: "Constructed single visit",
    identity_status: "UNKNOWN",
    external_reference: null,
    data_source: "Constructed demonstration",
    created_at: "2026-10-22T10:55:00Z",
    examinations: [exam("e-1501", "2026-10-22T11:00:00Z", "UNKNOWN", "", "b2e031")],
  },
  {
    case_id: "c-0019",
    label: "Constructed intake, running",
    identity_status: "UNVERIFIED",
    external_reference: null,
    data_source: "Constructed demonstration",
    created_at: "2026-10-31T16:00:00Z",
    examinations: [exam("e-1901", "2026-10-31T16:02:00Z", "DEVICE", "", "c3f0a1")],
  },
  {
    case_id: "c-0021",
    label: "Constructed intake, queued",
    identity_status: "UNVERIFIED",
    external_reference: null,
    data_source: "Constructed demonstration",
    created_at: "2026-10-31T16:03:00Z",
    examinations: [exam("e-2101", "2026-10-31T16:04:00Z", "DEVICE", "", "c3f0b7")],
  },
  {
    case_id: "c-0023",
    label: "Constructed intake, worker lost",
    changed: true,
    identity_status: "UNVERIFIED",
    external_reference: null,
    data_source: "Constructed demonstration",
    created_at: "2026-10-30T12:35:00Z",
    examinations: [exam("e-2301", "2026-10-30T12:40:00Z", "DEVICE", "", "c3f0c9")],
  },
  {
    case_id: "c-0026",
    label: "Constructed case, no examinations yet",
    identity_status: "UNKNOWN",
    external_reference: null,
    data_source: "Constructed demonstration",
    created_at: "2026-10-31T17:00:00Z",
    examinations: [],
  },
];

const LABEL =
  "Image-derived technical trend of the segmented region. Not a clinical assessment of healing, prognosis or treatment response.";

const row = (
  examination_id: string,
  analysis_id: string,
  captured_at: string,
  days: number,
  area: number,
  perimeter: number,
  max_feret: number,
  base: number | null,
  previous: number | null,
) => ({
  examination_id,
  analysis_id,
  captured_at,
  days_since_baseline: days,
  is_baseline: base === null,
  values: { area, perimeter, max_feret },
  from_baseline:
    base === null
      ? null
      : { absolute_change: +(area - base).toFixed(1), percent_change: +(((area - base) / base) * 100).toFixed(1) },
  from_previous:
    previous === null
      ? null
      : { absolute_change: +(area - previous).toFixed(1), percent_change: +(((area - previous) / previous) * 100).toFixed(1) },
});

// One constructed correction, so the corrected-outline marks can be reviewed in mock mode.
export const corrections: Record<string, Correction[]> = {
  a1d079: [
    {
      correction_id: "cor-0704a",
      analysis_id: "a1d079",
      version: 1,
      author: "demo",
      created_at: "2026-10-14T11:02:00Z",
      measurement: {
        status: "MEASURED",
        pixel: { area_px: 86412, perimeter_px: 1198, max_feret_px: 441, min_feret_px: 264, component_count: 1 },
        physical: { area_mm2: 341.7, perimeter_mm: 77.5, max_feret_mm: 28.2, min_feret_mm: 16.9 },
        warnings: [{ code: "CORRECTED_MASK", message: "Measured from an outline corrected by hand, not the model's own outline" }],
      },
      research_opt_in: false,
      links: { self: "/api/v2/corrections/cor-0704a", mask: "/api/v2/corrections/cor-0704a/mask" },
    },
  ],
};

export const trends: Record<string, Trend> = {
  "c-0007": {
    status: "AVAILABLE",
    case_id: "c-0007",
    basis: "PHYSICALLY_CALIBRATED",
    unit: { area: "mm²", perimeter: "mm", max_feret: "mm" },
    rows: [
      row("e-0701", "a1d04e", "2026-09-02T09:40:00Z", 0, 412.6, 86.2, 31.4, null, null),
      row("e-0702", "a1d052", "2026-09-16T10:05:00Z", 14, 388.1, 82.9, 30.1, 412.6, 412.6),
      { ...row("e-0704", "a1d079", "2026-10-14T09:15:00Z", 42, 341.7, 77.5, 28.2, 412.6, 388.1), mask_source: "CORRECTED", correction_id: "cor-0704a" },
      row("e-0705", "a1d093", "2026-10-28T09:50:00Z", 56, 322.4, 75.1, 27.3, 412.6, 341.7),
    ],
    excluded: [
      { examination_id: "e-0703", analysis_id: "a1d066", captured_at: "2026-09-30T09:30:00Z", reason_codes: ["MEASUREMENT_MISSING"] },
    ],
    warnings: [{ code: "EXAMINATIONS_EXCLUDED", message: "One examination is left out of this trend" }],
    reason_codes: [],
    version: "p04-s03-v1",
    label: LABEL,
  },
  "c-0012": {
    status: "AVAILABLE",
    case_id: "c-0012",
    basis: "PIXEL_BASED",
    unit: { area: "px²", perimeter: "px", max_feret: "px" },
    rows: [
      row("e-1201", "b2e011", "2026-10-06T14:20:00Z", 0, 58214, 1184, 402, null, null),
      row("e-1202", "b2e018", "2026-10-20T14:10:00Z", 14, 51327, 1102, 381, 58214, 58214),
    ],
    excluded: [],
    warnings: [noPixelScale],
    reason_codes: [],
    version: "p04-s03-v1",
    label: LABEL,
  },
};

export function unavailableTrend(caseId: string, reasons: string[]): Trend {
  return {
    status: "UNAVAILABLE",
    case_id: caseId,
    basis: null,
    unit: { area: "", perimeter: "", max_feret: "" },
    rows: [],
    excluded: [],
    warnings: [],
    reason_codes: reasons,
    version: "p04-s03-v1",
    label: LABEL,
  };
}

const point = (item: Analysis) => ({
  case_id: item.case_id,
  examination_id: item.examination_id,
  analysis_id: item.analysis_id,
  captured_at: item.captured_at,
  model_version: item.model_version,
  measurement_basis: item.measurement?.measurement_basis ?? null,
});

export function buildComparison(earlier: Analysis, later: Analysis): Comparison {
  const label = "Image-derived technical comparison. The two photos are not claimed to be aligned.";
  const days = Math.round((Date.parse(later.captured_at!) - Date.parse(earlier.captured_at!)) / 86_400_000);
  const reasons: string[] = [];
  if (earlier.case_id !== later.case_id) reasons.push("DIFFERENT_CASE");
  if (!earlier.measurement || !later.measurement) reasons.push("MEASUREMENT_MISSING");
  else if (earlier.measurement.measurement_basis !== later.measurement.measurement_basis)
    reasons.push("MEASUREMENT_BASIS_MISMATCH");
  if (reasons.length || !earlier.measurement || !later.measurement) {
    return { status: "UNAVAILABLE", reason_codes: reasons, warnings: [], earlier: point(earlier), later: point(later), basis: null, interval_days: days, metrics: [], label };
  }
  const physical = earlier.measurement.physical && later.measurement.physical;
  const a = earlier.measurement;
  const b = later.measurement;
  const metric = (name: string, unit: string, x: number, y: number) => ({
    name,
    unit,
    earlier: x,
    later: y,
    absolute_change: +(y - x).toFixed(1),
    percent_change: +(((y - x) / x) * 100).toFixed(1),
  });
  const metrics = physical
    ? [
        metric("Area", "mm²", a.physical!.area_mm2, b.physical!.area_mm2),
        metric("Perimeter", "mm", a.physical!.perimeter_mm, b.physical!.perimeter_mm),
        metric("Maximum Feret", "mm", a.physical!.max_feret_mm, b.physical!.max_feret_mm),
      ]
    : [
        metric("Area", "px²", a.pixel.area_px, b.pixel.area_px),
        metric("Perimeter", "px", a.pixel.perimeter_px, b.pixel.perimeter_px),
        metric("Maximum Feret", "px", a.pixel.max_feret_px, b.pixel.max_feret_px),
      ];
  return {
    status: "AVAILABLE",
    reason_codes: [],
    warnings: physical ? [] : [noPixelScale],
    earlier: point(earlier),
    later: point(later),
    basis: a.measurement_basis,
    interval_days: days,
    metrics,
    label,
  };
}

export const readiness: Readiness = { model: "READY", database: "READY", storage: "READY", queue: "READY" };
