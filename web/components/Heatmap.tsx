"use client";

import { useEffect, useRef } from "react";

import type { Uncertainty } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { outline, seedOf } from "@/lib/shape";

const SIZE = { width: 800, height: 600 };

interface LayerProps {
  id: string;
  areaShare: number;
  probability?: string;
  opacity: number;
}

// REQ-P09-S02-001: the stored probability map drawn in one hue, its alpha following the per-pixel score.
// Without a signed URL a soft constructed shape stands in, like the constructed mask beside it.
export function HeatmapLayer({ id, areaShare, probability, opacity }: LayerProps) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const target = canvas.current;
    const context = target?.getContext("2d");
    if (!target || !context) return;
    const hue = getComputedStyle(target).getPropertyValue("--series").trim();

    if (!probability) {
      target.width = SIZE.width;
      target.height = SIZE.height;
      const radius = Math.sqrt(areaShare) * SIZE.height;
      const points = outline(seedOf(id) + 11, 410, 300, radius * 1.15, radius * 0.87);
      context.clearRect(0, 0, SIZE.width, SIZE.height);
      context.filter = "blur(22px)";
      context.beginPath();
      points.forEach(([x, y], index) => (index === 0 ? context.moveTo(x, y) : context.lineTo(x, y)));
      context.closePath();
      context.fillStyle = hue;
      context.fill();
      context.filter = "none";
      return;
    }

    let live = true;
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      if (!live) return;
      target.width = image.naturalWidth;
      target.height = image.naturalHeight;
      context.drawImage(image, 0, 0);
      const pixels = context.getImageData(0, 0, target.width, target.height);
      context.fillStyle = hue;
      context.fillRect(0, 0, 1, 1);
      const [r, g, b] = context.getImageData(0, 0, 1, 1).data;
      const data = pixels.data;
      for (let index = 0; index < data.length; index += 4) {
        const score = data[index];   // grayscale: red carries the score, 0..255
        data[index] = r;
        data[index + 1] = g;
        data[index + 2] = b;
        data[index + 3] = score;
      }
      context.putImageData(pixels, 0, 0);
    };
    image.src = probability;
    return () => {
      live = false;
    };
  }, [id, areaShare, probability]);

  return (
    <canvas
      ref={canvas}
      {...SIZE}
      aria-hidden="true"
      style={{ opacity: opacity / 100 }}
      className="pointer-events-none absolute inset-0 size-full"
    />
  );
}

export function HeatmapLegend() {
  return (
    <div className="flex items-center gap-2 text-13 text-ink-2">
      <span>Model score per pixel</span>
      <span className="value">0</span>
      <span aria-hidden="true" className="h-2 w-24 rounded-sm border border-rule bg-[linear-gradient(to_right,transparent,var(--series))]" />
      <span className="value">1</span>
    </div>
  );
}

// REQ-P09-S02-004: named as model uncertainty, and never worded as how sure the model is of the outline.
export function UncertaintyPanel({ uncertainty }: { uncertainty?: Uncertainty | null }) {
  if (!uncertainty || !uncertainty.summary_shown) return null;
  return (
    <section aria-labelledby="uncertainty" className="panel p-4">
      <h2 id="uncertainty" className="text-lg">Model uncertainty</h2>
      <p className="mt-1">
        Flipped-view disagreement <span className="value">{formatNumber(uncertainty.tta_disagreement, 3)}</span>
        <span className="text-13 text-ink-2"> on a scale of 0 to 1</span>
      </p>
      <p className="mt-1 max-w-[60ch] text-13 text-ink-2">
        How much the model&apos;s answer changes when the photo is mirrored, measured
        {uncertainty.region === "MASK_AND_BAND" ? " inside the outline and a narrow band around it" : " over the whole photo"}.
        On validation photos, higher values went with less accurate outlines. It is not the chance that the outline is correct.
      </p>
    </section>
  );
}
