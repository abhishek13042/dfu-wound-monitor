import Link from "next/link";

import { MedicalNotice } from "@/components/MedicalNotice";
import { ReadingStrip } from "@/components/ReadingStrip";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <>
      <MedicalNotice constructed={false} />
      <main className="mx-auto max-w-xl px-4 py-20">
        <ReadingStrip />
        <h1 className="mt-4 text-2xl">No such page</h1>
        <p className="mt-2 text-ink-2">The link may be wrong, or the record may have been deleted.</p>
        <Link href="/" className={`${buttonVariants()} mt-5`}>Back to the start</Link>
      </main>
    </>
  );
}
