"use client";

import { useEffect, useId, useRef, useState } from "react";

import { ConstructedPhoto } from "@/components/ConstructedPhoto";
import { outline, seedOf } from "@/lib/shape";

const SIZE = { width: 800, height: 600 };

export function MaskOverlay({ id, areaShare }: { id: string; areaShare: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const control = useId();
  const [opacity, setOpacity] = useState(55);

  useEffect(() => {
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
  }, [id, areaShare]);

  return (
    <figure className="panel overflow-hidden">
      <div className="relative">
        <ConstructedPhoto id={id} className="block h-auto w-full" />
        <canvas
          ref={canvas}
          {...SIZE}
          aria-hidden="true"
          style={{ opacity: opacity / 100 }}
          className="pointer-events-none absolute inset-0 size-full"
        />
      </div>
      <figcaption className="flex items-center gap-3 border-t border-rule px-4 py-2 text-sm">
        <label htmlFor={control} className="flex-none">Mask opacity</label>
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
