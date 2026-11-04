import Link from "next/link";

import type { Trend } from "@/lib/api";
import { trendReasonCopy } from "@/lib/copy";
import { formatDate } from "@/lib/format";

// Every examination the service left out of the trend, with its reasons (REQ-P08-S03-002).
export function Exclusions({ excluded }: { excluded: Trend["excluded"] }) {
  if (excluded.length === 0) return null;
  return (
    <section aria-labelledby="excluded" className="panel px-4 py-3">
      <h2 id="excluded" className="text-lg">Left out of this trend</h2>
      <ul className="mt-1 text-sm">
        {excluded.map((entry) => (
          <li key={entry.examination_id} className="border-t border-rule py-2 first:border-t-0">
            <Link href={`/analyses/${entry.analysis_id}`} className="value font-semibold hover:underline">
              {entry.captured_at ? formatDate(entry.captured_at) : entry.examination_id}
            </Link>
            <span className="ml-2 text-ink-2">{entry.reason_codes.map((code) => trendReasonCopy[code] ?? code).join(" ")}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
