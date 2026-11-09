// Inner shapes of /api/v2 responses. OpenAPI types these as plain objects, so they are written out here
// from captured responses of the running service (P08-S01). The envelopes come from schema.d.ts.

import type { IdentityStatus, MeasurementBasis, TimestampSource, Uncertainty } from "./types";

export interface WireCase {
  case_id: string;
  identity_status: IdentityStatus;
  external_reference: string | null;
  data_source: string;
  label: string | null;
  created_at: string;
}

export interface WireExamination {
  examination_id: string;
  case_id: string | null;
  captured_at: string | null;
  timestamp_source: TimestampSource;
  notes: string | null;
  created_at: string;
}

export interface WireImage {
  image_id: string;
  examination_id: string | null;
  sha256: string;
  original_filename: string | null;
  format: string;
  width: number;
  height: number;
  created_at: string;
}

export interface WireQuality {
  status: "ACCEPTED" | "REJECTED";
  reason_codes: string[];
  measurements: Record<string, number>;
  thresholds: Record<string, number>;
  config_reference: { version: string } | null;
}

export interface WireWarning {
  code: string;
  message?: string;
  [extra: string]: unknown;
}

export interface WireMeasurement {
  measurement_basis: MeasurementBasis;
  status: string;
  pixel: { area_px: number; perimeter_px: number; max_feret_px: number; min_feret_px: number; component_count: number };
  physical: { area_mm2: number; perimeter_mm: number; max_feret_mm: number; min_feret_mm: number } | null;
  calibration: { pixels_per_mm: number; method: string; source: string | null; uncertainty_pct: number | null } | null;
}

export interface WireAnalysis {
  analysis_id: string;
  status: "COMPLETED" | "QUALITY_REJECTED" | "FAILED";
  image: WireImage;
  quality: WireQuality;
  model_version: string | null;
  measurement: WireMeasurement | null;
  warnings: WireWarning[];
  provenance: {
    request_id?: string;
    postprocessing?: { threshold: number };
    execution?: { device: string; duration_ms: number };
  };
  inference?: { uncertainty?: Uncertainty | null } | null;
  links: Record<string, string>;
  limitation: string;
}

export interface WireJob {
  analysis_id: string;
  status: "QUEUED" | "RUNNING" | "FAILED" | "COMPLETED" | "QUALITY_REJECTED";
  error: { category: string; failure_class: string; code: string; message: string } | null;
  links: Record<string, string>;
}

export interface WireChange {
  earlier: number;
  later: number;
  absolute_change: number;
  percent_change: number | null;
  state: string;
}

export interface WireTrend {
  status: "AVAILABLE" | "UNAVAILABLE";
  case_id: string;
  basis: MeasurementBasis | null;
  unit: Record<string, string>;
  rows: {
    examination_id: string;
    analysis_id: string;
    captured_at: string;
    days_since_baseline: number;
    is_baseline: boolean;
    model_version: string;
    values: Record<string, number>;
    from_baseline: Record<string, WireChange> | null;
    from_previous: Record<string, WireChange> | null;
    flags: string[];
    mask_source?: "MODEL" | "CORRECTED";
    correction_id?: string | null;
  }[];
  excluded: { examination_id: string; analysis_id: string | null; reason_codes: string[] }[];
  warnings: WireWarning[];
  reason_codes: string[];
  version: string;
  label: string;
}

export interface WirePoint {
  case_id: string;
  examination_id: string;
  analysis_id: string;
  captured_at: string | null;
  model_version: string | null;
  measurement_basis: MeasurementBasis | null;
}

export interface WireComparison {
  status: "AVAILABLE" | "UNAVAILABLE";
  reason_codes: string[];
  warnings: WireWarning[];
  earlier: WirePoint;
  later: WirePoint;
  basis: MeasurementBasis | null;
  interval_days: number | null;
  metrics: Record<string, WireChange>;
  label: string;
}
