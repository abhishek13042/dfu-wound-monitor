import type { Metadata } from "next";
import Link from "next/link";

import { ErrorPanel } from "@/components/ErrorPanel";
import { PageHeader } from "@/components/PageHeader";
import { UploadForm } from "@/components/UploadForm";
import { listCases, type ErrorCategory } from "@/lib/api";
import { errorCopy } from "@/lib/copy";

export const metadata: Metadata = { title: "New analysis" };

export default async function AnalysePage({ searchParams }: { searchParams: Promise<{ case?: string; error?: string }> }) {
  const params = await searchParams;
  const cases = await listCases();
  const category = params.error && params.error in errorCopy ? (params.error as ErrorCategory) : undefined;

  return (
    <>
      <PageHeader title="New analysis">The photo is read first. It is measured only if all nine checks pass.</PageHeader>
      {category && (
        <div className="mb-4 max-w-[920px]">
          <ErrorPanel category={category} requestId="req_constructed" />
        </div>
      )}
      <UploadForm cases={cases} initialCase={params.case} />
      <details className="mt-6 max-w-[920px] border-t border-rule pt-2 text-sm">
        <summary className="flex min-h-11 cursor-pointer items-center font-medium">Constructed service responses</summary>
        <ul className="grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(errorCopy).map(([code, copy]) => (
            <li key={code}>
              <Link href={`/analyse?error=${code}`} className="text-link flex min-h-9 items-center">
                <span className="value mr-2 text-13 text-ink-2">{copy.status.split(",")[0]}</span>
                {copy.title}
              </Link>
            </li>
          ))}
        </ul>
      </details>
    </>
  );
}
