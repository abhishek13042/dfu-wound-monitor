import type { Measurement } from "@/lib/api";
import { basisCopy } from "@/lib/copy";
import { formatNumber } from "@/lib/format";

export function Measurements({ measurement, model }: { measurement: Measurement; model: string }) {
  const { pixel, physical } = measurement;
  const rows: [string, string, string][] = physical
    ? [
        ["Area", formatNumber(physical.area_mm2), "mm²"],
        ["Perimeter", formatNumber(physical.perimeter_mm), "mm"],
        ["Maximum Feret", formatNumber(physical.max_feret_mm), "mm"],
        ["Minimum Feret", formatNumber(physical.min_feret_mm), "mm"],
      ]
    : [
        ["Area", formatNumber(pixel.area_px, 0), "px²"],
        ["Perimeter", formatNumber(pixel.perimeter_px, 0), "px"],
        ["Maximum Feret", formatNumber(pixel.max_feret_px, 0), "px"],
        ["Minimum Feret", formatNumber(pixel.min_feret_px, 0), "px"],
      ];
  rows.push(["Separate regions", String(pixel.component_count), "count"]);
  return (
    <section aria-labelledby="measurements" className="panel">
      <h2 id="measurements" className="px-4 pt-3 text-lg">Measurements</h2>
      <p className="px-4 pb-2 text-13 text-ink-2">
        {basisCopy[measurement.measurement_basis].long}. Model <span className="value">{model}</span>
      </p>
      <table className="w-full border-collapse">
        <caption className="sr-only">Measured values of the segmented region</caption>
        <thead className="sr-only">
          <tr>
            <th scope="col">Measure</th>
            <th scope="col">Value</th>
            <th scope="col">Unit</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, value, unit]) => (
            <tr key={label} className="h-11 border-t border-rule">
              <th scope="row" className="px-4 text-left text-sm font-normal">{label}</th>
              <td className="value text-right text-lg">{value}</td>
              <td className="value w-16 px-4 text-left text-13 text-ink-2">{unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
