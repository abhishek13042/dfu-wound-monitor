import type { Metadata } from "next";
import Link from "next/link";
import { Plus } from "lucide-react";

import { CasesTable, type CaseRow } from "@/components/CasesTable";
import { PageHeader } from "@/components/PageHeader";
import { buttonVariants } from "@/components/ui/button";
import { isMock, latestAnalysis, listCases } from "@/lib/api";

export const metadata: Metadata = { title: "Cases" };

export default async function CasesPage({ searchParams }: { searchParams: Promise<{ state?: string }> }) {
  const { state } = await searchParams;
  // ?state=empty previews the empty state against constructed data only.
  const cases = isMock && state === "empty" ? [] : await listCases();
  const latest = await Promise.all(cases.map((item) => latestAnalysis(item)));
  const rows: CaseRow[] = await Promise.all(
    cases.map(async (item, index) => {
      const analysis = latest[index];
      return {
        id: item.case_id,
        label: item.label ?? item.case_id,
        identity: item.identity_status,
        examinations: item.examinations.length,
        latestAt: item.examinations.at(-1)?.captured_at ?? null,
        status: analysis?.status ?? null,
        quality: analysis?.quality,
        measurement: analysis?.measurement ?? null,
        changed: item.changed ?? false,
      };
    }),
  );

  const models = [...new Set(latest.map((item) => item?.model_version).filter(Boolean))];

  return (
    <>
      <PageHeader
        title="Cases"
        actions={
          <Link href="/cases/new" className={buttonVariants()}>
            <Plus aria-hidden="true" />
            New case
          </Link>
        }
      />
      {rows.length === 0 ? (
        <div className="panel px-6 py-14 text-center">
          <h2 className="text-lg">No cases yet</h2>
          <p className="mt-1 text-ink-2">A case groups the examinations of one wound over time.</p>
          <Link href="/cases/new" className={`${buttonVariants()} mt-4`}>Create the first case</Link>
        </div>
      ) : (
        <>
          <CasesTable rows={rows} />
          <p className="mt-2 text-13 text-ink-2">
            {models.length > 0 && (
              <>
                Area comes from model{models.length > 1 ? "s" : ""} <span className="value">{models.join(", ")}</span>.{" "}
              </>
            )}
            A refused photo has no value.
          </p>
        </>
      )}
    </>
  );
}
