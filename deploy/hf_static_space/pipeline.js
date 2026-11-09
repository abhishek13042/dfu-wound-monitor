// Browser port of the DFU Wound Monitor pipeline: the P03-S02 quality gate and the
// SPEC-02-03 segmentation post-processing. Pure functions over typed arrays, so the
// same file runs in the page and in Node for the parity check against Python.
//
// Sources it mirrors:
//   src/quality/measures.py, src/quality/gate.py, configs/quality/quality_gate_v1.json
//   src/segmentation/dataset.py (preprocess_image), src/segmentation/inference.py

export const QUALITY = {
  version: "p03-s02-v1",
  analysisSize: 512,
  checks: {
    min_side_px: 128,
    max_aspect_ratio: 4.0,
    min_laplacian_variance: 8.0,
    min_mean_luminance: 30,
    max_mean_luminance: 220,
    max_dark_fraction: 0.7,
    max_bright_fraction: 0.5,
    min_luminance_std: 10,
    max_glare_fraction: 0.4,
    min_content_fraction: 0.3,
    min_entropy_bits: 3.0,
  },
};

export const MODEL = {
  version: "spec-02-03-resnet34-unet-512-onnx-v1",
  inputSize: 512,
  mean: [0.485, 0.456, 0.406],
  std: [0.229, 0.224, 0.225],
  threshold: 0.4,
  minComponentArea: 128,
};

// Python's round(): halves go to the even neighbour.
export function roundHalfEven(x) {
  const f = Math.floor(x);
  const d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

// Drop alpha: RGBA (canvas ImageData) -> packed RGB.
export function rgbaToRgb(rgba, w, h) {
  const out = new Uint8Array(w * h * 3);
  for (let i = 0, j = 0; i < w * h; i++, j += 3) {
    out[j] = rgba[i * 4];
    out[j + 1] = rgba[i * 4 + 1];
    out[j + 2] = rgba[i * 4 + 2];
  }
  return out;
}

// Pillow's 8-bit BILINEAR resample (libImaging/Resample.c): a triangle filter whose
// support widens when shrinking, fixed-point weights, horizontal pass then vertical,
// each pass rounded to uint8.
const PRECISION_BITS = 32 - 8 - 2;
const ONE = 2 ** PRECISION_BITS;
const HALF = 2 ** (PRECISION_BITS - 1);

function coefficients(inSize, outSize) {
  const scale = inSize / outSize;
  const filterscale = Math.max(scale, 1);
  const support = 1 * filterscale;
  const ksize = Math.ceil(support) * 2 + 1;
  const bounds = new Int32Array(outSize * 2);
  const kk = new Float64Array(outSize * ksize);
  for (let xx = 0; xx < outSize; xx++) {
    const center = (xx + 0.5) * scale;
    const ss = 1 / filterscale;
    let xmin = Math.trunc(center - support + 0.5);
    if (xmin < 0) xmin = 0;
    let xmax = Math.trunc(center + support + 0.5);
    if (xmax > inSize) xmax = inSize;
    xmax -= xmin;
    let ww = 0;
    const row = new Float64Array(xmax);
    for (let x = 0; x < xmax; x++) {
      const t = Math.abs((x + xmin - center + 0.5) * ss);
      const w = t < 1 ? 1 - t : 0;
      row[x] = w;
      ww += w;
    }
    for (let x = 0; x < xmax; x++) {
      const k = ww !== 0 ? row[x] / ww : row[x];
      kk[xx * ksize + x] = k < 0 ? Math.trunc(-0.5 + k * ONE) : Math.trunc(0.5 + k * ONE);
    }
    bounds[xx * 2] = xmin;
    bounds[xx * 2 + 1] = xmax;
  }
  return { bounds, kk, ksize };
}

const clip8 = (ss) => {
  const v = Math.floor(ss / ONE);
  return v < 0 ? 0 : v > 255 ? 255 : v;
};

export function pilResizeBilinear(rgb, w, h, ow, oh) {
  if (ow === w && oh === h) return rgb.slice();
  let src = rgb;
  let sw = w;
  let sh = h;
  if (ow !== w) {
    const { bounds, kk, ksize } = coefficients(w, ow);
    const out = new Uint8Array(ow * sh * 3);
    for (let y = 0; y < sh; y++) {
      for (let xx = 0; xx < ow; xx++) {
        const xmin = bounds[xx * 2];
        const xmax = bounds[xx * 2 + 1];
        let s0 = HALF, s1 = HALF, s2 = HALF;
        for (let x = 0; x < xmax; x++) {
          const k = kk[xx * ksize + x];
          const p = (y * sw + x + xmin) * 3;
          s0 += src[p] * k;
          s1 += src[p + 1] * k;
          s2 += src[p + 2] * k;
        }
        const o = (y * ow + xx) * 3;
        out[o] = clip8(s0);
        out[o + 1] = clip8(s1);
        out[o + 2] = clip8(s2);
      }
    }
    src = out;
    sw = ow;
  }
  if (oh !== sh) {
    const { bounds, kk, ksize } = coefficients(sh, oh);
    const out = new Uint8Array(sw * oh * 3);
    for (let yy = 0; yy < oh; yy++) {
      const ymin = bounds[yy * 2];
      const ymax = bounds[yy * 2 + 1];
      for (let x = 0; x < sw; x++) {
        let s0 = HALF, s1 = HALF, s2 = HALF;
        for (let y = 0; y < ymax; y++) {
          const k = kk[yy * ksize + y];
          const p = ((y + ymin) * sw + x) * 3;
          s0 += src[p] * k;
          s1 += src[p + 1] * k;
          s2 += src[p + 2] * k;
        }
        const o = (yy * sw + x) * 3;
        out[o] = clip8(s0);
        out[o + 1] = clip8(s1);
        out[o + 2] = clip8(s2);
      }
    }
    src = out;
    sh = oh;
  }
  return src;
}

// Label connected components of a binary mask. connectivity 4 or 8.
export function labelComponents(mask, w, h, connectivity) {
  const labels = new Int32Array(w * h);
  const sizes = [0];
  const stack = new Int32Array(w * h);
  let next = 0;
  for (let start = 0; start < w * h; start++) {
    if (!mask[start] || labels[start]) continue;
    next++;
    let top = 0;
    let size = 0;
    stack[top++] = start;
    labels[start] = next;
    while (top) {
      const p = stack[--top];
      size++;
      const x = p % w;
      const y = (p - x) / w;
      for (let dy = -1; dy <= 1; dy++) {
        const ny = y + dy;
        if (ny < 0 || ny >= h) continue;
        for (let dx = -1; dx <= 1; dx++) {
          if (!dx && !dy) continue;
          if (connectivity === 4 && dx && dy) continue;
          const nx = x + dx;
          if (nx < 0 || nx >= w) continue;
          const q = ny * w + nx;
          if (mask[q] && !labels[q]) {
            labels[q] = next;
            stack[top++] = q;
          }
        }
      }
    }
    sizes.push(size);
  }
  return { labels, sizes, count: next };
}

function erode(mask, w, h) {
  // scipy binary_erosion with the default cross structure; outside the frame counts as 0.
  const out = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const p = y * w + x;
      out[p] = mask[p] && x > 0 && x < w - 1 && y > 0 && y < h - 1 &&
        mask[p - 1] && mask[p + 1] && mask[p - w] && mask[p + w] ? 1 : 0;
    }
  }
  return out;
}

