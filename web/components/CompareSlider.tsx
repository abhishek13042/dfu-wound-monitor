"use client";

import { useId, useState } from "react";

import { PlaceholderLabel } from "@/components/ConstructedPhoto";
import { Photo } from "@/components/Photo";

interface Props {
  earlier: string;
  later: string;
  earlierLabel: string;
  laterLabel: string;
  earlierSrc?: string;
  laterSrc?: string;
}

export function CompareSlider({ earlier, later, earlierLabel, laterLabel, earlierSrc, laterSrc }: Props) {
  const control = useId();
  const [split, setSplit] = useState(50);
  return (
    <figure className="panel overflow-hidden">
      <div className="relative">
        <Photo id={later} src={laterSrc} className="block h-auto w-full" labelled={false} />
        <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
          <Photo id={earlier} src={earlierSrc} className="block h-auto w-full" labelled={false} />
        </div>
        <div aria-hidden="true" className="absolute inset-y-0 w-0.5 bg-panel" style={{ left: `${split}%` }} />
        {/* One label over both layers, so the clipped layer never hides the other's. */}
        {(!earlierSrc || !laterSrc) && <PlaceholderLabel />}
      </div>
      <figcaption className="border-t border-rule px-4 py-2 text-sm">
        <div className="flex justify-between gap-3 text-13">
          <span>Earlier: <span className="value">{earlierLabel}</span></span>
          <span>Later: <span className="value">{laterLabel}</span></span>
        </div>
        <label htmlFor={control} className="sr-only">Move the divider between the earlier and later image</label>
        <input
          id={control}
          type="range"
          min="0"
          max="100"
          value={split}
          onChange={(event) => setSplit(Number(event.target.value))}
          className="h-11 w-full"
        />
      </figcaption>
    </figure>
  );
}
