import type { Metadata } from "next";
import Link from "next/link";

import { CompareSlider } from "@/components/CompareSlider";
import { PageHeader } from "@/components/PageHeader";
import { Warnings } from "@/components/Warnings";
import { buttonVariants } from "@/components/ui/button";
import { getArtifact, getComparison, isMock, listAnalyses } from "@/lib/api";
import { basisCopy, trendReasonCopy } from "@/lib/copy";
import { formatDate, formatNumber, signed } from "@/lib/format";

export const metadata: Metadata = { title: "Compare" };

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ a?: string; b?: string }> }) {
  const params = await searchParams;
  const options = (await listAnalyses()).filter((item) => item.status === "COMPLETED");
  const a = params.a ?? (isMock ? "a1d04e" : options[0]?.analysis_id);
  const b = params.b ?? (isMock ? "a1d093" : options[1]?.analysis_id);
  // The service decides whether two analyses can be compared (REQ-P08-S03-005); the page only reports its answer.
  const comparison = a && b && a !== b ? await getComparison(a, b) : undefined;
  const [earlierImage, laterImage] =
    comparison?.status === "AVAILABLE"
      ? await Promise.all([getArtifact(comparison.earlier.analysis_id, "image"), getArtifact(comparison.later.analysis_id, "image")])
      : [];
  const pickers = [
    ["a", "First analysis", a],
    ["b", "Second analysis", b],
  ];

  if (options.length < 2) {
    return (
      <>
        <PageHeader title="Compare two analyses" />
        <p className="panel px-5 py-8 text-ink-2">A comparison needs two completed analyses. Analyse another photo first.</p>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Compare two analyses" />
      <form className="panel mb-4 grid gap-3 p-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        {pickers.map(([name, label, value]) => (
          <div key={name}>
            <label htmlFor={name} className="text-sm font-medium">{label}</label>
            <select id={name} name={name} defaultValue={value} className="field mt-1">
              {options.map((item) => (
                <option key={item.analysis_id} value={item.analysis_id}>
                  {item.case_id ?? "No case"}, {formatDate(item.captured_at)}
                </option>
              ))}
            </select>
          </div>
        ))}
        <button type="submit" className={buttonVariants({ size: "lg" })}>Compare</button>
      </form>

      {!comparison ? (
        <p className="panel px-5 py-8 text-ink-2">{a && a === b ? "Choose two different analyses." : "Choose two analyses to compare."}</p>
      ) : comparison.status !== "AVAILABLE" ? (
        <section className="panel space-y-3 p-5">
          <h2 className="text-lg">These two cannot be compared</h2>
          <ul className="text-ink-2">
            {comparison.reason_codes.map((code) => (
              <li key={code}>{trendReasonCopy[code] ?? code}</li>
            ))}
          </ul>
          <Warnings warnings={comparison.warnings} />
        </section>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,440px)]">
          <div className="space-y-2">
            <CompareSlider
              earlier={comparison.earlier.analysis_id}
              later={comparison.later.analysis_id}
              earlierSrc={earlierImage?.url}
              laterSrc={laterImage?.url}
              earlierLabel={formatDate(comparison.earlier.captured_at)}
              laterLabel={formatDate(comparison.later.captured_at)}
            />
            <p className="text-13 text-ink-2">{comparison.label}</p>
          </div>
          <div className="space-y-4">
            <Warnings warnings={comparison.warnings} />
            <section aria-labelledby="change" className="panel overflow-hidden">
              <h2 id="change" className="px-4 pt-3 text-lg">
                {comparison.interval_days === null ? "Change" : `Change over ${formatNumber(comparison.interval_days, 0)} days`}
              </h2>
              {comparison.basis && <p className="px-4 pb-2 text-13 text-ink-2">{basisCopy[comparison.basis].long}</p>}
              <table className="w-full border-collapse text-sm">
                <caption className="sr-only">Measured values for both analyses</caption>
                <thead>
                  <tr className="h-9 border-y border-rule text-right text-13 text-ink-2">
                    <th scope="col" className="px-4 text-left font-medium">Measure</th>
                    <th scope="col" className="px-2 font-medium">Earlier</th>
                    <th scope="col" className="px-2 font-medium">Later</th>
                    <th scope="col" className="px-4 font-medium">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.metrics.map((metric) => (
                    <tr key={metric.name} className="h-11 border-b border-rule last:border-b-0">
                      <th scope="row" className="px-4 text-left font-normal">
                        {metric.name} <span className="value text-xs text-ink-2">{metric.unit}</span>
                      </th>
                      <td className="value px-2 text-right">{formatNumber(metric.earlier)}</td>
                      <td className="value px-2 text-right">{formatNumber(metric.later)}</td>
                      <td className="value px-4 text-right">{metric.percent_change === null ? "—" : `${signed(metric.percent_change)}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <p className="text-13 text-ink-2">
              Model <span className="value">{comparison.later.model_version ?? "unknown"}</span>.
              {isMock && (
                <>
                  {" "}
                  <Link href="/compare?a=a1d04e&b=b2e011" className="text-link">See a pair that cannot be compared</Link>
                </>
              )}
            </p>
          </div>
        </div>
      )}
    </>
  );
}
