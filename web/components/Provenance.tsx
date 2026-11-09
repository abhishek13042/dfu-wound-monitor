import { ChevronRight } from "lucide-react";

import type { Analysis } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";

export function Provenance({ analysis }: { analysis: Analysis }) {
  const rows = [
    ["Analysis", analysis.analysis_id],
    ["Captured", formatDate(analysis.captured_at)],
    ["Image", analysis.image ? `${analysis.image.width} × ${analysis.image.height} px` : "—"],
    ["SHA-256", analysis.image ? `${analysis.image.sha256.slice(0, 16)}…` : "—"],
    ["Model", analysis.model_version ?? "—"],
    ["Threshold", analysis.threshold === null ? "—" : analysis.threshold.toFixed(2)],
    ["Quality gate", analysis.quality.config_version ?? "—"],
  ];
  if (analysis.inference) rows.push(["Inference", `${formatNumber(analysis.inference.duration_ms / 1000)} s on ${analysis.inference.device}`]);
  return (
    <details className="panel group">
      <summary className="flex min-h-11 cursor-pointer items-center gap-2 px-4 text-sm font-semibold">
        <ChevronRight className="size-4 text-ink-2 group-open:rotate-90" aria-hidden="true" />
        Provenance
      </summary>
      <dl className="border-t border-rule px-4 py-2">
        {rows.map(([label, value]) => (
          <div key={label} className="grid grid-cols-[110px_minmax(0,1fr)] gap-2 py-1 text-13">
            <dt className="text-ink-2">{label}</dt>
            <dd className="value break-all">{value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
