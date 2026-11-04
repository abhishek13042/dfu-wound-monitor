import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ImageUp, LineChart } from "lucide-react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { ReadingStrip } from "@/components/ReadingStrip";
import { StateTag } from "@/components/StateTag";
import { buttonVariants } from "@/components/ui/button";
import { getAnalysis, getCase } from "@/lib/api";
import { basisCopy, identityCopy, timestampCopy } from "@/lib/copy";
import { areaOf, formatDate } from "@/lib/format";

export const metadata: Metadata = { title: "Case" };

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const item = await getCase(id);
  if (!item) notFound();
  const rows = await Promise.all(
    item.examinations.map(async (exam) => ({ exam, analysis: exam.analysis_id ? await getAnalysis(exam.analysis_id) : undefined })),
  );
  const facts: [string, React.ReactNode][] = [
    ["Case ID", <span key="id" className="value">{item.case_id}</span>],
    ["Identity", identityCopy[item.identity_status]],
    ["External reference", item.external_reference ?? "None"],
    ["Data source", item.data_source],
  ];

  return (
    <>
      <p className="mb-1 text-sm">
        <Link href="/cases" className="text-link text-ink-2">Cases</Link>
      </p>
      <PageHeader
        title={item.label ?? item.case_id}
        actions={
          <>
            <Link href={`/analyse?case=${item.case_id}`} className={buttonVariants()}>
              <ImageUp aria-hidden="true" />
              New analysis
            </Link>
            <Link href={`/cases/${item.case_id}/trend`} className={buttonVariants({ variant: "outline" })}>
              <LineChart aria-hidden="true" />
              Trend
            </Link>
          </>
        }
      />

      <dl className="mb-6 grid grid-cols-2 gap-x-6 gap-y-2 border-y border-rule py-3 text-sm sm:grid-cols-4">
        {facts.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-13 text-ink-2">{label}</dt>
            <dd className="break-words">{value}</dd>
          </div>
        ))}
      </dl>

      <h2 className="mb-2 text-lg">Examinations</h2>
      {rows.length === 0 ? (
        <div className="panel px-6 py-10 text-center">
          <p className="text-ink-2">No examinations yet. A trend needs at least two measured examinations.</p>
          <Link href={`/analyse?case=${item.case_id}`} className={`${buttonVariants()} mt-3`}>Add the first photo</Link>
        </div>
      ) : (
        <div className="panel overflow-hidden">
          <table className="stack-table w-full border-collapse text-sm">
            <caption className="sr-only">Examinations in time order</caption>
            <thead>
              <tr className="h-10 border-b border-rule text-left text-13 text-ink-2">
                <th scope="col" className="px-3 font-medium">Captured</th>
                <th scope="col" className="px-3 font-medium">Time source</th>
                <th scope="col" className="px-3 font-medium">Reading</th>
                <th scope="col" className="px-3 font-medium">Area</th>
                <th scope="col" className="px-3 font-medium">Basis</th>
                <th scope="col" className="px-3 font-medium">State</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ exam, analysis }) => {
                const area = analysis?.measurement ? areaOf(analysis.measurement) : null;
                return (
                  <tr key={exam.examination_id} className="border-b border-rule last:border-b-0 sm:h-11 hover:bg-secondary">
                    <td data-wide className="px-3 py-1.5">
                      {exam.analysis_id ? (
                        <Link href={`/analyses/${exam.analysis_id}`} className="value font-semibold hover:underline">{formatDate(exam.captured_at)}</Link>
                      ) : (
                        <span className="value font-semibold">{formatDate(exam.captured_at)}</span>
                      )}
                      {exam.notes && <span className="block max-w-[32ch] text-13 text-ink-2">{exam.notes}</span>}
                    </td>
                    <td data-label="Time source" className="px-3 text-13">{timestampCopy[exam.timestamp_source]}</td>
                    <td data-wide className="px-3 py-1.5"><ReadingStrip quality={analysis?.quality} /></td>
                    <td data-label="Area" className="px-3">
                      {area ? <span className="value">{area.value} <span className="text-13 text-ink-2">{area.unit}</span></span> : <span className="text-13 text-ink-2">No value</span>}
                    </td>
                    <td data-label="Basis" className="px-3 text-13">{analysis?.measurement ? basisCopy[analysis.measurement.measurement_basis].short : "None"}</td>
                    <td data-label="State" className="px-3">{analysis && <StateTag status={analysis.status} />}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-10 border-t border-rule pt-4">
        <h2 className="text-lg">Delete this case</h2>
        <p className="mt-1 mb-3 max-w-[70ch] text-sm text-ink-2">Removes the case, its examinations, photos and analyses. This cannot be undone.</p>
        <ConfirmDialog
          action="Delete case"
          title="Delete this case?"
          body="The case, its examinations, photos and analyses will be removed. This cannot be undone."
          word={item.case_id}
          redirect="/cases"
          endpoint={`/cases/${item.case_id}`}
        />
      </div>
    </>
  );
}
