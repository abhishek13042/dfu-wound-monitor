"use client";

import { useId, useState } from "react";

import { ConstructedPhoto } from "@/components/ConstructedPhoto";

interface Props {
  earlier: string;
  later: string;
  earlierLabel: string;
  laterLabel: string;
}

export function CompareSlider({ earlier, later, earlierLabel, laterLabel }: Props) {
  const control = useId();
  const [split, setSplit] = useState(50);
  return (
    <figure className="panel overflow-hidden">
      <div className="relative">
        <ConstructedPhoto id={later} className="block h-auto w-full" />
        <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
          <ConstructedPhoto id={earlier} className="block h-auto w-full" />
        </div>
        <div aria-hidden="true" className="absolute inset-y-0 w-0.5 bg-panel" style={{ left: `${split}%` }} />
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
