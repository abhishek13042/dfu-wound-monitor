"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Trend } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";

interface TipProps {
  active?: boolean;
  payload?: { payload: Trend["rows"][number] }[];
  unit: string;
}

function Tip({ active, payload, unit }: TipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="panel px-3 py-2 text-13 shadow-menu">
      <p className="font-medium">{formatDate(row.captured_at)}</p>
      <p className="text-ink-2">Day {row.days_since_baseline}{row.is_baseline ? ", baseline" : ""}</p>
      <p className="value mt-1">{formatNumber(row.values.area, 1)} {unit}</p>
      {row.mask_source === "CORRECTED" && <p className="text-ink-2">From a corrected outline</p>}
    </div>
  );
}

export function TrendChart({ trend }: { trend: Trend }) {
  const last = trend.rows.at(-1)?.days_since_baseline ?? 0;
  const baseline = Date.parse(trend.rows[0].captured_at);
  const tick = { fill: "var(--muted-foreground)", fontSize: 12, fontFamily: "var(--font-spline-mono)" };
  const stroke = trend.basis === "PHYSICALLY_CALIBRATED" ? "var(--series)" : "var(--muted-foreground)";
  // Only for placing the excluded markers on the time axis; no plotted value is computed here.
  const excluded = trend.excluded
    .filter((item) => item.captured_at)
    .map((item) => Math.round((Date.parse(item.captured_at!) - baseline) / 86_400_000));
  const days = [...trend.rows.map((row) => row.days_since_baseline), ...excluded].sort((a, b) => a - b);
  const peak = Math.max(...trend.rows.map((row) => row.values.area));
  const step = 10 ** Math.floor(Math.log10(peak));
  const top = Math.ceil(peak / step) * step;
  const levels = Array.from({ length: top / step + 1 }, (_, index) => index * step);
  return (
    <div role="img" aria-label="Line chart of area by days since baseline. The table below holds the same values." className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={trend.rows} margin={{ top: 20, right: 16, bottom: 20, left: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            type="number"
            dataKey="days_since_baseline"
            domain={[0, last]}
            ticks={days}
            tick={tick}
            tickLine={false}
            axisLine={{ stroke: "var(--rule-strong)" }}
            label={{ value: "Days since baseline", position: "insideBottom", offset: -12, fill: "var(--muted-foreground)", fontSize: 12 }}
          />
          <YAxis
            dataKey="values.area"
            domain={[0, top]}
            ticks={levels}
            width={64}
            tick={tick}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => formatNumber(value, 0)}
            label={{ value: trend.unit.area, position: "top", offset: 8, fill: "var(--muted-foreground)", fontSize: 12 }}
          />
          {excluded.map((day) => (
            <ReferenceLine
              key={day}
              x={day}
              stroke="var(--reject)"
              strokeDasharray="4 4"
              label={{ value: "Excluded", position: "insideBottomLeft", fill: "var(--muted-foreground)", fontSize: 12 }}
            />
          ))}
          <Tooltip content={<Tip unit={trend.unit.area} />} cursor={{ stroke: "var(--rule-strong)" }} isAnimationActive={false} />
          <Line
            type="linear"
            dataKey="values.area"
            stroke={stroke}
            strokeWidth={2}
            dot={{ r: 4, fill: stroke, stroke: "var(--panel)", strokeWidth: 2 }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
