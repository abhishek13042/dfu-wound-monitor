// Constructed data for design review and the browser tests. Selected when NEXT_PUBLIC_DFU_MOCK=1.

import { analyses, buildComparison, cases, readiness, trends, unavailableTrend } from "./mock-data";
import type { Analysis, Artifact, Case, Comparison, Readiness, Trend } from "./types";

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
