import {
  PADS, QUALITY, MODEL, rgbaToRgb, measureQuality, decide, pilResizeBilinear,
  buildTtaBatch, meanOfTtaViews, upsampleBilinear, postprocess,
} from "./pipeline.js";

const MODEL_URL = "https://huggingface.co/abhishek1402/dfu-resnet34-unet/resolve/" +
  "0fea018600a205f37cc92b2f171ea1d1f41401cf/resnet34_unet_512.onnx";
const MODEL_SHA256 = "d3738aed14c52b3b227226b61f56c66fd8550a705c296ad1c5a6ff124fafb698";
const MODEL_BYTES = 97730777;
const ORT_DIST = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";
const CACHE_NAME = "dfu-model-v1";
const MAX_PIXELS = 50_000_000;
const SIZE = MODEL.inputSize;

const $ = (id) => document.getElementById(id);
const el = {
  file: $("file"), sample: $("sample"), drop: $("drop"), fileName: $("file-name"),
  strip: $("strip"), outcome: $("outcome"), readings: $("readings"), readingsBody: $("readings-body"),
  modelStatus: $("model-status"), progress: $("model-progress"), fill: $("model-fill"),
  empty: $("empty"), stage: $("stage"), photo: $("photo"), overlay: $("overlay"), stageHidden: $("stage-hidden"),
  controls: $("view-controls"), showPhoto: $("show-photo"), opacity: $("opacity"), opacityOut: $("opacity-out"),
  saveMask: $("save-mask"), run: $("m-run"),
  area: $("m-area"), share: $("m-share"), regions: $("m-regions"), bbox: $("m-bbox"), prob: $("m-prob"), size: $("m-size"),
};

const fmt = new Intl.NumberFormat("en-GB");
const forceWasm = new URLSearchParams(location.search).get("ep") === "wasm";
let runId = 0;
let sessionPromise = null;
let sessionBackend = "";
let lastMask = null;

// ---------- Reading strip ----------
const MARKS = {
  pass: '<path d="M3.5 8.5 6.5 11.5 12.5 4.5"/>',
  fail: '<path d="M4 4 12 12M12 4 4 12"/>',
  none: '<path d="M5 8h6"/>',
};
const WORD = { pass: "passed", fail: "failed", none: "not read" };
// Narrow screens use the short names from web/lib/pads.ts.
const SHORT = { sharpness: "Sharp", under: "Under", over: "Over" };

function stripSummary(states) {
  if (states.every((s) => s === "none")) return "Quality reading: not read yet.";
  const passed = states.filter((s) => s === "pass").length;
  const failed = PADS.filter((_, i) => states[i] === "fail").map((p) => p.label);
  const unread = states.filter((s) => s === "none").length;
  const parts = [`${passed} of 9 checks passed`];
  if (failed.length) parts.push(`failed: ${failed.join(", ")}`);
  if (unread) parts.push(`${unread} not read`);
  return `Quality reading: ${parts.join("; ")}.`;
}

function renderStrip(states, animate = false) {
  el.strip.setAttribute("aria-label", stripSummary(states));
  el.strip.innerHTML = PADS.map((pad, i) => {
    const s = states[i];
    const step = animate ? ` data-step style="--step:${i}"` : "";
    return `<li data-state="${s}"><span class="pad" data-state="${s}"${step}>` +
      `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="square" aria-hidden="true">${MARKS[s]}</svg>` +
      `</span><span class="name" title="${pad.label}"><span class="long">${pad.label}</span>` +
      `<span class="short" aria-hidden="true">${SHORT[pad.key] ?? pad.label}</span>` +
      `<span class="sr-only">: ${WORD[s]}</span></span></li>`;
  }).join("");
}

function setOutcome(text, tone) {
  el.outcome.textContent = text;
  if (tone) el.outcome.dataset.tone = tone; else delete el.outcome.dataset.tone;
}

