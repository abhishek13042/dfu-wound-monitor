import { Info } from "lucide-react";

export const TREND_NOTICE = "Image-derived technical trends, not a healing assessment.";

// Shown above every trend (REQ-P08-S03-004). The service's own label follows when it says more.
export function TrendNotice({ label }: { label?: string }) {
  const extra = label && label.trim().toLowerCase() !== TREND_NOTICE.toLowerCase() ? label : null;
  return (
    <div role="note" className="panel mb-4 flex max-w-[80ch] gap-3 px-4 py-3 text-sm">
      <Info className="mt-0.5 size-4 flex-none text-ink-2" aria-hidden="true" />
      <p>
        <span className="font-medium">{TREND_NOTICE}</span>
        {extra && <span className="block text-ink-2">{extra}</span>}
      </p>
    </div>
  );
}
