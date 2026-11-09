"use client";

import { useEffect, useId, useRef, useState } from "react";

import { HeatmapLayer, HeatmapLegend } from "@/components/Heatmap";
import { Photo } from "@/components/Photo";
import { outline, seedOf } from "@/lib/shape";

const SIZE = { width: 800, height: 600 };

interface Props {
  id: string;
  areaShare: number;
  image?: string;
  mask?: string;
  probability?: string;
}

const VIEWS = [
  ["mask", "Outline"],
  ["heatmap", "Heatmap"],
] as const;

// With signed URLs the stored mask is drawn over the stored photo; without them a constructed outline stands in.
export function MaskOverlay({ id, areaShare, image, mask, probability }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const control = useId();
  const [opacity, setOpacity] = useState(55);
  const [view, setView] = useState<(typeof VIEWS)[number][0]>("mask");

  useEffect(() => {
    if (mask || view !== "mask") return;
    const context = canvas.current?.getContext("2d");
    if (!context || !canvas.current) return;
    const styles = getComputedStyle(canvas.current);
    const radius = Math.sqrt(areaShare) * SIZE.height;
    const points = outline(seedOf(id) + 11, 410, 300, radius * 1.15, radius * 0.87);
    context.clearRect(0, 0, SIZE.width, SIZE.height);
    context.beginPath();
    points.forEach(([x, y], index) => (index === 0 ? context.moveTo(x, y) : context.lineTo(x, y)));
    context.closePath();
    context.fillStyle = styles.getPropertyValue("--series");
    context.fill();
  }, [id, areaShare, mask, view]);

  return (
    <figure className="panel overflow-hidden">
      <div className="relative">
        <Photo id={id} src={image} className="block h-auto w-full" />
        {view === "heatmap" ? (
          <HeatmapLayer id={id} areaShare={areaShare} probability={probability} opacity={opacity} />
        ) : mask ? (
          <div
            aria-hidden="true"
            style={{
              opacity: opacity / 100,
              maskImage: `url(${mask})`,
              WebkitMaskImage: `url(${mask})`,
              maskSize: "100% 100%",
              WebkitMaskSize: "100% 100%",
              maskMode: "luminance",
            }}
            className="pointer-events-none absolute inset-0 bg-[var(--series)]"
          />
        ) : (
          <canvas
            ref={canvas}
            {...SIZE}
            aria-hidden="true"
            style={{ opacity: opacity / 100 }}
            className="pointer-events-none absolute inset-0 size-full"
          />
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-rule px-4 py-2">
        <div role="group" aria-label="Overlay" className="inline-flex rounded-sm border border-rule p-0.5">
          {VIEWS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={view === key}
              onClick={() => setView(key)}
              className="h-9 rounded-[3px] px-3 text-sm aria-pressed:bg-[var(--series-wash)] aria-pressed:font-semibold"
            >
              {label}
            </button>
          ))}
        </div>
        {view === "heatmap" && <HeatmapLegend />}
      </div>
      <figcaption className="flex items-center gap-3 border-t border-rule px-4 py-2 text-sm">
        <label htmlFor={control} className="flex-none">Overlay opacity</label>
        <input
          id={control}
          type="range"
          min="0"
          max="100"
          value={opacity}
          onChange={(event) => setOpacity(Number(event.target.value))}
          className="h-11 min-w-0 flex-1"
        />
        <output htmlFor={control} className="value w-10 text-right text-13">{opacity}%</output>
      </figcaption>
    </figure>
  );
}
