import { cn } from "@/lib/utils";
import { failedNames, PADS, padStates, type PadState } from "@/lib/pads";
import type { Analysis } from "@/lib/api";

export function PadMark({ state, className }: { state: PadState; className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" className={className} aria-hidden="true">
      {state === "pass" && <path d="M3.5 8.5 6.5 11.5 12.5 4.5" />}
      {state === "fail" && <path d="M4 4 12 12M12 4 4 12" />}
      {state === "none" && <path d="M5 8h6" />}
    </svg>
  );
}

function summary(states: PadState[]): string {
  if (states.every((state) => state === "none")) return "Quality reading: not read yet.";
  const passed = states.filter((state) => state === "pass").length;
  const failed = failedNames(states);
  const unread = states.filter((state) => state === "none").length;
  const parts = [`${passed} of 9 checks passed`];
  if (failed.length) parts.push(`failed: ${failed.join(", ")}`);
  if (unread) parts.push(`${unread} not read`);
  return `Quality reading: ${parts.join("; ")}.`;
}

interface StripProps {
  quality?: Analysis["quality"];
  states?: PadState[];
  size?: "compact" | "standard";
  animate?: boolean;
  className?: string;
}

// Compact sits in table rows. Standard carries each pad's name. The key size lives in KeyChart.
export function ReadingStrip({ quality, states, size = "compact", animate = false, className }: StripProps) {
  const resolved = states ?? padStates(quality);
  const failed = failedNames(resolved);

  if (size === "compact") {
    return (
      <div className={cn("flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1", className)}>
        <div role="img" aria-label={summary(resolved)} className="flex gap-0.5">
          {resolved.map((state, index) => (
            <span key={PADS[index].key} data-state={state} title={PADS[index].name} className="pad size-4">
              <PadMark state={state} className="size-3" />
            </span>
          ))}
        </div>
        {failed.length > 0 && <span className="text-13 text-reject">{failed.join(", ")}</span>}
      </div>
    );
  }

  return (
    <ol aria-label={summary(resolved)} className={cn("grid grid-cols-3 gap-x-2 gap-y-3 sm:grid-cols-9 sm:gap-x-1", className)}>
      {resolved.map((state, index) => (
        <li key={PADS[index].key} className="flex min-w-0 items-center gap-2 sm:flex-col sm:items-start sm:gap-1">
          <span
            data-state={state}
            data-step={animate ? "" : undefined}
            style={animate ? ({ "--step": index } as React.CSSProperties) : undefined}
            className="pad size-7 sm:size-9"
          >
            <PadMark state={state} className="size-4" />
          </span>
          <span className={cn("truncate text-xs [font-stretch:80%]", state === "fail" && "font-semibold text-reject")}>
            {PADS[index].short}
            <span className="sr-only">: {state === "pass" ? "passed" : state === "fail" ? "failed" : "not read"}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
