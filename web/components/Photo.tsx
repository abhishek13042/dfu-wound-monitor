import { ConstructedPhoto } from "@/components/ConstructedPhoto";
import { cn } from "@/lib/utils";

// The stored photograph when the service supplied a signed URL, otherwise the constructed placeholder.
// Signed URLs are relative to /api/v2 and reach the service through the same-origin proxy route.
export function Photo({ id, src, className, labelled }: { id: string; src?: string; className?: string; labelled?: boolean }) {
  if (!src) return <ConstructedPhoto id={id} className={className} labelled={labelled} />;
  // eslint-disable-next-line @next/next/no-img-element -- short-lived signed URL, not an optimisable asset.
  return <img src={src} alt="Uploaded wound photograph" className={cn("block h-auto w-full", className)} />;
}
