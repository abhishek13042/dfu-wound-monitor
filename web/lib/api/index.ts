// Single data entry point for every screen. NEXT_PUBLIC_DFU_MOCK=1 selects constructed data for design review
// and the browser tests; otherwise every call goes to /api/v2 and no constructed record can appear.

import { isMock } from "./mode";
import type { Analysis, Artifact, Case, Comparison, Readiness, Trend } from "./types";

export * from "./types";
export { isMock };

const source = () => (isMock ? import("./mock") : import("./live"));

export async function listCases(): Promise<Case[]> {
  return (await source()).listCases();
}

export async function getCase(id: string): Promise<Case | undefined> {
  return (await source()).getCase(id);
}

export async function getAnalysis(id: string): Promise<Analysis | undefined> {
  return (await source()).getAnalysis(id);
}

export async function listAnalyses(): Promise<Analysis[]> {
  return (await source()).listAnalyses();
}

export async function latestAnalysis(item: Case): Promise<Analysis | undefined> {
  return (await source()).latestAnalysis(item);
}

export async function getTrend(id: string): Promise<Trend | undefined> {
  return (await source()).getTrend(id);
}

export async function getComparison(a: string, b: string): Promise<Comparison | undefined> {
  return (await source()).getComparison(a, b);
}

export async function getReadiness(): Promise<Readiness> {
  return (await source()).getReadiness();
}

export async function getArtifact(id: string, kind: "image" | "mask" | "probability"): Promise<Artifact | undefined> {
  return (await source()).getArtifact(id, kind);
}