const n2 = (v) => v.toFixed(2);
const n1 = (v) => v.toFixed(1);
function renderReadings(m, reasons) {
  const c = QUALITY.checks;
  const rows = [
    ["Size", "TOO_SMALL", `${Math.min(m.width, m.height)} px`, `≥ ${c.min_side_px} px`],
    ["Aspect", "BAD_ASPECT_RATIO", n2(Math.max(m.width, m.height) / Math.max(1, Math.min(m.width, m.height))), `≤ ${n1(c.max_aspect_ratio)}`],
    ["Content", "INSUFFICIENT_CONTENT", `${n2(m.content_fraction)}, ${n2(m.entropy)} bits`, `≥ ${n2(c.min_content_fraction)}, ${n1(c.min_entropy_bits)}`],
    ["Sharpness", "BLURRY", n1(m.laplacian_variance), `≥ ${n1(c.min_laplacian_variance)}`],
    ["Underexposure", "UNDEREXPOSED", `${n1(m.mean_luminance)}, ${n2(m.dark_fraction)}`, `≥ ${c.min_mean_luminance}, ≤ ${n2(c.max_dark_fraction)}`],
    ["Overexposure", "OVEREXPOSED", `${n1(m.mean_luminance)}, ${n2(m.bright_fraction)}`, `≤ ${c.max_mean_luminance}, ≤ ${n2(c.max_bright_fraction)}`],
    ["Contrast", "LOW_CONTRAST", n1(m.luminance_std), `≥ ${c.min_luminance_std}`],
    ["Glare", "GLARE", n2(m.glare_fraction), `≤ ${n2(c.max_glare_fraction)}`],
  ];
  el.readingsBody.innerHTML = rows.map(([name, code, value, limit]) => {
    const failed = reasons.includes(code);
    return `<tr><th scope="row">${name}</th><td class="value${failed ? " fail" : ""}">${value}${failed ? " <span class=\"sr-only\">(failed)</span>" : ""}</td><td class="value">${limit}</td></tr>`;
  }).join("");
  el.readings.hidden = false;
}

// ---------- Measurements ----------
function clearMeasures() {
  for (const k of ["area", "share", "regions", "bbox", "prob", "size"]) el[k].textContent = "–";
  el.run.hidden = true;
  el.saveMask.hidden = true;
  lastMask = null;
}

function renderMeasures(r, w, h, ms) {
  el.area.textContent = `${fmt.format(r.area_px)} px`;
  el.share.textContent = `${(r.area_fraction * 100).toFixed(2)} %`;
  el.regions.textContent = r.dropped_regions ? `${r.regions} (${r.dropped_regions} under 128 px dropped)` : String(r.regions);
  el.bbox.textContent = r.area_px ? `${fmt.format(r.bbox_width_px)} × ${fmt.format(r.bbox_height_px)} px` : "–";
  el.prob.textContent = r.mean_probability == null ? "–" : r.mean_probability.toFixed(2);
  el.size.textContent = `${fmt.format(w)} × ${fmt.format(h)} px`;
  el.run.textContent = `Ran on ${sessionBackend} in ${fmt.format(Math.round(ms))} ms.`;
  el.run.hidden = false;
  el.saveMask.hidden = !r.area_px;
}

// ---------- Viewer ----------
function showStage(bitmap) {
  const { width: w, height: h } = bitmap;
  for (const c of [el.photo, el.overlay]) { c.width = w; c.height = h; }
  el.photo.getContext("2d").drawImage(bitmap, 0, 0);
  el.overlay.getContext("2d").clearRect(0, 0, w, h);
  el.empty.hidden = true;
  el.stage.hidden = false;
  el.controls.hidden = false;
}

