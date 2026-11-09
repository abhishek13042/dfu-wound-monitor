"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

export function SignInButton({ callbackUrl, label }: { callbackUrl: string; label: string }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button
      size="lg"
      className="w-full"
      disabled={busy}
      onClick={() => {
        setBusy(true);
        void signIn("oidc", { callbackUrl });
      }}
    >
      {busy ? "Opening your provider…" : label}
    </Button>
  );
}
