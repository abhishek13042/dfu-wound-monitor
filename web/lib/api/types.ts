// View models the screens read. lib/api/live.ts maps /api/v2 responses (schema.d.ts, wire.ts) onto them,
// and lib/api/mock-data.ts builds them from constructed data.

export type AnalysisStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "QUALITY_REJECTED" | "FAILED";
export type IdentityStatus = "VERIFIED" | "UNVERIFIED" | "UNKNOWN";
export type MeasurementBasis = "PIXEL_BASED" | "PHYSICALLY_CALIBRATED";
export type TimestampSource = "EXIF" | "USER_ENTERED" | "DEVICE" | "UNKNOWN";

export type ReasonCode =
  | "UNREADABLE"
  | "TOO_SMALL"
  | "BAD_ASPECT_RATIO"
  | "INSUFFICIENT_CONTENT"
  | "BLURRY"
  | "UNDEREXPOSED"
  | "OVEREXPOSED"
  | "LOW_CONTRAST"
  | "GLARE";

export type ErrorCategory =
  | "INVALID_INPUT"
  | "UNAUTHENTICATED"
  | "NOT_FOUND"
  | "CONFLICT"
  | "QUALITY_REJECTED"
  | "BUSY"
  | "MODEL_FAILURE"
  | "MODEL_NOT_READY"
  | "INFRASTRUCTURE_FAILURE";

export interface Warning {
  code: string;
  message?: string;
}

export interface Uncertainty {
  tta_disagreement: number;
  method: string;
  region: "MASK_AND_BAND" | "WHOLE_IMAGE";
  empty_mask: boolean;
  // Set by the study (REQ-P09-S02-003): the number is shown only when it tracked error on validation.
  summary_shown: boolean;
}

export interface Measurement {
  measurement_basis: MeasurementBasis;
  pixel: {
    area_px: number;
    perimeter_px: number;
    max_feret_px: number;
    min_feret_px: number;
    component_count: number;
  };
  physical: {
    area_mm2: number;
    perimeter_mm: number;
    max_feret_mm: number;
    min_feret_mm: number;
  } | null;
  // Where the scale came from; null when the values are in pixels.
  calibration?: { pixels_per_mm: number; method: string; source: string | null; uncertainty_pct: number | null } | null;
}

export interface Analysis {
  analysis_id: string;
  // A queued, running or failed job has no stored record yet, so the fields below it can be null.
  case_id: string | null;
  examination_id: string | null;
  status: AnalysisStatus;
  filename: string | null;
  captured_at: string | null;
  image: { width: number; height: number; sha256: string } | null;
  quality: { status: "ACCEPTED" | "REJECTED" | "PENDING"; reason_codes: ReasonCode[]; config_version: string | null };
  model_version: string | null;
  threshold: number | null;
  measurement: Measurement | null;
  inference: { duration_ms: number; device: string } | null;
  // REQ-P09-S02-002: how much the flipped views disagree; absent when TTA was off or the record predates it.
  uncertainty?: Uncertainty | null;
  warnings: Warning[];
  // The external-validation limitation the service attaches to every stored result.
  limitation?: string;
  failure?: { category: ErrorCategory; failure_class: string; code: string; message?: string; request_id?: string; retry?: number };
}

export interface Examination {
  examination_id: string;
  captured_at: string | null;
  timestamp_source: TimestampSource;
  notes: string | null;
  analysis_id?: string;
}

export interface Case {
  case_id: string;
  label: string | null;
  identity_status: IdentityStatus;
  external_reference: string | null;
  data_source: string;
  created_at: string;
  examinations: Examination[];
  changed?: boolean;
}

export interface TrendRow {
  examination_id: string;
  analysis_id: string;
  captured_at: string;
  days_since_baseline: number;
  is_baseline: boolean;
  values: { area: number; perimeter: number; max_feret: number };
  // Area change, as the service computed it.
  from_baseline: { absolute_change: number; percent_change: number | null } | null;
  from_previous: { absolute_change: number; percent_change: number | null } | null;
  // REQ-P09-S03-004: CORRECTED when the value comes from an outline the user redrew.
  mask_source?: MaskSource;
  correction_id?: string | null;
}

export interface Trend {
  status: "AVAILABLE" | "UNAVAILABLE";
  case_id: string;
  basis: MeasurementBasis | null;
  unit: { area: string; perimeter: string; max_feret: string };
  rows: TrendRow[];
  excluded: { examination_id: string; analysis_id: string | null; captured_at?: string | null; reason_codes: string[] }[];
  warnings: Warning[];
  reason_codes: string[];
  version: string;
  label: string;
}

export interface ComparisonPoint {
  case_id: string | null;
  examination_id: string | null;
  analysis_id: string;
  captured_at: string | null;
  model_version: string | null;
  measurement_basis: MeasurementBasis | null;
}

export interface Comparison {
  status: "AVAILABLE" | "UNAVAILABLE";
  reason_codes: string[];
  warnings: Warning[];
  earlier: ComparisonPoint;
  later: ComparisonPoint;
  basis: MeasurementBasis | null;
  interval_days: number | null;
  metrics: { name: string; unit: string; earlier: number; later: number; absolute_change: number; percent_change: number | null }[];
  label: string;
}

export type MaskSource = "MODEL" | "CORRECTED";

// A user's redrawn outline (P09-S03). Each save is a new version; the model's own result is never changed.
export interface Correction {
  correction_id: string;
  analysis_id: string;
  version: number;
  author: string;
  created_at: string;
  measurement: { status: string; pixel: Measurement["pixel"]; physical: Measurement["physical"]; warnings: Warning[] };
  research_opt_in: boolean;
  links: { self: string; mask: string };
}

export interface Artifact {
  url: string;
  expires_at: string;
}

export interface Readiness {
  model: "READY" | "NOT_READY";
  database: "READY" | "NOT_READY";
  storage: "READY" | "NOT_READY";
  queue: "READY" | "NOT_READY";
}

// Consent is per user and per text version; a null accepted_at means it is asked before the first upload.
export interface Consent {
  text_version: string;
  accepted_at: string | null;
  retention_hours: number;
}

export interface Keep {
  case_id: string;
  keep: boolean;
  retention_hours: number;
}
