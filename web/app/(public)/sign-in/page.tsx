import type { Metadata } from "next";
import Link from "next/link";

import { SignInButton } from "@/components/SignInButton";
import { buttonVariants } from "@/components/ui/button";
import { isMock } from "@/lib/api/mode";
import { providerConfigured } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Sign in" };

// Only a path on this site is accepted as the place to return to.
function safeReturn(value: string | undefined) {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/cases";
}

export default async function SignInPage({ searchParams }: { searchParams: Promise<{ callbackUrl?: string; error?: string }> }) {
  const params = await searchParams;
  const callbackUrl = safeReturn(params.callbackUrl);
  const expired = params.callbackUrl !== undefined && !params.error;
  return (
    <div className="mx-auto max-w-md px-4 py-14 sm:py-20">
      <h1 className="text-2xl">Sign in</h1>
      {isMock ? (
        <p className="mt-3 text-ink-2">This build serves constructed demonstration data only, so it needs no sign-in.</p>
      ) : providerConfigured ? (
        <p className="mt-3 text-ink-2">
          {expired ? "Your session has ended. Sign in again to carry on where you were. " : ""}
          Sign-in hands you to your organisation&apos;s provider and brings you back here.
        </p>
      ) : (
        <p className="mt-3 text-ink-2">No sign-in provider is configured for this deployment, so the working pages cannot be opened.</p>
      )}
      {params.error && (
        <p role="alert" className="mt-3 text-sm text-failure">Sign-in did not finish. Try again, or ask your administrator if it repeats.</p>
      )}
      <div className="mt-6 space-y-2">
        {isMock ? (
          <Link href="/cases" className={cn(buttonVariants({ size: "lg" }), "w-full")}>Open the constructed demonstration</Link>
        ) : providerConfigured ? (
          <SignInButton callbackUrl={callbackUrl} label="Continue with your provider" />
        ) : (
          <button type="button" disabled className={cn(buttonVariants({ size: "lg" }), "w-full")}>Continue with your provider</button>
        )}
      </div>
      {isMock && <p className="mt-4 text-13 text-ink-2">The demonstration holds no real records and uploads nothing.</p>}
    </div>
  );
}
