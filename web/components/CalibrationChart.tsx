"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CalibrationBin } from "@/lib/api";
import { int, pct } from "@/lib/format";

const C = {
  raw: "var(--color-aux)",
  cal: "var(--color-team-a)",
  grid: "var(--color-border)",
  axis: "var(--color-axis)",
  muted: "var(--color-muted)",
  surface: "var(--color-surface)",
};
type Pt = CalibrationBin & { series: string };

/**
 * 신뢰도 곡선(reliability diagram). 예측 확률을 10% 구간으로 묶어
 * x = 구간의 평균 예측 확률, y = 그 구간에서 Team A가 실제로 이긴 비율을 찍는다.
 * 대각선에 붙을수록 '70%라고 말한 라운드는 실제로 70% 이긴다' — 확률을 숫자 그대로 믿어도 된다는 뜻이다.
 * 보정 전(LightGBM 원출력)과 보정 후(isotonic)를 겹쳐 보정이 무엇을 고쳤는지 보여 준다.
 */
export default function CalibrationChart({ raw, calibrated }: { raw: CalibrationBin[]; calibrated: CalibrationBin[] }) {
  const r: Pt[] = raw.map((b) => ({ ...b, series: "보정 전" }));
  const c: Pt[] = calibrated.map((b) => ({ ...b, series: "보정 후" }));
  return (
    <div className="aspect-square max-h-[26rem] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart margin={{ top: 8, right: 12, bottom: 18, left: 0 }}>
          <CartesianGrid stroke={C.grid} />
          <XAxis
            dataKey="mean_predicted"
            type="number"
            domain={[0, 1]}
            ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fill: C.muted, fontSize: 11 }}
            stroke={C.axis}
            tickLine={false}
            label={{ value: "예측 확률", position: "insideBottom", offset: -12, fill: C.muted, fontSize: 11 }}
          />
          <YAxis
            dataKey="observed_rate"
            type="number"
            domain={[0, 1]}
            ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fill: C.muted, fontSize: 11 }}
            stroke={C.axis}
            tickLine={false}
            axisLine={false}
            label={{ value: "실제 승률", angle: -90, position: "insideLeft", offset: 14, fill: C.muted, fontSize: 11 }}
          />
          <ReferenceLine
            segment={[
              { x: 0, y: 0 },
              { x: 1, y: 1 },
            ]}
            stroke={C.muted}
            strokeDasharray="3 3"
          />
          <Tooltip content={<BinTip />} cursor={false} isAnimationActive={false} />
          <Line data={r} dataKey="observed_rate" name="보정 전" stroke={C.raw} strokeWidth={2}
            dot={{ r: 4, fill: C.raw, stroke: C.surface, strokeWidth: 2 }} activeDot={{ r: 6 }} isAnimationActive={false} />
          <Line data={c} dataKey="observed_rate" name="보정 후" stroke={C.cal} strokeWidth={2}
            dot={{ r: 4, fill: C.cal, stroke: C.surface, strokeWidth: 2 }} activeDot={{ r: 6 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function BinTip({ active, payload }: { active?: boolean; payload?: { payload: Pt }[] }) {
  if (!active || !payload?.length) return null;
  const b = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-raised px-3 py-2 text-xs text-secondary shadow-lg shadow-black/40">
      <div className="mb-1 font-semibold text-text">
        {b.series} · 예측 {pct(b.bin_lower, 0)}–{pct(b.bin_upper, 0)} 구간
      </div>
      <div>
        평균 예측 <span className="tabular text-text">{pct(b.mean_predicted)}</span> → 실제 승률{" "}
        <span className="tabular text-text">{pct(b.observed_rate)}</span>
      </div>
      <div>{int(b.count)}라운드</div>
    </div>
  );
}

export function CalibrationLegend() {
  const item = (color: string, label: string) => (
    <span className="flex items-center gap-1.5">
      <svg width="22" height="10" aria-hidden>
        <line x1="0" y1="5" x2="22" y2="5" stroke={color} strokeWidth="2" />
        <circle cx="11" cy="5" r="3.5" fill={color} />
      </svg>
      {label}
    </span>
  );
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-secondary">
      {item(C.cal, "보정 후 (서비스 모델)")}
      {item(C.raw, "보정 전 (LightGBM 원출력)")}
      <span className="flex items-center gap-1.5">
        <svg width="22" height="10" aria-hidden>
          <line x1="0" y1="5" x2="22" y2="5" stroke={C.muted} strokeWidth="1.5" strokeDasharray="3 3" />
        </svg>
        완벽한 보정
      </span>
    </div>
  );
}

export function CalibrationTable({ raw, calibrated }: { raw: CalibrationBin[]; calibrated: CalibrationBin[] }) {
  const rows = [...raw.map((b) => ({ ...b, s: "보정 전" })), ...calibrated.map((b) => ({ ...b, s: "보정 후" }))];
  return (
    <div className="max-h-[26rem] overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-surface text-xs text-muted">
          <tr className="border-b border-border">
            <th className="py-1.5 text-left font-normal">모델</th>
            <th className="py-1.5 text-left font-normal">구간</th>
            <th className="py-1.5 text-right font-normal">평균 예측</th>
            <th className="py-1.5 text-right font-normal">실제 승률</th>
            <th className="py-1.5 text-right font-normal">라운드</th>
          </tr>
        </thead>
        <tbody className="tabular">
          {rows.map((b) => (
            <tr key={`${b.s}${b.bin_lower}`} className="border-b border-border/60">
              <td className="py-1.5 text-secondary">{b.s}</td>
              <td className="py-1.5 text-secondary">
                {pct(b.bin_lower, 0)}–{pct(b.bin_upper, 0)}
              </td>
              <td className="py-1.5 text-right">{pct(b.mean_predicted)}</td>
              <td className="py-1.5 text-right">{pct(b.observed_rate)}</td>
              <td className="py-1.5 text-right text-secondary">{int(b.count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