function drawMask(mask, w, h) {
  const ctx = el.overlay.getContext("2d");
  const img = ctx.createImageData(w, h);
  for (let i = 0; i < mask.length; i++) {
    if (!mask[i]) continue;
    img.data[i * 4] = 0x33; img.data[i * 4 + 1] = 0x57; img.data[i * 4 + 2] = 0x8f; img.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
}

el.opacity.addEventListener("input", () => {
  el.overlay.style.opacity = String(el.opacity.value / 100);
  el.opacityOut.textContent = `${el.opacity.value}%`;
});
el.showPhoto.addEventListener("change", () => {
  el.stage.classList.toggle("photo-off", !el.showPhoto.checked);
  el.stageHidden.hidden = el.showPhoto.checked;
});
el.saveMask.addEventListener("click", () => {
  if (!lastMask) return;
  const { mask, w, h } = lastMask;
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const ctx = c.getContext("2d");
  const img = ctx.createImageData(w, h);
  for (let i = 0; i < mask.length; i++) {
    const v = mask[i] ? 255 : 0;
    img.data[i * 4] = v; img.data[i * 4 + 1] = v; img.data[i * 4 + 2] = v; img.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  c.toBlob((blob) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "segmentation-mask.png";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }, "image/png");
});

// ---------- Model ----------
function setModelStatus(text, tone) {
  el.modelStatus.textContent = text;
  if (tone) el.modelStatus.dataset.tone = tone; else delete el.modelStatus.dataset.tone;
}

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

async function download() {
  const response = await fetch(MODEL_URL);
  if (!response.ok) throw new Error(`Model download failed (HTTP ${response.status}).`);
  const total = Number(response.headers.get("content-length")) || MODEL_BYTES;
  const bytes = new Uint8Array(total);
  const reader = response.body.getReader();
  let got = 0;
  el.progress.hidden = false;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (got + value.length > bytes.length) throw new Error("Model download was larger than expected.");
    bytes.set(value, got);
    got += value.length;
    el.fill.style.width = `${Math.min(100, (got / total) * 100)}%`;
    setModelStatus(`Downloading the model: ${(got / 1e6).toFixed(1)} of ${(total / 1e6).toFixed(1)} MB.`);
  }
  el.progress.hidden = true;
  return bytes.subarray(0, got);
}

async function loadModelBytes() {
  let cache = null;
  try { cache = await caches.open(CACHE_NAME); } catch { /* no Cache API: download each visit */ }
  if (cache) {
    try {
      const hit = await cache.match(MODEL_URL);
      if (hit) {
        setModelStatus("Checking the saved model…");
        const bytes = new Uint8Array(await hit.arrayBuffer());
        if (await sha256Hex(bytes) === MODEL_SHA256) return { bytes, from: "saved copy" };
        await cache.delete(MODEL_URL);
      }
    } catch { /* fall through to a fresh download */ }
  }
  const bytes = await download();
  setModelStatus("Checking the download against its SHA-256…");
  if (await sha256Hex(bytes) !== MODEL_SHA256) {
    throw new Error("The downloaded model does not match its published SHA-256, so it was not run.");
  }
  if (cache) {
    try { await cache.put(MODEL_URL, new Response(bytes)); } catch { /* storage full: still usable now */ }
  }
  return { bytes, from: "download" };
}

async function waitForOrt() {
  for (let i = 0; i < 200 && !window.ort; i++) await new Promise((r) => setTimeout(r, 50));
  if (!window.ort) throw new Error("ONNX Runtime Web did not load. Check the connection and reload.");
  window.ort.env.wasm.wasmPaths = ORT_DIST;
  return window.ort;
}

function getSession() {
  if (!sessionPromise) {
    sessionPromise = (async () => {
      const ort = await waitForOrt();
      const { bytes, from } = await loadModelBytes();
      setModelStatus("Starting the model…");
      let session = null;
      if (!forceWasm && navigator.gpu) {
        try {
          session = await ort.InferenceSession.create(bytes, { executionProviders: ["webgpu"] });
          sessionBackend = "WebGPU";
        } catch { session = null; }
      }
      if (!session) {
        session = await ort.InferenceSession.create(bytes, { executionProviders: ["wasm"] });
        sessionBackend = "WebAssembly (CPU)";
      }
      setModelStatus(`Loaded from ${from}, SHA-256 verified. Running on ${sessionBackend}.`, "pass");
      return { ort, session };
    })().catch((error) => {
      sessionPromise = null;
      el.progress.hidden = true;
      throw error;
    });
  }
  return sessionPromise;
}

// ---------- Decode ----------
async function sniffFormat(blob) {
  const b = new Uint8Array(await blob.slice(0, 12).arrayBuffer());
  const ascii = (from, to) => String.fromCharCode(...b.slice(from, to));
  if (b[0] === 0x89 && ascii(1, 4) === "PNG") return "PNG";
  if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "JPEG";
  if (ascii(0, 2) === "BM") return "BMP";
  if (ascii(0, 4) === "RIFF" && ascii(8, 12) === "WEBP") return "WEBP";
  if ((ascii(0, 2) === "II" && b[2] === 42) || (ascii(0, 2) === "MM" && b[3] === 42)) return "TIFF";
  return null;
}

