import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { EvidenceTable } from "@/components/EvidenceTable";
import { KeyChart } from "@/components/KeyChart";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STAGES = [
  { name: "Read", body: "Nine checks run on the photo first. A failure stops the work and names the check that failed." },
  { name: "Segment", body: "An accepted photo goes through a ResNet34 U-Net at 512 by 512 pixels, with a threshold of 0.40." },
  { name: "Measure", body: "Area, perimeter and Feret diameters come from the mask, in pixels or in millimetres when you give a scale." },
  { name: "Compare", body: "Examinations of one case form a technical trend on a true time axis. Refused photos are listed, never hidden." },
];

export default function LandingPage() {
  return (
    <>
      <section className="on-aubergine bg-aubergine pb-10 text-rail-ink">
        <div className="mx-auto max-w-[1320px] px-4 sm:px-6">
          <div className="grid gap-6 pt-8 pb-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)] lg:items-end lg:pt-12">
            <h1 className="text-2xl sm:text-3xl sm:[font-stretch:75%]">A photo that fails the key gets no measurement.</h1>
            <div>
              <p className="text-base text-rail-muted">
                DFU-WoundMonitor reads each diabetic foot photo against nine printed checks. When one fails, you see which
                one and how to retake it.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  href="/sign-in"
                  className={cn(buttonVariants({ size: "lg" }), "bg-rail-ink text-aubergine hover:bg-white")}
                >
                  Sign in
                </Link>
                <Link
                  href="/model"
                  className={cn(buttonVariants({ size: "lg" }), "border-rail-muted bg-transparent text-rail-ink hover:bg-aubergine-2")}
                >
                  Model evidence
                  <ArrowRight aria-hidden="true" />
                </Link>
              </div>
            </div>
          </div>
          <KeyChart />
        </div>
      </section>

      <section aria-labelledby="stages" className="mx-auto max-w-[1320px] px-4 pt-14 sm:px-6">
        <h2 id="stages" className="text-xl">Measuring comes last</h2>
        <dl className="mt-4 border-t border-rule-strong">
          {STAGES.map((stage) => (
            <div key={stage.name} className="grid gap-1 border-b border-rule py-3 sm:grid-cols-[180px_minmax(0,70ch)] sm:gap-4">
              <dt className="font-semibold [font-stretch:85%]">{stage.name}</dt>
              <dd className="text-ink-2">{stage.body}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="evidence" className="mx-auto max-w-[1320px] px-4 pt-14 pb-16 sm:px-6">
        <h2 id="evidence" className="text-xl">Two results, read together</h2>
        <p className="mt-2 mb-4 max-w-[70ch] text-ink-2">
          The model does well on images like its training set and poorly on an external set. Why they differ is not settled:
          the annotation protocol is one hypothesis.
        </p>
        <EvidenceTable />
        <Link href="/model" className="text-link mt-2 inline-flex min-h-11 items-center text-sm font-medium">
          Read the full model card
        </Link>
      </section>
    </>
  );
}
