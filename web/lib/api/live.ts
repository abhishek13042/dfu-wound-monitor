// Reads /api/v2 through the generated client and maps each response onto the view models in types.ts.
// Nothing here computes a measurement, a change or a compatibility result; those come from the service.

import { cache } from "react";

import { api, call } from "./http";
import type { Analysis, Artifact, Case, Comparison, Consent, Correction, Examination, Keep, Readiness, ReasonCode, Trend } from "./types";
import type { WireAnalysis, WireCase, WireChange, WireComparison, WireExamination, WireJob, WireTrend } from "./wire";

// The schema types inner objects as plain dictionaries, so responses are read through wire.ts.
const as = <T>(value: unknown) => value as T;

const METRICS = [
  ["area", "Area"],
  ["perimeter", "Perimeter"],
  ["max_feret", "Maximum Feret"],
  ["min_feret", "Minimum Feret"],
] as const;

const UNIT: Record<string, string> = { "px^2": "px²", "mm^2": "mm²" };
const unit = (value: string | undefined) => (value ? (UNIT[value] ?? value) : "");

function toAnalysis(wire: WireAnalysis, exam?: WireExamination): Analysis {
  const provenance = wire.provenance ?? {};
  return {
    analysis_id: wire.analysis_id,
    case_id: exam?.case_id ?? null,
    examination_id: wire.image?.examination_id ?? exam?.examination_id ?? null,
    status: wire.status,
    filename: wire.image?.original_filename ?? null,
    captured_at: exam?.captured_at ?? null,
    image: wire.image ? { width: wire.image.width, height: wire.image.height, sha256: wire.image.sha256 } : null,
    quality: {
      status: wire.quality?.status ?? "PENDING",
      reason_codes: as<ReasonCode[]>(wire.quality?.reason_codes ?? []),
      config_version: wire.quality?.config_reference?.version ?? null,
    },
    model_version: wire.model_version,
    threshold: provenance.postprocessing?.threshold ?? null,
    measurement: wire.measurement ? { measurement_basis: wire.measurement.measurement_basis, pixel: wire.measurement.pixel, physical: wire.measurement.physical, calibration: wire.measurement.calibration } : null,
    inference: provenance.execution ? { duration_ms: provenance.execution.duration_ms, device: provenance.execution.device } : null,
    uncertainty: wire.inference?.uncertainty ?? null,
    warnings: wire.warnings ?? [],
    limitation: wire.limitation,
  };
}

// A job that is still queued or running, or that failed before a record was written, has only a status.
function fromJob(job: WireJob): Analysis {
  return {
    analysis_id: job.analysis_id,
    case_id: null,
    examination_id: null,
    status: job.status,
    filename: null,
    captured_at: null,
    image: null,
    quality: { status: "PENDING", reason_codes: [], config_version: null },
    model_version: null,
    threshold: null,
    measurement: null,
    inference: null,
    warnings: [],
    failure: job.error
      ? { category: as<NonNullable<Analysis["failure"]>["category"]>(job.error.category), failure_class: job.error.failure_class, code: job.error.code, message: job.error.message }
      : undefined,
  };
}

const getExamination = cache(async (id: string) => {
  const client = await api();
  const body = await call(client.GET("/api/v2/examinations/{examination_id}", { params: { path: { examination_id: id } } }));
  if (!body) return undefined;
  const examination = as<WireExamination>(body.examination);
  const analyses = as<WireAnalysis[]>(body.analyses ?? []).map((item) => toAnalysis(item, examination));
  return { examination, analyses };
});

function toExamination(wire: WireExamination, analyses: Analysis[]): Examination {
  return {
    examination_id: wire.examination_id,
    captured_at: wire.captured_at,
    timestamp_source: wire.timestamp_source,
    notes: wire.notes,
    analysis_id: analyses.at(-1)?.analysis_id,
  };
}

export const getCase = cache(async (id: string): Promise<Case | undefined> => {
  const client = await api();
  const body = await call(client.GET("/api/v2/cases/{case_id}", { params: { path: { case_id: id } } }));
  if (!body) return undefined;
  const record = as<WireCase>(body.case);
  const exams = as<WireExamination[]>(body.examinations ?? []);
  // The case response carries no analyses, so each examination is read on its own.
  const detail = await Promise.all(exams.map((exam) => getExamination(exam.examination_id)));
  const examinations = exams
    .map((exam, index) => toExamination(exam, detail[index]?.analyses ?? []))
    .sort((a, b) => (a.captured_at ?? "").localeCompare(b.captured_at ?? ""));
  return { ...record, examinations };
});

export async function listCases(): Promise<Case[]> {
  const client = await api();
  const body = await call(client.GET("/api/v2/cases"));
  const records = as<WireCase[]>(body?.cases ?? []);
  const cases = await Promise.all(records.map((record) => getCase(record.case_id)));
  return cases.filter((item): item is Case => Boolean(item));
}

export const getAnalysis = cache(async (id: string): Promise<Analysis | undefined> => {
  const client = await api();
  const body = await call(client.GET("/api/v2/analyses/{analysis_id}", { params: { path: { analysis_id: id } } }));
  if (!body) return undefined;
  if (!("image" in body)) return fromJob(as<WireJob>(body));
  const wire = as<WireAnalysis>(body);
  const exam = wire.image.examination_id ? (await getExamination(wire.image.examination_id))?.examination : undefined;
  return toAnalysis(wire, exam);
});

