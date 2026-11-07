import Link from "next/link";

import { MedicalNotice } from "@/components/MedicalNotice";
import { Wordmark } from "@/components/Wordmark";
import { LIMITATION, NOTICE } from "@/lib/copy";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <MedicalNotice constructed={false} />
      <header className="on-aubergine bg-aubergine text-rail-ink">
        <div className="mx-auto flex h-14 max-w-[1320px] items-center justify-between gap-4 px-4 sm:px-6">
          <Wordmark />
          <nav aria-label="Main" className="flex items-center text-sm font-medium whitespace-nowrap sm:gap-1">
            <Link href="/model" className="flex h-11 items-center px-2 hover:underline sm:px-3">
              Model<span className="max-sm:hidden">&nbsp;evidence</span>
            </Link>
            <Link href="/sign-in" className="flex h-11 items-center px-2 hover:underline sm:px-3">
              Sign in
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-rule">
        <div className="mx-auto flex max-w-[1320px] flex-col gap-1 px-4 py-6 text-13 text-ink-2 sm:px-6">
          <p className="font-medium text-ink">{NOTICE}</p>
          <p className="max-w-[65ch]">{LIMITATION}</p>
          <p>
            <Link href="/privacy" className="text-link text-ink-2">Photos and privacy</Link>
          </p>
        </div>
      </footer>
    </div>
  );
}
