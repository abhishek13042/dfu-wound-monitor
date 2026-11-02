import type { Metadata } from "next";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-14 sm:py-20">
      <h1 className="text-2xl">Sign in</h1>
      <p className="mt-3 text-ink-2">
        Sign-in hands you to your organisation&apos;s provider. No provider is connected to this build yet, so you can only
        open the constructed demonstration.
      </p>
      <div className="mt-6 space-y-2">
        <button type="button" disabled className={cn(buttonVariants({ size: "lg" }), "w-full")}>
          Continue with your provider
        </button>
        <Link href="/cases" className={cn(buttonVariants({ size: "lg", variant: "outline" }), "w-full")}>
          Open the constructed demonstration
        </Link>
      </div>
      <p className="mt-4 text-13 text-ink-2">The demonstration holds no real records and uploads nothing.</p>
    </div>
  );
}