async function decode(blob) {
  const format = await sniffFormat(blob);
  if (!format) throw new Error("This file is not a PNG, JPEG, BMP, TIFF or WebP image.");
  let bitmap;
  try {
    bitmap = await createImageBitmap(blob, { imageOrientation: "from-image", colorSpaceConversion: "none", premultiplyAlpha: "none" });
  } catch {
    throw new Error(format === "TIFF" ? "This browser cannot open TIFF files. Save the photo as PNG or JPEG." : "The image could not be opened.");
  }
  if (bitmap.width * bitmap.height > MAX_PIXELS) {
    bitmap.close();
    throw new Error("The image is larger than 50 megapixels.");
  }
  const c = new OffscreenCanvas(bitmap.width, bitmap.height);
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(bitmap, 0, 0);
  const rgba = ctx.getImageData(0, 0, bitmap.width, bitmap.height).data;
  return { bitmap, rgb: rgbaToRgb(rgba, bitmap.width, bitmap.height), width: bitmap.width, height: bitmap.height };
}

// ---------- Pipeline ----------
// Let the status text paint. rAF never fires in a hidden tab, so a timer stands in.
const nextFrame = () => new Promise((r) => {
  let done = false;
  const go = () => { if (!done) { done = true; r(); } };
  requestAnimationFrame(() => setTimeout(go, 0));
  setTimeout(go, 50);
});

// ORT sessions refuse overlapping runs, so a new photo waits for the previous one to stop.
let inferenceLock = Promise.resolve();
function segment(rgb, w, h, id) {
  const job = inferenceLock.then(() => segmentNow(rgb, w, h, id));
  inferenceLock = job.catch(() => {});
  return job;
}

async function segmentNow(rgb, w, h, id) {
  const { ort, session } = await getSession();
  if (id !== runId) return null;
  const started = performance.now();
  const r512 = pilResizeBilinear(rgb, w, h, SIZE, SIZE);
  const batch = buildTtaBatch(r512);
  const plane = SIZE * SIZE;
  const logits = new Float32Array(4 * plane);
  const inputName = session.inputNames[0];
  const outputName = session.outputNames[0];
  for (let v = 0; v < 4; v++) {
    setOutcome(`Accepted. Segmenting: view ${v + 1} of 4…`, "pass");
    await nextFrame();
    const input = new ort.Tensor("float32", batch.slice(v * 3 * plane, (v + 1) * 3 * plane), [1, 3, SIZE, SIZE]);
    const out = await session.run({ [inputName]: input });
    logits.set(await out[outputName].getData(), v * plane);
    out[outputName].dispose?.();
    if (id !== runId) return null;
  }
  const prob = upsampleBilinear(meanOfTtaViews(logits), SIZE, SIZE, w, h);
  const result = postprocess(prob, w, h);
  return { result, ms: performance.now() - started };
}

