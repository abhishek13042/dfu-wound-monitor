import type { Metadata } from "next";

import { EvidenceTable } from "@/components/EvidenceTable";

export const metadata: Metadata = { title: "Model evidence" };

const FACTS = [
  ["Version", "spec-02-03-resnet34-unet-512-v1"],
  ["Architecture", "ResNet34 U-Net"],
  ["Input", "512 × 512 px"],
  ["Threshold", "0.40"],
  ["Small regions", "Below 128 px removed"],
  ["Augmentation at test", "Horizontal flip"],
  ["Weights", "EMA, epoch 71"],
  ["CPU time", "About 5.8 s per image, 2 cores"],
];

const OUTCOMES = [
  ["Well segmented", "156"],
  ["Missed entirely", "8"],
  ["Under-segmented", "10"],
  ["Over-segmented", "6"],
  ["Low overlap", "6"],
  ["False positive on an empty image", "3"],
];

const LIMITS = [
  ["FUSeg-style masks", "16", "0.82"],
  ["Coarser native masks", "132", "0.20"],
];

export default function ModelPage() {
  return (
    <div className="mx-auto grid max-w-[1320px] gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <article className="min-w-0">
        <h1 className="text-2xl">Model evidence</h1>
        <p className="mt-3 max-w-[60ch] text-ink-2">
          What the segmentation model was tested on, how it did, and where it does poorly. No outcome for any person is
          claimed.
        </p>

        <h2 className="mt-10 mb-3 text-xl">Pooled Dice on both sets</h2>
        <EvidenceTable />
        <p className="mt-3 max-w-[60ch] text-sm text-ink-2">
          Macro Dice on FUSeg2021 is 0.84. Pooled Dice weights every pixel, so large regions carry more of the score.
        </p>

        <h2 className="mt-10 mb-3 text-xl">Where the 191 test images went</h2>
        <table className="w-full max-w-lg border-collapse text-sm">
          <caption className="sr-only">Outcome groups on the FUSeg2021 test set</caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">Outcome</th>
              <th scope="col">Images</th>
            </tr>
          </thead>
          <tbody>
            {OUTCOMES.map(([label, count]) => (
              <tr key={label} className="border-b border-rule">
                <th scope="row" className="py-2 text-left font-normal">{label}</th>
                <td className="value py-2 text-right">{count}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h2 className="mt-10 mb-3 text-xl">Why the external result is low</h2>
        <p className="max-w-[60ch] text-ink-2">
          On LowerLimb V3 the model is precise but finds little of the marked area: precision 0.90, recall 0.15. Dice splits
          sharply by mask style. This points to the annotation protocol, but that remains a hypothesis and has not been tested.
        </p>
        <table className="mt-3 w-full max-w-lg border-collapse text-sm">
          <caption className="sr-only">Pooled Dice on LowerLimb V3 by mask style</caption>
          <thead>
            <tr className="border-b border-rule-strong text-left text-13 text-ink-2">
              <th scope="col" className="py-2 font-normal">Mask style</th>
              <th scope="col" className="py-2 text-right font-normal">Images</th>
              <th scope="col" className="py-2 text-right font-normal">Pooled Dice</th>
            </tr>
          </thead>
          <tbody>
            {LIMITS.map(([label, count, dice]) => (
              <tr key={label} className="border-b border-rule">
                <th scope="row" className="py-2 text-left font-normal">{label}</th>
                <td className="value py-2 text-right">{count}</td>
                <td className="value py-2 text-right">{dice}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h2 className="mt-10 mb-3 text-xl">What this model cannot tell you</h2>
        <ul className="max-w-[70ch] list-disc space-y-1 pl-5 text-ink-2">
          <li>Whether a region is a wound, or what kind of wound it is.</li>
          <li>Anything about depth, infection or tissue type.</li>
          <li>A size in millimetres, unless you supply a scale.</li>
          <li>How it performs on people or cameras outside these two datasets.</li>
        </ul>
      </article>

      <aside className="lg:sticky lg:top-12 lg:self-start">
        <h2 className="mb-2 text-lg">Model facts</h2>
        <dl className="panel divide-y divide-rule text-sm">
          {FACTS.map(([label, value]) => (
            <div key={label} className="px-3 py-2">
              <dt className="text-13 text-ink-2">{label}</dt>
              <dd className="value break-words text-13">{value}</dd>
            </div>
          ))}
        </dl>
      </aside>
    </div>
  );
}
