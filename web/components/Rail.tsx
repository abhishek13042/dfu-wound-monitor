"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { FolderOpen, ImageUp, Menu, Scaling, UserRound, X } from "lucide-react";

import { Wordmark } from "@/components/Wordmark";
import { PadMark } from "@/components/ReadingStrip";
import type { Readiness } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/cases", label: "Cases", icon: FolderOpen },
  { href: "/analyse", label: "New analysis", icon: ImageUp },
  { href: "/compare", label: "Compare", icon: Scaling },
  { href: "/account", label: "Account", icon: UserRound },
];

const SERVICES = ["model", "database", "storage", "queue"] as const;

export function Rail({ readiness }: { readiness: Readiness }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [pathname]);

  return (
    <aside className="on-aubergine z-40 bg-aubergine text-rail-ink min-[900px]:sticky min-[900px]:top-0 min-[900px]:flex min-[900px]:h-dvh min-[900px]:w-[220px] min-[900px]:flex-none min-[900px]:flex-col">
      <div className="flex h-14 items-center justify-between px-4">
        <Wordmark href="/cases" />
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls="rail-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          className="-mr-2 grid size-11 place-items-center min-[900px]:hidden"
        >
          {open ? <X className="size-5" aria-hidden="true" /> : <Menu className="size-5" aria-hidden="true" />}
        </button>
      </div>

      <div id="rail-menu" className={cn("flex-1 flex-col justify-between pb-4 min-[900px]:flex", open ? "flex" : "hidden")}>
        <nav aria-label="Main" className="px-2">
          <ul>
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex h-11 items-center gap-3 rounded-sm px-3 text-sm font-medium",
                      active ? "bg-rail-ink text-aubergine" : "text-rail-ink hover:bg-aubergine-2",
                    )}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <section aria-label="Service readiness" className="mx-4 mt-6 border-t border-aubergine-2 pt-3">
          <h2 className="pb-1 text-xs font-medium text-rail-muted [font-stretch:100%]">Service readiness</h2>
          <ul>
            {SERVICES.map((service) => {
              const ready = readiness[service] === "READY";
              return (
                <li key={service} className="flex h-7 items-center justify-between text-13 capitalize">
                  <span>{service}</span>
                  <span className="flex items-center gap-1.5 normal-case text-rail-muted">
                    {ready ? "Ready" : "Not ready"}
                    <span data-state={ready ? "pass" : "fail"} className="pad size-3.5">
                      <PadMark state={ready ? "pass" : "fail"} className="size-2.5" />
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </aside>
  );
}
