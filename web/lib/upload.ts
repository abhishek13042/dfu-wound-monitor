// The same limits the service enforces on verify (REQ-P08-S02-001); the browser check only saves a round trip.
const TYPES: Record<string, string[]> = {
  png: ["image/png"],
  jpg: ["image/jpeg"],
  jpeg: ["image/jpeg"],
  bmp: ["image/bmp", "image/x-ms-bmp"],
  tif: ["image/tiff"],
  tiff: ["image/tiff"],
  webp: ["image/webp"],
};

export const UPLOAD_LIMIT = 25 * 1024 * 1024;

export function problemWith(file: { name: string; size: number; type: string }): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const types = TYPES[extension];
  if (!types || (file.type && !types.includes(file.type))) return `${file.name} is not a PNG, JPEG, BMP, TIFF or WebP file.`;
  if (file.size === 0) return `${file.name} is empty.`;
  if (file.size > UPLOAD_LIMIT) return `${file.name} is larger than 25 MB.`;
  return null;
}
