import { isMock } from "@/lib/api/mode";
import { NOTICE } from "@/lib/copy";

export function MedicalNotice({ constructed = true }: { constructed?: boolean }) {
  return (
    <p className="sticky top-0 z-30 flex flex-wrap items-center gap-x-3 border-b border-warn bg-warn-wash px-4 py-1.5 text-13 font-medium text-foreground sm:px-6">
      <span>{NOTICE}</span>
      {constructed && isMock && <span className="font-normal text-warn-ink">All records shown are constructed demonstration data.</span>}
    </p>
  );
}