// src/quality/measures.py measure_quality, on an RGB image at its decoded size.
export function measureQuality(rgb, width, height, analysisSize = QUALITY.analysisSize) {
  let w = width;
  let h = height;
  let img = rgb;
  const scale = analysisSize / Math.max(width, height);
  if (scale < 1) {
    w = Math.max(1, roundHalfEven(width * scale));
    h = Math.max(1, roundHalfEven(height * scale));
    img = pilResizeBilinear(rgb, width, height, w, h);
  }
  const n = w * h;
  const lum = new Float32Array(n);
  const black = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const r = img[i * 3], g = img[i * 3 + 1], b = img[i * 3 + 2];
    lum[i] = Math.fround(Math.fround(Math.fround(r * Math.fround(0.299)) + Math.fround(g * Math.fround(0.587))) +
      Math.fround(b * Math.fround(0.114)));
    black[i] = Math.max(r, g, b) <= 2 ? 1 : 0;
  }
  // Padding: exact-black regions that touch the frame border (scipy default 4-connectivity).
  const content = new Uint8Array(n).fill(1);
  const { labels, count } = labelComponents(black, w, h, 4);
  if (count) {
    const border = new Set();
    for (let x = 0; x < w; x++) { border.add(labels[x]); border.add(labels[(h - 1) * w + x]); }
    for (let y = 0; y < h; y++) { border.add(labels[y * w]); border.add(labels[y * w + w - 1]); }
    border.delete(0);
    for (let i = 0; i < n; i++) if (border.has(labels[i])) content[i] = 0;
  }
  let contentCount = 0;
  for (let i = 0; i < n; i++) contentCount += content[i];
  const contentFraction = contentCount / n;
  const m = { width, height, content_fraction: contentFraction };
  if (contentCount < 16) {
    return { ...m, laplacian_variance: 0, mean_luminance: 0, luminance_std: 0, dark_fraction: 1,
      bright_fraction: 0, glare_fraction: 0, entropy: 0 };
  }
  let interior = contentFraction < 1 ? erode(erode(content, w, h), w, h) : content;
  let interiorCount = 0;
  for (let i = 0; i < n; i++) interiorCount += interior[i];
  if (interiorCount < 16) { interior = content; interiorCount = contentCount; }

  // 4-neighbour Laplacian, mode="nearest" (edge pixels repeat).
  let lapSum = 0;
  const lap = new Float64Array(n);
  for (let y = 0; y < h; y++) {
    const yu = y > 0 ? y - 1 : 0, yd = y < h - 1 ? y + 1 : h - 1;
    for (let x = 0; x < w; x++) {
      const p = y * w + x;
      if (!interior[p]) continue;
      const xl = x > 0 ? x - 1 : 0, xr = x < w - 1 ? x + 1 : w - 1;
      const v = lum[yu * w + x] + lum[yd * w + x] + lum[y * w + xl] + lum[y * w + xr] - 4 * lum[p];
      lap[p] = v;
      lapSum += v;
    }
  }
  const lapMean = lapSum / interiorCount;
  let lapVar = 0;
  for (let i = 0; i < n; i++) if (interior[i]) lapVar += (lap[i] - lapMean) ** 2;
  lapVar /= interiorCount;

  let sum = 0, dark = 0, bright = 0, glare = 0;
  const hist = new Float64Array(64);
  for (let i = 0; i < n; i++) {
    if (!content[i]) continue;
    const v = lum[i];
    sum += v;
    if (v < 16) dark++;
    if (v > 239) bright++;
    const r = img[i * 3], g = img[i * 3 + 1], b = img[i * 3 + 2];
    const lo = Math.min(r, g, b), hi = Math.max(r, g, b);
    if (lo >= 235 && hi - lo <= 25) glare++;
    hist[Math.min(63, Math.floor(v / 4))]++;
  }
  const mean = sum / contentCount;
  let sq = 0;
  for (let i = 0; i < n; i++) if (content[i]) sq += (lum[i] - mean) ** 2;
  let entropy = 0;
  for (const c of hist) if (c > 0) { const p = c / contentCount; entropy -= p * Math.log2(p); }
  return {
    ...m,
    laplacian_variance: lapVar,
    mean_luminance: mean,
    luminance_std: Math.sqrt(sq / contentCount),
    dark_fraction: dark / contentCount,
    bright_fraction: bright / contentCount,
    glare_fraction: glare / contentCount,
    entropy,
  };
}

