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
