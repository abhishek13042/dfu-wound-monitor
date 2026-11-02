import { AlertOctagon, Clock, Loader, type LucideIcon } from "lucide-react";

import { PadMark } from "@/components/ReadingStrip";
import type { AnalysisStatus } from "@/lib/api";
import { statusCopy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const ICON: Partial<Record<AnalysisStatus, { icon: LucideIcon; tone: string }>> = {
  QUEUED: { icon: Clock, tone: "text-ink-2" },
  RUNNING: { icon: Loader, tone: "text-series" },
  FAILED: { icon: AlertOctagon, tone: "text-failure" },
};

export function StateTag({ status, className }: { status: AnalysisStatus; className?: string }) {
  const entry = ICON[status];
  if (entry) {
    const Icon = entry.icon;
    return (
      <span className={cn("inline-flex items-center gap-1.5 text-sm font-medium", entry.tone, className)}>
        <Icon className="size-4" aria-hidden="true" />
        {statusCopy[status].short}
      </span>
    );
  }
  const passed = status === "COMPLETED";
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-sm font-medium", passed ? "text-pass" : "text-reject", className)}>
      <span data-state={passed ? "pass" : "fail"} className="pad size-4">
        <PadMark state={passed ? "pass" : "fail"} className="size-3" />
      </span>
      {statusCopy[status].short}
    </span>
  );
}