// The nine pads of the reading strip, in DESIGN.md order. Each names the reason code it reads.
export const PADS = [
  { key: "decode", label: "Decode", code: "UNREADABLE" },
  { key: "size", label: "Size", code: "TOO_SMALL" },
  { key: "aspect", label: "Aspect", code: "BAD_ASPECT_RATIO" },
  { key: "content", label: "Content", code: "INSUFFICIENT_CONTENT" },
  { key: "sharpness", label: "Sharpness", code: "BLURRY" },
  { key: "under", label: "Underexposure", code: "UNDEREXPOSED" },
  { key: "over", label: "Overexposure", code: "OVEREXPOSED" },
  { key: "contrast", label: "Contrast", code: "LOW_CONTRAST" },
  { key: "glare", label: "Glare", code: "GLARE" },
];

// src/quality/gate.py QualityGate._decide. A value exactly at a threshold passes.
export function decide(m, c = QUALITY.checks) {
  const reasons = [];
  const short = Math.min(m.width, m.height);
  const long = Math.max(m.width, m.height);
  if (short < c.min_side_px) reasons.push("TOO_SMALL");
  if (long / Math.max(short, 1) > c.max_aspect_ratio) reasons.push("BAD_ASPECT_RATIO");
  if (m.content_fraction < c.min_content_fraction || m.entropy < c.min_entropy_bits) reasons.push("INSUFFICIENT_CONTENT");
  if (m.laplacian_variance < c.min_laplacian_variance) reasons.push("BLURRY");
  if (m.mean_luminance < c.min_mean_luminance || m.dark_fraction > c.max_dark_fraction) reasons.push("UNDEREXPOSED");
  if (m.mean_luminance > c.max_mean_luminance || m.bright_fraction > c.max_bright_fraction) reasons.push("OVEREXPOSED");
  if (m.luminance_std < c.min_luminance_std) reasons.push("LOW_CONTRAST");
  if (m.glare_fraction > c.max_glare_fraction) reasons.push("GLARE");
  return { status: reasons.length ? "REJECTED" : "ACCEPTED", reasons };
}

