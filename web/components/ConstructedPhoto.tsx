import { outline, seedOf, toPath } from "@/lib/shape";
import { cn } from "@/lib/utils";

// Stands in for a photograph until real sample images are supplied.
// The label is HTML so it stays 13px whatever size the image is drawn at.
export function ConstructedPhoto({ id, className }: { id: string; className?: string }) {
  const seed = seedOf(id);
  return (
    <div className={cn("relative", className)}>
      <svg viewBox="0 0 400 300" role="img" aria-label="Constructed placeholder image, not a photograph" className="block h-auto w-full">
        <rect width="400" height="300" fill="var(--photo-1)" />
        <path d={toPath(outline(seed, 200, 165, 190, 120))} fill="var(--photo-2)" />
        <path d={toPath(outline(seed + 5, 205, 150, 110, 78))} fill="var(--photo-3)" />
        {Array.from({ length: 21 }, (_, index) => (
          <rect key={index} x={20 + index * 9} y={270} width="1" height={index % 5 === 0 ? 14 : 8} fill="var(--photo-ink)" />
        ))}
      </svg>
      <span aria-hidden="true" className="absolute top-3 left-3 bg-[var(--photo-3)] px-1.5 text-13 text-[var(--photo-ink)]">
        Constructed placeholder, no photograph
      </span>
    </div>
  );
}
