import type { Metadata } from "next";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { UNREACHABLE, messageFor } from "@/lib/errors";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Service unavailable" };

// Shown in place of any page whose data could not be read. It never shows earlier or constructed values.
export default async function UnavailablePage({ searchParams }: { searchParams: Promise<{ category?: string; code?: string; from?: string }> }) {
  const params = await searchParams;
  const copy = params.category ? messageFor(params.category) : UNREACHABLE;
  const back = params.from?.startsWith("/") && !params.from.startsWith("//") ? params.from : "/cases";
  return (
    <div className="mx-auto max-w-xl px-4 py-14 sm:py-20">
      <h1 className="text-2xl text-failure">{copy.title}</h1>
      <p className="mt-3 max-w-[60ch]">{copy.body}</p>
      {params.code && (
        <p className="mt-2 text-13 text-ink-2">
          Code <span className="value text-ink">{params.code}</span>
        </p>
      )}
      <Link href={back} className={cn(buttonVariants({ size: "lg" }), "mt-6")}>Try again</Link>
    </div>
  );
}
