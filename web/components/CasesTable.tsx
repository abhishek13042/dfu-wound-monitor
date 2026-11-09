"use client";

import Link from "next/link";
import { useEffect, useId, useMemo, useState } from "react";
import { ChevronDown, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, ChevronUp, Search } from "lucide-react";

import { ReadingStrip } from "@/components/ReadingStrip";
import { StateTag } from "@/components/StateTag";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Pagination, PaginationContent, PaginationItem } from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Analysis, AnalysisStatus, IdentityStatus } from "@/lib/api";
import { basisCopy, identityCopy } from "@/lib/copy";
import { areaOf, formatDate } from "@/lib/format";

export interface CaseRow {
  id: string;
  label: string;
  identity: IdentityStatus;
  examinations: number;
  latestAt: string | null;
  status: AnalysisStatus | null;
  quality?: Analysis["quality"];
  measurement: Analysis["measurement"];
  changed: boolean;
}

type SortColumn = "label" | "latestAt" | "status";
const STORE = "dfu-opened-cases";

function readOpened(): string[] {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? "[]");
  } catch {
    return [];
  }
}

function writeOpened(ids: string[]) {
  try {
    localStorage.setItem(STORE, JSON.stringify(ids));
  } catch {
    // Without storage the marker stays until the service records the visit.
  }
}