export async function listAnalyses(): Promise<Analysis[]> {
  const cases = await listCases();
  const exams = cases.flatMap((item) => item.examinations);
  const detail = await Promise.all(exams.map((exam) => getExamination(exam.examination_id)));
  return detail.flatMap((item) => item?.analyses ?? []);
}

export async function latestAnalysis(item: Case): Promise<Analysis | undefined> {
  const last = item.examinations.at(-1);
  return last?.analysis_id ? getAnalysis(last.analysis_id) : undefined;
}

const change = (entry: Record<string, WireChange> | null) =>
  entry?.area ? { absolute_change: entry.area.absolute_change, percent_change: entry.area.percent_change } : null;

export async function getTrend(id: string): Promise<Trend | undefined> {
  const client = await api();
  const body = await call(client.GET("/api/v2/cases/{case_id}/trend", { params: { path: { case_id: id } } }));
  if (!body) return undefined;
  const wire = as<WireTrend>(body.trend);
  const item = await getCase(id);
  const capturedAt = new Map(item?.examinations.map((exam) => [exam.examination_id, exam.captured_at]) ?? []);
  return {
    status: wire.status,
    case_id: wire.case_id,
    basis: wire.basis,
    unit: { area: unit(wire.unit?.area), perimeter: unit(wire.unit?.perimeter), max_feret: unit(wire.unit?.max_feret) },
    rows: wire.rows.map((row) => ({
      examination_id: row.examination_id,
      analysis_id: row.analysis_id,
      captured_at: row.captured_at,
      days_since_baseline: row.days_since_baseline,
      is_baseline: row.is_baseline,
      values: { area: row.values.area, perimeter: row.values.perimeter, max_feret: row.values.max_feret },
      from_baseline: change(row.from_baseline),
      from_previous: change(row.from_previous),
      mask_source: row.mask_source ?? "MODEL",
      correction_id: row.correction_id ?? null,
    })),
    excluded: wire.excluded.map((entry) => ({ ...entry, captured_at: capturedAt.get(entry.examination_id) ?? null })),
    warnings: wire.warnings ?? [],
    reason_codes: wire.reason_codes ?? [],
    version: wire.version,
    label: wire.label,
  };
}

export async function getComparison(a: string, b: string): Promise<Comparison | undefined> {
  const client = await api();
  const body = await call(client.GET("/api/v2/compare", { params: { query: { analysis_a: a, analysis_b: b } } }));
  if (!body) return undefined;
  const wire = as<WireComparison>(body.comparison);
  const physical = wire.basis === "PHYSICALLY_CALIBRATED";
  const units: Record<string, string> = physical
    ? { area: "mm²", perimeter: "mm", max_feret: "mm", min_feret: "mm" }
    : { area: "px²", perimeter: "px", max_feret: "px", min_feret: "px" };
  return {
    status: wire.status,
    reason_codes: wire.reason_codes ?? [],
    warnings: wire.warnings ?? [],
    earlier: wire.earlier,
    later: wire.later,
    basis: wire.basis,
    interval_days: wire.interval_days,
    metrics: METRICS.filter(([key]) => wire.metrics?.[key]).map(([key, name]) => ({
      name,
      unit: units[key],
      earlier: wire.metrics[key].earlier,
      later: wire.metrics[key].later,
      absolute_change: wire.metrics[key].absolute_change,
      percent_change: wire.metrics[key].percent_change,
    })),
    label: wire.label,
  };
}

// The rail must render even while the service is down, so readiness never redirects.
export async function getReadiness(): Promise<Readiness> {
  const down: Readiness = { model: "NOT_READY", database: "NOT_READY", storage: "NOT_READY", queue: "NOT_READY" };
  try {
    const client = await api();
    const { data } = await client.GET("/health/ready");
    const body = as<Record<string, string> | undefined>(data);
    if (!body) return down;
    const state = (key: string) => (body[key] === "READY" ? "READY" : "NOT_READY");
    return { model: state("model"), database: state("database"), storage: state("storage"), queue: state("queue") };
  } catch {
    return down;
  }
}

export async function getArtifact(id: string, kind: "image" | "mask" | "probability"): Promise<Artifact | undefined> {
  const client = await api();
  const body = await call(client.GET("/api/v2/analyses/{analysis_id}/artifacts/{kind}", { params: { path: { analysis_id: id, kind } } }));
  // A relative URL points at the service, so the browser reaches it through the /api/v2 proxy route.
  return body ? as<Artifact>(body) : undefined;
}

export async function getConsent(): Promise<Consent> {
  const client = await api();
  const body = await call(client.GET("/api/v2/consent"));
  if (!body) throw new Error("The consent record was not returned.");
  return body;
}

export async function getKeep(caseId: string): Promise<Keep | undefined> {
  const client = await api();
  return call(client.GET("/api/v2/cases/{case_id}/keep", { params: { path: { case_id: caseId } } }));
}

export async function listCorrections(analysisId: string): Promise<Correction[]> {
  const client = await api();
  const body = await call(client.GET("/api/v2/analyses/{analysis_id}/corrections", { params: { path: { analysis_id: analysisId } } }));
  return body ? as<Correction[]>(body.corrections) : [];
}
