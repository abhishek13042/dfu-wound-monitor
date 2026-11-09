// Constructed outlines for placeholder images. They are drawn from a seed, not from any photo.
export function seedOf(text: string): number {
  return [...text].reduce((total, char) => (total * 31 + char.charCodeAt(0)) >>> 0, 7);
}

export function outline(seed: number, cx: number, cy: number, rx: number, ry: number, points = 48): [number, number][] {
  const phase = [(seed % 97) / 15, (seed % 89) / 13, (seed % 83) / 11];
  return Array.from({ length: points }, (_, index) => {
    const angle = (index / points) * Math.PI * 2;
    const wobble = 1 + 0.1 * Math.sin(angle * 3 + phase[0]) + 0.06 * Math.sin(angle * 5 + phase[1]) + 0.03 * Math.sin(angle * 9 + phase[2]);
    return [cx + Math.cos(angle) * rx * wobble, cy + Math.sin(angle) * ry * wobble];
  });
}

export function toPath(points: [number, number][]): string {
  return `M${points.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join("L")}Z`;
}