export function CasesTable({ rows }: { rows: CaseRow[] }) {
  const sizeId = useId();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ column: SortColumn; direction: "asc" | "desc" }>({ column: "latestAt", direction: "desc" });
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [opened, setOpened] = useState<string[]>([]);

  useEffect(() => setOpened(readOpened()), []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matched = rows.filter((row) => `${row.label} ${row.id}`.toLowerCase().includes(needle));
    return [...matched].sort((left, right) => {
      const order = String(left[sort.column] ?? "").localeCompare(String(right[sort.column] ?? ""));
      return sort.direction === "asc" ? order : -order;
    });
  }, [rows, query, sort]);

  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize));
  const current = Math.min(page, pageCount - 1);
  const start = current * pageSize;
  const shown = visible.slice(start, start + pageSize);

  const toggleSort = (column: SortColumn) =>
    setSort((value) => ({ column, direction: value.column === column && value.direction === "asc" ? "desc" : "asc" }));

  const sortable = (column: SortColumn, label: React.ReactNode, width: string) => {
    const direction = sort.column === column ? sort.direction : undefined;
    return (
      <TableHead aria-sort={direction === "asc" ? "ascending" : direction === "desc" ? "descending" : "none"} className={`h-10 px-3 ${width}`}>
        <button type="button" onClick={() => toggleSort(column)} className="flex h-full items-center gap-1 text-13 font-medium text-ink-2 hover:text-ink">
          {label}
          {direction === "asc" && <ChevronUp className="size-3.5" aria-hidden="true" />}
          {direction === "desc" && <ChevronDown className="size-3.5" aria-hidden="true" />}
        </button>
      </TableHead>
    );
  };

  const plain = (label: string, width: string) => <TableHead className={`h-10 px-3 text-13 font-medium text-ink-2 ${width}`}>{label}</TableHead>;

  return (
    <div className="panel @container/cases">
      <div className="flex items-center border-b border-rule px-3 has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-ring">
        <Search className="size-4 flex-none text-ink-2" aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(0);
          }}
          placeholder="Filter by label or case ID"
          aria-label="Filter cases"
          className="h-11 w-full min-w-0 bg-transparent px-2 text-base placeholder:text-ink-2 focus-visible:outline-none"
        />
      </div>

      <Table className="stack-table table-fixed">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {sortable("label", "Case", "w-[30%] @max-[820px]/cases:w-auto")}
            {plain("Latest reading", "w-[190px] @max-[820px]/cases:w-[176px]")}
            {plain("Latest area", "w-[120px] @max-[820px]/cases:w-[112px]")}
            {plain("Basis", "w-[92px] @max-[820px]/cases:hidden")}
            {sortable(
              "latestAt",
              <span>
                Latest exam<span className="@max-[820px]/cases:hidden">ination</span>
              </span>,
              "w-[132px] @max-[820px]/cases:w-[116px]",
            )}
            {sortable("status", "State", "w-[104px] @max-[820px]/cases:w-[108px]")}
          </TableRow>
        </TableHeader>
        <TableBody>
          {shown.map((row) => {
            const changed = row.changed && !opened.includes(row.id);
            const area = row.measurement ? areaOf(row.measurement) : null;
            return (
              <TableRow key={row.id} className="h-11 hover:bg-secondary">
                <TableCell data-wide className="truncate px-3 whitespace-nowrap @max-[820px]/cases:whitespace-normal">
                  <Link
                    href={`/cases/${row.id}`}
                    onClick={() => writeOpened([...opened, row.id])}
                    title={row.label}
                    className="font-semibold hover:underline"
                  >
                    {row.label}
                  </Link>
                  <span className="block truncate text-xs text-ink-2">
                    <span className="value">{row.id}</span>, {identityCopy[row.identity].toLowerCase()}, {row.examinations} exam{row.examinations === 1 ? "" : "s"}
                  </span>
                </TableCell>
                <TableCell data-wide className="px-3 whitespace-normal">
                  {row.quality ? <ReadingStrip quality={row.quality} /> : <span className="text-13 text-ink-2">No photo yet</span>}
                </TableCell>
                <TableCell data-label="Latest area" className="px-3">
                  {area ? (
                    <span className="value">
                      {area.value} <span className="text-13 text-ink-2">{area.unit}</span>
                    </span>
                  ) : (
                    <span className="text-13 text-ink-2">No value</span>
                  )}
                  {row.measurement && (
                    <span className="hidden text-xs text-ink-2 @min-[600px]/cases:@max-[820px]/cases:block">
                      {basisCopy[row.measurement.measurement_basis].short}
                    </span>
                  )}
                </TableCell>
                <TableCell data-label="Basis" className="px-3 text-13 @min-[600px]/cases:@max-[820px]/cases:hidden">
                  {row.measurement ? basisCopy[row.measurement.measurement_basis].short : <span className="text-ink-2">None</span>}
                </TableCell>
                <TableCell data-label="Latest examination" className="value px-3 text-13">
                  {row.latestAt ? formatDate(row.latestAt) : <span className="font-sans text-ink-2">None</span>}
                </TableCell>
                <TableCell data-label="State" className="px-3">
                  {row.status ? <StateTag status={row.status} /> : <span className="text-13 text-ink-2">Empty case</span>}
                  {changed && <span className="block text-xs font-semibold text-warn-ink">Changed</span>}
                </TableCell>
              </TableRow>
            );
          })}
          {shown.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} data-wide className="px-3 py-10 text-center whitespace-normal text-ink-2">
                No case matches “{query}”.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-3 py-2">
        <div className="flex items-center gap-2 text-13">
          <Label htmlFor={sizeId} className="text-13 font-normal">Rows per page</Label>
          <Select
            value={pageSize.toString()}
            onValueChange={(value) => {
              if (!value) return;
              setPageSize(Number(value));
              setPage(0);
            }}
          >
            <SelectTrigger id={sizeId} className="h-10 w-fit">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[10, 25, 50].map((size) => (
                <SelectItem key={size} value={size.toString()}>{size}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <p className="value text-13" aria-live="polite">
          {visible.length === 0 ? 0 : start + 1}–{Math.min(start + pageSize, visible.length)} of {visible.length}
        </p>
        <Pagination className="mx-0 w-auto justify-end">
          <PaginationContent className="gap-1">
            <PaginationItem>
              <Button size="icon" variant="outline" onClick={() => setPage(0)} disabled={current === 0} aria-label="First page"><ChevronFirst aria-hidden="true" /></Button>
            </PaginationItem>
            <PaginationItem>
              <Button size="icon" variant="outline" onClick={() => setPage(current - 1)} disabled={current === 0} aria-label="Previous page"><ChevronLeft aria-hidden="true" /></Button>
            </PaginationItem>
            <PaginationItem>
              <Button size="icon" variant="outline" onClick={() => setPage(current + 1)} disabled={current >= pageCount - 1} aria-label="Next page"><ChevronRight aria-hidden="true" /></Button>
            </PaginationItem>
            <PaginationItem>
              <Button size="icon" variant="outline" onClick={() => setPage(pageCount - 1)} disabled={current >= pageCount - 1} aria-label="Last page"><ChevronLast aria-hidden="true" /></Button>
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </div>
    </div>
  );
}
