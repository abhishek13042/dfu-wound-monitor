import Link from "next/link";

// The name sits beside three key pads, the mark's only drawn parts.
export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap text-base font-bold text-rail-ink [font-stretch:80%]">
      <span aria-hidden="true" className="flex gap-0.5">
        <span className="size-2.5 bg-pass" />
        <span className="size-2.5 bg-warn" />
        <span className="size-2.5 bg-reject" />
      </span>
      DFU-WoundMonitor
    </Link>
  );
}
