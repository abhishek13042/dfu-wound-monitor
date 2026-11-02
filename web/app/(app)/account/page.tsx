import type { Metadata } from "next";
import { Download } from "lucide-react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Account" };

const FACTS = [
  ["Signed in as", "Constructed demonstration user"],
  ["Sign-in provider", "Not chosen yet"],
  ["Photo retention", "Placeholder until a period is decided"],
];

export default function AccountPage() {
  return (
    <div className="max-w-2xl">
      <PageHeader title="Account" />
      <dl className="panel mb-6 divide-y divide-rule text-sm">
        {FACTS.map(([label, value]) => (
          <div key={label} className="grid gap-1 px-4 py-3 sm:grid-cols-[180px_1fr]">
            <dt className="text-ink-2">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <section className="border-t border-rule pt-4">
        <h2 className="text-lg">Export your data</h2>
        <p className="mt-1 mb-3 text-sm text-ink-2">Download your cases, examinations and analyses as one archive.</p>
        <Button variant="outline" disabled>
          <Download aria-hidden="true" />
          Export data
        </Button>
        <p className="mt-2 text-13 text-ink-2">Export needs the service connection.</p>
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
        />
      </section>
    </div>
  );
}
