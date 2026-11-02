import Link from "next/link";
import { CircleAlert } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import type { ErrorCategory } from "@/lib/api";
import { errorCopy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const USER_SIDE: ErrorCategory[] = ["INVALID_INPUT", "UNAUTHENTICATED", "NOT_FOUND", "CONFLICT"];

export function ErrorPanel({ category, requestId, details }: { category: ErrorCategory; requestId?: string; details?: string }) {
  const copy = errorCopy[category];
  const refused = category === "QUALITY_REJECTED";
  const neutral = USER_SIDE.includes(category);
  return (
    <section
      role="alert"
      className={cn("panel flex gap-3 p-4", refused ? "border-reject bg-reject-wash" : neutral ? "border-rule-strong" : "border-failure bg-failure-wash")}
    >
      <CircleAlert className={cn("mt-1 size-5 flex-none", refused ? "text-reject" : neutral ? "text-ink" : "text-failure")} aria-hidden="true" />
      <div className="min-w-0">
        <h2 className="text-lg">{copy.title}</h2>
        <p className="mt-1 max-w-[70ch] text-sm">{copy.body}</p>
        {details && <p className="mt-1 text-sm">{details}</p>}
        {requestId && (
          <p className="mt-1 text-13 text-ink-2">
            Request ID <span className="value text-ink">{requestId}</span>
          </p>
        )}
        {category === "BUSY" ? (
          <button type="button" disabled className={cn(buttonVariants({ variant: "outline" }), "mt-3")}>{copy.action}</button>
        ) : (
          <Link href={copy.href} className={cn(buttonVariants({ variant: "outline" }), "mt-3")}>{copy.action}</Link>
        )}
      </div>
    </section>
  );
}