// One NCHW float32 batch holding the four TTA views: identity, flip W, flip H, flip both.
export function buildTtaBatch(rgb512, size = MODEL.inputSize) {
  const plane = size * size;
  const batch = new Float32Array(4 * 3 * plane);
  const mean = MODEL.mean.map(Math.fround);
  const std = MODEL.std.map(Math.fround);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const p = (y * size + x) * 3;
      for (let c = 0; c < 3; c++) {
        const v = Math.fround(Math.fround(Math.fround(rgb512[p + c] / 255) - mean[c]) / std[c]);
        const fx = size - 1 - x, fy = size - 1 - y;
        batch[(0 * 3 + c) * plane + y * size + x] = v;
        batch[(1 * 3 + c) * plane + y * size + fx] = v;
        batch[(2 * 3 + c) * plane + fy * size + x] = v;
        batch[(3 * 3 + c) * plane + fy * size + fx] = v;
      }
    }
  }
  return batch;
}

const sigmoid = (z) => Math.fround(1 / (1 + Math.exp(-z)));

// Logits (4,1,S,S) -> mean probability (S,S), each view flipped back, summed in order.
export function meanOfTtaViews(logits, size = MODEL.inputSize) {
  const plane = size * size;
  const out = new Float32Array(plane);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const fx = size - 1 - x, fy = size - 1 - y;
      let t = sigmoid(logits[y * size + x]);
      t = Math.fround(t + sigmoid(logits[plane + y * size + fx]));
      t = Math.fround(t + sigmoid(logits[2 * plane + fy * size + x]));
      t = Math.fround(t + sigmoid(logits[3 * plane + fy * size + fx]));
      out[y * size + x] = Math.fround(t / 4);
    }
  }
  return out;
}

// torch F.interpolate(mode="bilinear", align_corners=False), then clamp to [0, 1].
export function upsampleBilinear(src, sw, sh, ow, oh) {
  const out = new Float32Array(ow * oh);
  const sx = sw / ow, sy = sh / oh;
  const xi0 = new Int32Array(ow), xi1 = new Int32Array(ow), xl = new Float32Array(ow);
  for (let x = 0; x < ow; x++) {
    let r = Math.max((x + 0.5) * sx - 0.5, 0);
    const i0 = Math.floor(r);
    xi0[x] = i0;
    xi1[x] = i0 < sw - 1 ? i0 + 1 : i0;
    xl[x] = r - i0;
  }
  for (let y = 0; y < oh; y++) {
    const r = Math.max((y + 0.5) * sy - 0.5, 0);
    const y0 = Math.floor(r);
    const y1 = y0 < sh - 1 ? y0 + 1 : y0;
    const ly = r - y0;
    for (let x = 0; x < ow; x++) {
      const a = src[y0 * sw + xi0[x]], b = src[y0 * sw + xi1[x]];
      const c = src[y1 * sw + xi0[x]], d = src[y1 * sw + xi1[x]];
      const top = a + (b - a) * xl[x];
      const bot = c + (d - c) * xl[x];
      const v = top + (bot - top) * ly;
      out[y * ow + x] = v < 0 ? 0 : v > 1 ? 1 : v;
    }
  }
  return out;
}

// Threshold, drop 8-connected regions under min area, and measure what is left in pixels.
export function postprocess(prob, w, h, threshold = MODEL.threshold, minArea = MODEL.minComponentArea) {
  const n = w * h;
  const raw = new Uint8Array(n);
  for (let i = 0; i < n; i++) raw[i] = prob[i] >= threshold ? 1 : 0;
  const { labels, sizes } = labelComponents(raw, w, h, 8);
  const mask = new Uint8Array(n);
  let area = 0, probSum = 0, regions = 0, dropped = 0;
  let x0 = w, y0 = h, x1 = -1, y1 = -1;
  for (let k = 1; k < sizes.length; k++) (sizes[k] >= minArea ? regions++ : dropped++);
  for (let i = 0; i < n; i++) {
    const l = labels[i];
    if (!l || sizes[l] < minArea) continue;
    mask[i] = 1;
    area++;
    probSum += prob[i];
    const x = i % w, y = (i - x) / w;
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  return {
    mask,
    area_px: area,
    area_fraction: area / n,
    regions,
    dropped_regions: dropped,
    mean_probability: area ? probSum / area : null,
    bbox: area ? [x0, y0, x1, y1] : null,
    bbox_width_px: area ? x1 - x0 + 1 : 0,
    bbox_height_px: area ? y1 - y0 + 1 : 0,
  };
}
