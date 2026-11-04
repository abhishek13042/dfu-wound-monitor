import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Exclusions } from "@/components/Exclusions";
import { PageHeader } from "@/components/PageHeader";
import { TrendNotice } from "@/components/TrendNotice";
import { TrendChart } from "@/components/TrendChart";
import { Warnings } from "@/components/Warnings";
import { buttonVariants } from "@/components/ui/button";
import { getCase, getTrend } from "@/lib/api";
import { basisCopy, trendReasonCopy } from "@/lib/copy";
import { formatDate, formatNumber, signed } from "@/lib/format";

export const metadata: Metadata = { title: "Trend" };

export default async function TrendPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const item = await getCase(id);
  if (!item) notFound();
  const trend = await getTrend(id);
  if (!trend) notFound();
  const digits = trend.basis === "PHYSICALLY_CALIBRATED" ? 1 : 0;
  // Every figure below is the service's own; the browser only formats it (REQ-P08-S03-001).
  const change = (value: { absolute_change: number; percent_change: number | null } | null) =>
    value ? `${signed(value.absolute_change, digits)}${value.percent_change === null ? "" : ` (${signed(value.percent_change)}%)`}` : "None";
  const day = (value: number) => formatNumber(value, Number.isInteger(value) ? 0 : 1);
  const plotted = trend.status === "AVAILABLE" && trend.rows.length >= 2;

  return (
    <>
      <p className="mb-1 text-sm">
        <Link href={`/cases/${id}`} className="text-link text-ink-2">{item.label ?? item.case_id}</Link>
      </p>
      <PageHeader title="Trend" />

      <TrendNotice label={trend.label} />

      {!plotted ? (
        <section className="panel px-6 py-10">
          <h2 className="text-lg">No trend for this case</h2>
          <ul className="mt-2 text-ink-2">
            {trend.rows.length < 2 && (
              <li>
                {trend.rows.length === 0 ? "No examination" : "Only one examination"} has a usable measurement. A trend needs at least two.
              </li>
            )}
            {trend.reason_codes
              .filter((code) => !(trend.rows.length < 2 && code === "INSUFFICIENT_POINTS"))
              .map((code) => (
                <li key={code}>{trendReasonCopy[code] ?? code}</li>
              ))}
          </ul>
          <Link href={`/analyse?case=${id}`} className={`${buttonVariants()} mt-4`}>Add a photo</Link>
        </section>
      ) : (
        <div className="space-y-4">
          <Warnings warnings={trend.warnings} />

          <section aria-labelledby="chart" className="panel p-4">
            <h2 id="chart" className="text-lg">Area of the segmented region</h2>
            <p className="mb-2 text-13 text-ink-2">
              {basisCopy[trend.basis!].long}. Spacing on the time axis follows the real intervals.
            </p>
            <TrendChart trend={trend} />
          </section>

          <section aria-labelledby="values" className="panel overflow-hidden">
            <h2 id="values" className="px-4 pt-3 pb-2 text-lg">Values</h2>
            <table className="stack-table w-full border-collapse text-sm">
              <caption className="sr-only">Trend values by examination</caption>
              <thead>
                <tr className="h-10 border-y border-rule text-left text-13 text-ink-2">
                  <th scope="col" className="px-4 font-medium">Captured</th>
                  <th scope="col" className="px-4 text-right font-medium">Day</th>
                  <th scope="col" className="px-4 text-right font-medium">Area ({trend.unit.area})</th>
                  <th scope="col" className="px-4 text-right font-medium">From baseline</th>
                  <th scope="col" className="px-4 text-right font-medium">From previous</th>
                </tr>
              </thead>
              <tbody className="value">
                {trend.rows.map((row) => (
                  <tr key={row.examination_id} className="border-b border-rule last:border-b-0 sm:h-11">
                    <td data-wide className="px-4">
                      <Link href={`/analyses/${row.analysis_id}`} className="font-semibold hover:underline">{formatDate(row.captured_at)}</Link>
                      {row.is_baseline && <span className="ml-2 font-sans text-13 text-ink-2">Baseline</span>}
                    </td>
                    <td data-label="Day" className="px-4 sm:text-right">{day(row.days_since_baseline)}</td>
                    <td data-label={`Area (${trend.unit.area})`} className="px-4 sm:text-right">{formatNumber(row.values.area, digits)}</td>
                    <td data-label="From baseline" className="px-4 sm:text-right">{change(row.from_baseline)}</td>
                    <td data-label="From previous" className="px-4 sm:text-right">{change(row.from_previous)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}

      <div className="mt-4 space-y-4">
        <Exclusions excluded={trend.excluded} />
        {plotted && (
          <p className="text-13 text-ink-2">
            Trend method <span className="value">{trend.version}</span>. Values come from the service, never from the browser.
          </p>
        )}
      </div>
    </>
  );
}
