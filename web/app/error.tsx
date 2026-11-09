"use client";

import { MedicalNotice } from "@/components/MedicalNotice";
import { Button } from "@/components/ui/button";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <>
      <MedicalNotice constructed={false} />
      <main className="mx-auto max-w-xl px-4 py-20">
        <h1 className="text-2xl text-failure">This page could not load</h1>
        <p className="mt-2 text-ink-2">This is a fault on our side. Your saved records are unchanged.</p>
        {error.digest && (
          <p className="mt-1 text-13 text-ink-2">
            Request ID <span className="value text-ink">{error.digest}</span>
          </p>
        )}
        <Button className="mt-5" onClick={reset}>Try again</Button>
      </main>
    </>
  );
}