async function analyse(blob, name) {
  const id = ++runId;
  clearMeasures();
  el.fileName.textContent = name;
  el.fileName.hidden = false;
  el.readings.hidden = true;
  renderStrip(PADS.map(() => "none"));
  setOutcome("Reading the photo…");
  await nextFrame();

  let decoded;
  try {
    decoded = await decode(blob);
  } catch (error) {
    if (id !== runId) return;
    renderStrip(PADS.map((_, i) => (i === 0 ? "fail" : "none")), true);
    setOutcome(`Refused: ${error.message} No measurement.`, "reject");
    el.stage.hidden = true; el.controls.hidden = true; el.empty.hidden = false;
    return { status: "REJECTED", reasons: ["UNREADABLE"] };
  }
  if (id !== runId) return;
  const { bitmap, rgb, width: w, height: h } = decoded;
  showStage(bitmap);
  bitmap.close();

  const measures = measureQuality(rgb, w, h);
  const verdict = decide(measures);
  renderStrip(PADS.map((p, i) => (i === 0 ? "pass" : verdict.reasons.includes(p.code) ? "fail" : "pass")), true);
  renderReadings(measures, verdict.reasons);
  if (verdict.status === "REJECTED") {
    const names = PADS.filter((p) => verdict.reasons.includes(p.code)).map((p) => p.label.toLowerCase());
    setOutcome(`Refused: failed ${names.join(", ")}. No measurement. Retake the photo and try again.`, "reject");
    return { status: verdict.status, reasons: verdict.reasons, measures };
  }

  setOutcome("Accepted. Loading the model…", "pass");
  let seg;
  try {
    seg = await segment(rgb, w, h, id);
  } catch (error) {
    if (id !== runId) return;
    setModelStatus(error.message || "The model could not start.", "failure");
    setOutcome("Accepted, but the model could not run. Nothing was measured. Reload to try again.", "failure");
    return { status: "ACCEPTED", error: String(error) };
  }
  if (!seg || id !== runId) return;
  const { result, ms } = seg;
  drawMask(result.mask, w, h);
  lastMask = { mask: result.mask, w, h };
  renderMeasures(result, w, h, ms);
  setOutcome(result.area_px ? "Accepted and measured." : "Accepted and measured. No region reached the 0.40 threshold.", "pass");
  const { mask, ...numbers } = result;
  return { status: "ACCEPTED", reasons: [], measures, backend: sessionBackend, ...numbers };
}

// ---------- Inputs ----------
el.file.addEventListener("change", () => {
  const f = el.file.files?.[0];
  if (f) analyse(f, f.name);
  el.file.value = "";
});

for (const type of ["dragenter", "dragover"]) {
  el.drop.addEventListener(type, (e) => { e.preventDefault(); el.drop.classList.add("dragging"); });
}
for (const type of ["dragleave", "drop"]) {
  el.drop.addEventListener(type, () => el.drop.classList.remove("dragging"));
}
el.drop.addEventListener("drop", (e) => {
  e.preventDefault();
  const f = e.dataTransfer?.files?.[0];
  if (f) analyse(f, f.name);
});

// A synthetic sample drawn by the page: skin-like tones and an irregular red patch. Not a photo of anyone.
function seeded(seed) {
  return () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 2 ** 32; };
}
async function syntheticSample() {
  const w = 720, h = 540;
  const c = new OffscreenCanvas(w, h);
  const ctx = c.getContext("2d");
  const g = ctx.createLinearGradient(0, 0, w, h);
  g.addColorStop(0, "#c99a7e"); g.addColorStop(0.6, "#b98568"); g.addColorStop(1, "#8f6550");
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  const rand = seeded(1402);
  ctx.beginPath();
  const cx = 380, cy = 280;
  for (let a = 0; a <= 64; a++) {
    const t = (a / 64) * Math.PI * 2;
    const r = 1 + 0.18 * Math.sin(3 * t + 0.5) + 0.08 * Math.sin(7 * t);
    const x = cx + Math.cos(t) * 110 * r, y = cy + Math.sin(t) * 75 * r;
    a ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  }
  ctx.closePath();
  ctx.lineWidth = 18; ctx.strokeStyle = "#c8a45a"; ctx.stroke();
  const rg = ctx.createRadialGradient(cx, cy, 10, cx, cy, 120);
  rg.addColorStop(0, "#8c1f24"); rg.addColorStop(1, "#b5403a");
  ctx.fillStyle = rg; ctx.fill();
  const img = ctx.getImageData(0, 0, w, h);
  for (let i = 0; i < img.data.length; i += 4) {
    const n = (rand() - 0.5) * 26;
    img.data[i] += n; img.data[i + 1] += n; img.data[i + 2] += n;
  }
  ctx.putImageData(img, 0, 0);
  return c.convertToBlob({ type: "image/png" });
}
el.sample.addEventListener("click", async () => {
  analyse(await syntheticSample(), "synthetic-sample.png (drawn by this page, not a photo)");
});

renderStrip(PADS.map(() => "none"));
// For the parity check against the Python pipeline.
window.dfuDemo = { analyse, syntheticSample };
