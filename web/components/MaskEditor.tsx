"use client";

import { Eraser, Paintbrush, Redo2, RotateCcw, Undo2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { Photo } from "@/components/Photo";
import { Button } from "@/components/ui/button";
import type { Correction } from "@/lib/api";
import { problemText, send } from "@/lib/api/browser";
import { isMock } from "@/lib/api/mode";
import { messageFor } from "@/lib/errors";
import { formatNumber } from "@/lib/format";
import { outline, seedOf } from "@/lib/shape";

// Each step keeps one byte per pixel, so 20 steps of a 1600 x 1200 photo stay under 40 MB.
const HISTORY = 20;
const draftKey = (id: string) => `dfu-mask-draft:${id}`;

interface Props {
  id: string;
  width: number;
  height: number;
  areaShare: number;
  image?: string;
  mask?: string;
}

type Tool = "brush" | "eraser";
type Draft = { saved_at: string; png: string };

function readDraft(id: string): Draft | null {
  try {
    const raw = window.localStorage.getItem(draftKey(id));
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}

function dropDraft(id: string) {
  try {
    window.localStorage.removeItem(draftKey(id));
  } catch {
    // Storage can be blocked; the draft then never existed.
  }
}

// The series token in whatever form the theme writes it, resolved by the browser to RGB.
function seriesRgb(element: HTMLElement): [number, number, number] {
  const probe = document.createElement("canvas").getContext("2d")!;
  probe.fillStyle = getComputedStyle(element).getPropertyValue("--series").trim() || "#33578f";
  probe.fillRect(0, 0, 1, 1);
  const [r, g, b] = probe.getImageData(0, 0, 1, 1).data;
  return [r, g, b];
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    // Signed URLs may be on the storage host; without CORS the pixels cannot be read back.
    if (!src.startsWith("data:")) image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
}

// REQ-P09-S03-001: redraw the outline with a brush and an eraser, at the photo's own resolution.
// The model's result is never changed; saving sends a new 0/255 PNG that the service measures (REQ-P09-S03-002, -003).
export function MaskEditor({ id, width, height, areaShare, image, mask }: Props) {
  const router = useRouter();
  const canvas = useRef<HTMLCanvasElement>(null);
  const last = useRef<{ x: number; y: number } | null>(null);
  const history = useRef<{ steps: Uint8Array[]; index: number }>({ steps: [], index: -1 });
  const sizeControl = useId();
  const [tool, setTool] = useState<Tool>("brush");
  const [size, setSize] = useState(() => Math.max(4, Math.round(width / 40)));
  const [canStep, setCanStep] = useState({ undo: false, redo: false });
  const [ready, setReady] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [share, setShare] = useState(false);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState<{ text: string; failed: boolean } | null>(null);

  const context = () => canvas.current?.getContext("2d", { willReadFrequently: true }) ?? null;

  const snapshot = useCallback((): Uint8Array => {
    const pixels = context()!.getImageData(0, 0, width, height).data;
    const alpha = new Uint8Array(width * height);
    for (let i = 0; i < alpha.length; i += 1) alpha[i] = pixels[i * 4 + 3] >= 128 ? 1 : 0;
    return alpha;
  }, [width, height]);

  const paint = useCallback(
    (alpha: Uint8Array) => {
      const ctx = context();
      if (!ctx || !canvas.current) return;
      const [r, g, b] = seriesRgb(canvas.current);
      const data = ctx.createImageData(width, height);
      for (let i = 0; i < alpha.length; i += 1) {
        if (!alpha[i]) continue;
        data.data.set([r, g, b, 255], i * 4);
      }
      ctx.putImageData(data, 0, 0);
    },
    [width, height],
  );

  const record = useCallback(() => {
    const state = history.current;
    state.steps = [...state.steps.slice(0, state.index + 1), snapshot()].slice(-HISTORY);
    state.index = state.steps.length - 1;
    setCanStep({ undo: state.index > 0, redo: false });
  }, [snapshot]);

  const step = useCallback(
    (by: -1 | 1) => {
      const state = history.current;
      const next = state.index + by;
      if (next < 0 || next >= state.steps.length) return;
      state.index = next;
      paint(state.steps[next]);
      setCanStep({ undo: next > 0, redo: next < state.steps.length - 1 });
      saveDraft();
    },
    // saveDraft only reads refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [paint],
  );

  // A stroke is saved on this device as soon as it ends, so a lost connection or a closed tab loses nothing.
  const saveDraft = () => {
    if (!canvas.current) return;
    const value: Draft = { saved_at: new Date().toISOString(), png: canvas.current.toDataURL("image/png") };
    try {
      window.localStorage.setItem(draftKey(id), JSON.stringify(value));
    } catch {
      // Quota or blocked storage: the editor still works, it just cannot recover after a reload.
    }
  };

  // Start from the model's outline: the stored mask, or the constructed shape in mock mode.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = context();
      if (!ctx || !canvas.current) return;
      const alpha = new Uint8Array(width * height);
      if (mask) {
        try {
          const source = await loadImage(mask);
          const scratch = document.createElement("canvas");
          scratch.width = width;
          scratch.height = height;
          const scratchContext = scratch.getContext("2d")!;
          scratchContext.drawImage(source, 0, 0, width, height);
          const pixels = scratchContext.getImageData(0, 0, width, height).data;
          for (let i = 0; i < alpha.length; i += 1) alpha[i] = pixels[i * 4] > 127 ? 1 : 0;
        } catch {
          setNote({ text: "The model's outline could not be loaded, so the editor starts empty.", failed: true });
        }
      } else {
        const scale = width / 800;
        const radius = Math.sqrt(areaShare) * 600;
        const points = outline(seedOf(id) + 11, 410, 300, radius * 1.15, radius * 0.87);
        ctx.clearRect(0, 0, width, height);
        ctx.beginPath();
        points.forEach(([x, y], index) => (index === 0 ? ctx.moveTo(x * scale, y * scale) : ctx.lineTo(x * scale, y * scale)));
        ctx.closePath();
        ctx.fillStyle = "#000";
        ctx.fill();
        alpha.set(snapshot());
      }
      if (cancelled) return;
      paint(alpha);
      history.current = { steps: [], index: -1 };
      record();
      setDraft(readDraft(id));
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [id, width, height, areaShare, mask, paint, record, snapshot]);

  const restore = async () => {
    if (!draft) return;
    try {
      const source = await loadImage(draft.png);
      const ctx = context()!;
      ctx.clearRect(0, 0, width, height);
      ctx.drawImage(source, 0, 0, width, height);
      paint(snapshot());
      record();
      setNote({ text: "Draft restored. It is not saved to the service until you save it.", failed: false });
    } catch {
      setNote({ text: "The draft could not be read, so it was discarded.", failed: true });
      dropDraft(id);
    }
    setDraft(null);
  };

  const discard = () => {
    dropDraft(id);
    setDraft(null);
  };

  const point = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    return { x: ((event.clientX - box.left) * width) / box.width, y: ((event.clientY - box.top) * height) / box.height };
  };

  const stroke = (from: { x: number; y: number }, to: { x: number; y: number }) => {
    const ctx = context();
    if (!ctx || !canvas.current) return;
    ctx.globalCompositeOperation = tool === "eraser" ? "destination-out" : "source-over";
    ctx.strokeStyle = `rgb(${seriesRgb(canvas.current).join(" ")})`;
    ctx.lineWidth = size;
    ctx.lineCap = ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
    ctx.globalCompositeOperation = "source-over";
  };

  const down = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!ready || saving || event.button > 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    last.current = point(event);
    stroke(last.current, last.current);
  };

  const move = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!last.current) return;
    const next = point(event);
    stroke(last.current, next);
    last.current = next;
  };

  const up = () => {
    if (!last.current) return;
    last.current = null;
    // Edges are snapped to on or off, so what is drawn is exactly what is saved.
    paint(snapshot());
    record();
    saveDraft();
  };

  const keys = (event: React.KeyboardEvent) => {
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z") return;
    event.preventDefault();
    step(event.shiftKey ? 1 : -1);
  };

  const reset = () => {
    const first = history.current.steps[0];
    if (!first) return;
    paint(first);
    record();
    saveDraft();
  };

  const save = async () => {
    setSaving(true);
    setNote(null);
    const alpha = snapshot();
    const area = alpha.reduce((total, value) => total + value, 0);
    try {
      // A 0/255 PNG the size of the photo: white inside the outline, black outside, fully opaque.
      const out = document.createElement("canvas");
      out.width = width;
      out.height = height;
      const outContext = out.getContext("2d")!;
      const data = outContext.createImageData(width, height);
      for (let i = 0; i < alpha.length; i += 1) {
        const value = alpha[i] ? 255 : 0;
        data.data.set([value, value, value, 255], i * 4);
      }
      outContext.putImageData(data, 0, 0);
      const blob = await new Promise<Blob>((resolve, reject) =>
        out.toBlob((result) => (result ? resolve(result) : reject(new Error("PNG encoding failed"))), "image/png"),
      );
      let saved: Pick<Correction, "version" | "measurement"> = {
        version: 0,
        measurement: { status: area ? "MEASURED" : "EMPTY", pixel: { area_px: area, perimeter_px: 0, max_feret_px: 0, min_feret_px: 0, component_count: 0 }, physical: null, warnings: [] },
      };
      if (!isMock) {
        const form = new FormData();
        form.append("file", blob, "mask.png");
        form.append("research_opt_in", String(share));
        saved = await send<Correction>(`/analyses/${id}/corrections`, { method: "POST", body: form });
      }
      dropDraft(id);
      const physical = saved.measurement.physical;
      const areaText = physical ? `${formatNumber(physical.area_mm2, 1)} mm²` : `${formatNumber(saved.measurement.pixel.area_px, 0)} px²`;
      setNote({
        text: isMock
          ? `Constructed data: nothing was sent. The outline covers ${formatNumber(area, 0)} px².`
          : saved.measurement.status === "EMPTY"
            ? `Saved as version ${saved.version}. The outline is empty, so there is no area.`
            : `Saved as version ${saved.version}. The service measured an area of ${areaText}.`,
        failed: false,
      });
      router.refresh();
    } catch (error) {
      setNote({ text: `${problemText(error, messageFor)} Your draft is kept on this device.`, failed: true });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div onKeyDown={keys}>
      {draft && (
        <div role="status" className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-sm border border-rule bg-[var(--series-wash)] px-3 py-2 text-sm">
          <span className="min-w-0 flex-1">An unsaved draft from {new Date(draft.saved_at).toLocaleString()} is on this device.</span>
          <Button type="button" size="sm" onClick={() => void restore()}>Restore draft</Button>
          <Button type="button" size="sm" variant="outline" onClick={discard}>Discard</Button>
        </div>
      )}

      <div className="relative overflow-hidden rounded-sm border border-rule">
        <Photo id={id} src={image} labelled={false} className="block h-auto w-full" />
        <canvas
          ref={canvas}
          width={width}
          height={height}
          role="img"
          aria-label="Outline being corrected. Draw with a mouse, pen or finger."
          onPointerDown={down}
          onPointerMove={move}
          onPointerUp={up}
          onPointerCancel={up}
          style={{ touchAction: "none", cursor: tool === "eraser" ? "cell" : "crosshair" }}
          className="absolute inset-0 size-full opacity-55"
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-3">
        <div role="group" aria-label="Tool" className="inline-flex rounded-sm border border-rule p-0.5">
          {([["brush", "Brush", Paintbrush], ["eraser", "Eraser", Eraser]] as const).map(([key, label, Icon]) => (
            <button
              key={key}
              type="button"
              aria-pressed={tool === key}
              onClick={() => setTool(key)}
              className="inline-flex h-9 items-center gap-1.5 rounded-[3px] px-3 text-sm aria-pressed:bg-[var(--series-wash)] aria-pressed:font-semibold"
            >
              <Icon aria-hidden="true" className="size-4" />
              {label}
            </button>
          ))}
        </div>
        <div className="flex min-w-[220px] flex-1 items-center gap-3 text-sm">
          <label htmlFor={sizeControl} className="flex-none">Size</label>
          <input
            id={sizeControl}
            type="range"
            min={2}
            max={Math.max(40, Math.round(width / 8))}
            value={size}
            onChange={(event) => setSize(Number(event.target.value))}
            className="h-11 min-w-0 flex-1"
          />
          <output htmlFor={sizeControl} className="value w-14 text-right text-13">{size} px</output>
        </div>
        <div className="flex gap-1">
          <Button type="button" variant="outline" size="icon-lg" className="size-11" aria-label="Undo" disabled={!canStep.undo} onClick={() => step(-1)}>
            <Undo2 aria-hidden="true" />
          </Button>
          <Button type="button" variant="outline" size="icon-lg" className="size-11" aria-label="Redo" disabled={!canStep.redo} onClick={() => step(1)}>
            <Redo2 aria-hidden="true" />
          </Button>
          <Button type="button" variant="outline" size="icon-lg" className="size-11" aria-label="Start again from the model's outline" disabled={!canStep.undo} onClick={reset}>
            <RotateCcw aria-hidden="true" />
          </Button>
        </div>
      </div>

      <label className="mt-4 flex items-start gap-3">
        <input
          type="checkbox"
          checked={share}
          onChange={(event) => setShare(event.target.checked)}
          className="mt-1 size-5 flex-none accent-[var(--aubergine)]"
        />
        <span>
          <span className="block font-medium">Share this correction for research</span>
          <span className="block max-w-[62ch] text-sm text-ink-2">
            Off unless you tick it. A shared outline is reviewed before any use, and you can withdraw it later.
          </span>
        </span>
      </label>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button type="button" onClick={() => void save()} disabled={!ready || saving}>
          {saving ? "Saving…" : "Save corrected outline"}
        </Button>
        <p className="text-13 text-ink-2">Saving adds a new version. The model&apos;s outline and values stay as they are.</p>
      </div>
      <p aria-live="polite" className={`mt-2 min-h-5 text-sm ${note?.failed ? "text-reject" : "text-ink-2"}`}>{note?.text}</p>
    </div>
  );
}
