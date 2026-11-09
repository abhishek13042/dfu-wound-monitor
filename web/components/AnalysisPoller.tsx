"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

// Re-reads the job while it is queued or running (REQ-P08-S02-002): every 2 seconds while the tab is visible,
// every 15 seconds while it is hidden. The server page renders whichever state the service reports.
export function AnalysisPoller({ active }: { active: boolean }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      timer = setTimeout(() => {
        router.refresh();
        schedule();
      }, document.hidden ? 15_000 : 2_000);
    };
    const onVisibility = () => {
      clearTimeout(timer);
      if (!document.hidden) router.refresh();
      schedule();
    };
    schedule();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [active, router]);
  return null;
}
