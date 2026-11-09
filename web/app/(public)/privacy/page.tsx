import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Photos and privacy" };

const STORED = [
  ["The photo", "A clean copy with location, camera and text details removed. The pixels the model reads are unchanged."],
  ["The results", "The mask, the probability map, the nine checks and the measurements."],
  ["Case records", "The label you give a case, capture dates and notes. No names are asked for."],
  ["Your account", "The identifier your sign-in provider sends, and when you gave consent."],
];

const SECTIONS: { title: string; body: React.ReactNode }[] = [
  {
    title: "Not for real patient photos",
    body: (
      <p>
        This is a research prototype. Use constructed or research images that you are allowed to share. The service cannot
        tell a real patient photo from any other, so keep names, faces, wristbands and record numbers out of the frame.
      </p>
    ),
  },
  {
    title: "How long photos are kept",
    body: (
      <>
        <p>
          Photos, results and uploads are deleted 24 hours after they are added. The operator can change the period, and
          the account page shows the one in force.
        </p>
        <p className="mt-3">
          To follow a wound over time, open the case and choose <span className="font-medium">Keep this case</span>. Kept
          cases stay until you delete them or clear the choice. If a deletion fails, it is tried again on the next run.
        </p>
      </>
    ),
  },
  {
    title: "Consent",
    body: (
      <p>
        Before your first upload you confirm that you may upload the photos for research use. The service records the
        time and the version of the text you accepted. If the text changes, you are asked again.
      </p>
    ),
  },
  {
    title: "Export and delete",
    body: (
      <p>
        The <Link href="/account" className="text-link">account page</Link> exports your cases, analyses and consent
        records as one file, and deletes your account with everything in it. A single case can be deleted from its own
        page.
      </p>
    ),
  },
  {
    title: "Limits on use",
    body: (
      <p>
        Each account and each network address can make a limited number of requests per minute. Past the limit the
        service asks you to wait and says for how long.
      </p>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <article className="mx-auto max-w-[760px] px-4 py-10 sm:px-6">
      <h1 className="text-2xl">Photos and privacy</h1>
      <p className="mt-3 max-w-[60ch] text-ink-2">
        What happens to a photo after you upload it, how long it stays, and how to remove it. This page describes the
        service; it is not legal advice and claims no regulatory approval.
      </p>

      <h2 className="mt-10 mb-3 text-xl">What is stored</h2>
      <dl className="panel max-w-[65ch] divide-y divide-rule text-sm">
        {STORED.map(([label, value]) => (
          <div key={label} className="grid gap-1 px-4 py-3 sm:grid-cols-[160px_1fr]">
            <dt className="font-medium">{label}</dt>
            <dd className="text-ink-2">{value}</dd>
          </div>
        ))}
      </dl>

      {SECTIONS.map((section) => (
        <section key={section.title} className="mt-10 max-w-[58ch]">
          <h2 className="mb-3 text-xl">{section.title}</h2>
          {section.body}
        </section>
      ))}
    </article>
  );
}
