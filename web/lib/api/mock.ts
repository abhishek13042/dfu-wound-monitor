// Constructed data for design review and the browser tests. Selected when NEXT_PUBLIC_DFU_MOCK=1.

import { analyses, buildComparison, cases, corrections, readiness, trends, unavailableTrend } from "./mock-data";
import type { Analysis, Artifact, Case, Comparison, Consent, Correction, Keep, Readiness, Trend } from "./types";

export async function listCases(): Promise<Case[]> {
  return cases;
}

export async function getCase(id: string): Promise<Case | undefined> {
  return cases.find((item) => item.case_id === id);
}

export async function getAnalysis(id: string): Promise<Analysis | undefined> {
  return analyses.find((item) => item.analysis_id === id);
}

export async function listAnalyses(): Promise<Analysis[]> {
  return analyses;
}

export async function latestAnalysis(item: Case): Promise<Analysis | undefined> {
  const last = item.examinations.at(-1);
  return last?.analysis_id ? getAnalysis(last.analysis_id) : undefined;
}

export async function getTrend(id: string): Promise<Trend | undefined> {
  const item = await getCase(id);
  if (!item) return undefined;
  if (trends[id]) return trends[id];
  if (item.examinations.length === 0) return unavailableTrend(id, ["NO_BASELINE"]);
  return unavailableTrend(id, ["INSUFFICIENT_POINTS"]);
}

export async function getComparison(a: string, b: string): Promise<Comparison | undefined> {
  const first = await getAnalysis(a);
  const second = await getAnalysis(b);
  if (!first || !second) return undefined;
  const [earlier, later] = (first.captured_at ?? "") <= (second.captured_at ?? "") ? [first, second] : [second, first];
  return buildComparison(earlier, later);
}

export async function getReadiness(): Promise<Readiness> {
  return readiness;
}

// Constructed records have no stored photo; the screens draw a labelled placeholder instead.
export async function getArtifact(): Promise<Artifact | undefined> {
  return undefined;
}

// The demonstration always asks for consent, so the step can be reviewed.
export async function getConsent(): Promise<Consent> {
  return { text_version: "2026-11-v1", accepted_at: null, retention_hours: 24 };
}

export async function getKeep(caseId: string): Promise<Keep | undefined> {
  return cases.some((item) => item.case_id === caseId) ? { case_id: caseId, keep: caseId === cases[0]?.case_id, retention_hours: 24 } : undefined;
}

export async function listCorrections(analysisId: string): Promise<Correction[]> {
  return corrections[analysisId] ?? [];
}
