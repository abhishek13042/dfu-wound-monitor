import { TriangleAlert } from "lucide-react";

import type { Warning } from "@/lib/api";

export function Warnings({ warnings }: { warnings: Warning[] }) {
  if (warnings.length === 0) return null;
  return (
    <ul className="space-y-1">
      {warnings.map((warning) => (
        <li key={warning.code} className="flex gap-2 border border-warn bg-warn-wash px-3 py-2 text-sm">
          <TriangleAlert className="mt-0.5 size-4 flex-none text-warn-ink" aria-hidden="true" />
          {warning.message}
        </li>
      ))}
    </ul>
  );
}
