import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AnalysisPoller } from "@/components/AnalysisPoller";
import { ErrorPanel } from "@/components/ErrorPanel";
import { MaskOverlay } from "@/components/MaskOverlay";
import { Measurements } from "@/components/Measurements";
import { PageHeader } from "@/components/PageHeader";
import { Photo } from "@/components/Photo";
import { Provenance } from "@/components/Provenance";
import { ReadingStrip } from "@/components/ReadingStrip";
import { StateTag } from "@/components/StateTag";
import { Warnings } from "@/components/Warnings";
import { buttonVariants } from "@/components/ui/button";
import { getAnalysis, getArtifact, getCase } from "@/lib/api";
import { LIMITATION, reasonCopy, statusCopy } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { PADS } from "@/lib/pads";

export const metadata: Metadata = { title: "Analysis" };

export default async function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const analysis = await getAnalysis(id);
  if (!analysis) notFound();
  const item = analysis.case_id ? await getCase(analysis.case_id) : undefined;
  const copy = statusCopy[analysis.status];
  const pending = analysis.status === "QUEUED" || analysis.status === "RUNNING";
  const refused = analysis.status === "QUALITY_REJECTED";
  const completed = analysis.status === "COMPLETED";
  // Signed URLs exist only for stored records; constructed data has none and falls back to placeholders.
  const [image, mask] = await Promise.all([
    refused || completed ? getArtifact(analysis.analysis_id, "image") : undefined,
    completed ? getArtifact(analysis.analysis_id, "mask") : undefined,
  ]);
  const retake = analysis.case_id ? `/analyse?case=${analysis.case_id}` : "/analyse";
  const failedPads = PADS.filter((pad) => analysis.quality.reason_codes.includes(pad.reason));

  return (
    <>
      <AnalysisPoller active={pending} />
      {analysis.case_id && (
        <p className="mb-1 text-sm">
          <Link href={`/cases/${analysis.case_id}`} className="text-link text-ink-2">{item?.label ?? "Case"}</Link>
        </p>
      )}
      <PageHeader title={copy.title} actions={<StateTag status={analysis.status} className="text-base" />}>
        {analysis.filename && <span className="value text-sm">{analysis.filename}, </span>}
        <span className="text-sm">captured {formatDate(analysis.captured_at)}</span>
      </PageHeader>

      <section aria-label="Quality reading" className="panel mb-4 p-4">
        <ReadingStrip quality={analysis.quality} size="standard" animate={pending || refused} />
      </section>

      {pending && (
        <section className="panel p-5" aria-live="polite">
          <p className="max-w-[70ch]">{copy.body}</p>
          <p className="mt-2 text-13 text-ink-2">This page checks again every 2 seconds, and less often while the tab is hidden.</p>
        </section>
      )}

      {refused && (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,440px)]">
          <section aria-labelledby="why" className="panel border-reject bg-reject-wash p-5">
            <h2 id="why" className="text-lg">Why it was refused</h2>
            <p className="mt-1 text-sm">{copy.body}</p>
            <dl className="mt-3 divide-y divide-reject/30">
              {failedPads.map((pad) => (
                <div key={pad.key} className="py-2.5">
                  <dt className="font-semibold">{pad.name}. {reasonCopy[pad.reason].reason}</dt>
                  <dd className="text-sm">{reasonCopy[pad.reason].retake}</dd>
                </div>
              ))}
            </dl>
            <Link href={retake} className={`${buttonVariants()} mt-3`}>Retake and upload</Link>
          </section>
          <figure className="panel overflow-hidden">
            <Photo id={analysis.analysis_id} src={image?.url} className="block h-auto w-full" />
            <figcaption className="px-4 py-2 text-13 text-ink-2">No mask and no measurement exist for this photo.</figcaption>
          </figure>
        </div>
      )}

      {analysis.status === "FAILED" && analysis.failure && (
        <ErrorPanel
          category={analysis.failure.category}
          requestId={analysis.failure.request_id}
          details={
            analysis.failure.retry === undefined
              ? `The worker stopped before finishing (${analysis.failure.code}).`
              : `The worker stopped before finishing, after ${analysis.failure.retry} attempts (${analysis.failure.code}).`
          }
          action={<Link href={retake} className={buttonVariants({ variant: "outline" })}>Upload the photo again</Link>}
        />
      )}

      {completed && analysis.measurement && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,400px)]">
          <MaskOverlay
            id={analysis.analysis_id}
            areaShare={analysis.image ? analysis.measurement.pixel.area_px / (analysis.image.width * analysis.image.height) : 0.1}
            image={image?.url}
            mask={mask?.url}
          />
          <div className="space-y-4">
            <Warnings warnings={analysis.warnings} />
            <Measurements measurement={analysis.measurement} model={analysis.model_version ?? "unknown"} />
            <p className="text-13 text-ink-2">{analysis.limitation ?? LIMITATION}</p>
          </div>
        </div>
      )}

      <div className="mt-4">
        <Provenance analysis={analysis} />
      </div>
    </>
  );
}
