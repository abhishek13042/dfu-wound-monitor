import type { Metadata } from "next";
import Link from "next/link";
import { getServerSession } from "next-auth";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ExportButton } from "@/components/ExportButton";
import { PageHeader } from "@/components/PageHeader";
import { getConsent, isMock } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { authOptions } from "@/lib/auth";

export const metadata: Metadata = { title: "Account" };

export default async function AccountPage() {
  const session = isMock ? null : await getServerSession(authOptions);
  const user = session?.user;
  const consent = await getConsent();
  const facts = [
    ["Signed in as", isMock ? "Constructed demonstration user" : (user?.email ?? user?.name ?? "Signed in")],
    ["Sign-in provider", isMock ? "None in this demonstration" : (process.env.AUTH_OIDC_NAME ?? "Organisation sign-in")],
    ["Photo retention", consent.retention_hours > 0 ? `${consent.retention_hours} hours, unless a case is kept` : "Off on this service"],
    ["Upload consent", consent.accepted_at ? `Given on ${formatDate(consent.accepted_at)}, text ${consent.text_version}` : "Not given yet. It is asked before the first upload."],
  ];

  return (
    <div className="max-w-2xl">
      <PageHeader title="Account" />
      <dl className="panel mb-6 divide-y divide-rule text-sm">
        {facts.map(([label, value]) => (
          <div key={label} className="grid gap-1 px-4 py-3 sm:grid-cols-[180px_1fr]">
            <dt className="text-ink-2">{label}</dt>
            <dd className="break-words">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="-mt-3 mb-6 text-sm">
        <Link href="/privacy" className="text-link">How photos and data are handled</Link>
      </p>

      <section className="border-t border-rule pt-4">
        <h2 className="text-lg">Export your data</h2>
        <p className="mt-1 mb-3 text-sm text-ink-2">Download your cases, examinations and analyses as one file.</p>
        <ExportButton />
      </section>

      <section className="mt-8 border-t border-rule pt-4">
        <h2 className="text-lg">Delete your account</h2>
        <p className="mt-1 mb-3 text-sm text-ink-2">Removes your account, cases and photos. This cannot be undone.</p>
        <ConfirmDialog
          action="Delete account"
          title="Delete your account?"
          body="Your account, cases, examinations and photos will be removed. This cannot be undone."
          word="delete"
          redirect="/"
          endpoint="/account"
          endSession
        />
      </section>
    </div>
  );
}
