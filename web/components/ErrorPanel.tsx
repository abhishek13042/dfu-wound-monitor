import Link from "next/link";
import type { ReactNode } from "react";
import { CircleAlert } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import type { ErrorCategory } from "@/lib/api";
import { errorCopy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const USER_SIDE: ErrorCategory[] = ["INVALID_INPUT", "UNAUTHENTICATED", "NOT_FOUND", "CONFLICT"];

interface Props {
  category: ErrorCategory;
  requestId?: string;
  details?: string;
  retryAfter?: number;
  action?: ReactNode;
}

export function ErrorPanel({ category, requestId, details, retryAfter, action }: Props) {
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
        {category === "BUSY" && retryAfter !== undefined && (
          <p className="mt-1 text-sm">The service asked for a pause of {retryAfter} seconds before the next attempt.</p>
        )}
        {action ? (
          <div className="mt-3">{action}</div>
        ) : category === "BUSY" ? (
          <button type="button" disabled className={cn(buttonVariants({ variant: "outline" }), "mt-3")}>{copy.action}</button>
        ) : (
          <Link href={copy.href} className={cn(buttonVariants({ variant: "outline" }), "mt-3")}>{copy.action}</Link>
        )}
      </div>
    </section>
  );
}
