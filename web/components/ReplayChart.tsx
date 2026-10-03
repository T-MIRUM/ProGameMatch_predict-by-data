"use client";

import type { ReactElement } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BUY_LABELS, type ReplayRound } from "@/lib/api";
import { credits, pct } from "@/lib/format";

type Row = ReplayRound & { p: number | null; base: number | null };
type DotProps = { cx?: number | null; cy?: number | null; payload?: Row; index?: number };

const C = {
  a: "var(--color-team-a)",
  b: "var(--color-team-b)",
  grid: "var(--color-border)",
  axis: "var(--color-axis)",
  muted: "var(--color-muted)",
  secondary: "var(--color-secondary)",
  surface: "var(--color-surface)",
  text: "var(--color-text)",
};

/**
 * 한 맵의 라운드별 Team A 승리 확률(라운드 시작 시점 예측).
 * - 실선 = 모델, 점선 = 구매 유형 룩업표. 둘을 겹쳐 '모델이 룩업보다 무엇을 더 아는가'를 라운드 단위로 보여 준다.
 * - 점 색 = 실제로 그 라운드를 이긴 팀. 50% 기준선 위의 주황 점(또는 아래의 파란 점)이 예측과 반대로 끝난 라운드다.
 * - 흰 테두리의 큰 점 = 이변: 이긴 팀의 예측 확률이 30% 미만이었던 라운드.
 * 이코노미 기록이 없는 라운드는 예측이 없으므로 선을 잇지 않고 끊는다(빈칸을 보간하면 없는 예측을 만든 셈이 된다).
 */
export default function ReplayChart({ rounds, teamA, teamB }: { rounds: ReplayRound[]; teamA: string; teamB: string }) {
  const data: Row[] = rounds.map((r) => ({ ...r, p: r.win_probability_a, base: r.baseline_probability_a }));
  const last = rounds.at(-1)?.round_number ?? 24;

  const dot = (props: DotProps): ReactElement => {
    const { cx, cy, payload, index } = props;
    if (cx == null || cy == null || !payload || payload.p === null) return <g key={`d${index}`} />;
    const fill = payload.winner === "A" ? C.a : C.b;
    return payload.upset ? (
      <circle key={`d${index}`} cx={cx} cy={cy} r={6} fill={fill} stroke={C.text} strokeWidth={2} />
    ) : (
      <circle key={`d${index}`} cx={cx} cy={cy} r={4} fill={fill} stroke={C.surface} strokeWidth={2} />
    );
  };

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis
            dataKey="round_number"
            type="number"
            domain={[1, last]}
            ticks={[...new Set([1, 6, 12, 18, 24, last])].filter((t) => t <= last).sort((a, b) => a - b)}
            tick={{ fill: C.muted, fontSize: 11 }}
            stroke={C.axis}
            tickLine={false}
          />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fill: C.muted, fontSize: 11 }}
            stroke={C.axis}
            tickLine={false}
            axisLine={false}
          />
          <ReferenceLine y={0.5} stroke={C.muted} strokeDasharray="2 3" />
          {/* 전·후반 교대 지점. 진영이 바뀌면 확률이 계단처럼 움직일 수 있어 위치를 표시해 둔다 */}
          <ReferenceLine x={12.5} stroke={C.axis} label={{ value: "후반", fill: C.muted, fontSize: 10, position: "insideTopRight" }} />
          {last > 24 && (
            <ReferenceLine x={24.5} stroke={C.axis} label={{ value: "연장", fill: C.muted, fontSize: 10, position: "insideTopRight" }} />
          )}
          <Tooltip content={<RoundTip teamA={teamA} teamB={teamB} />} cursor={{ stroke: C.axis }} isAnimationActive={false} />
          <Line dataKey="base" stroke={C.secondary} strokeWidth={1.5} strokeDasharray="4 3" dot={false} activeDot={false} connectNulls={false} isAnimationActive={false} />
          <Line dataKey="p" stroke={C.a} strokeWidth={2} dot={dot} activeDot={false} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function RoundTip({
  active,
  payload,
  teamA,
  teamB,
}: {
  active?: boolean;
  payload?: { payload: Row }[];
  teamA: string;
  teamB: string;
}) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  const side = r.team_a_side === "atk" ? "공격" : r.team_a_side === "def" ? "수비" : "모름";
  const buy = (b: Row["team_a_buy_type"]) => (b ? BUY_LABELS[b] : "기록 없음");
  return (
    <div className="rounded-md border border-border bg-raised px-3 py-2 text-xs text-secondary shadow-lg shadow-black/40">
      <div className="mb-1 font-semibold text-text">
        {r.round_number}라운드 · 시작 스코어 {r.score_a}:{r.score_b}
      </div>
      <div>
        {teamA} 진영: {side}
      </div>
      <div>
        {teamA}: {buy(r.team_a_buy_type)} · 장비 {credits(r.team_a_loadout)}
      </div>
      <div>
        {teamB}: {buy(r.team_b_buy_type)} · 장비 {credits(r.team_b_loadout)}
      </div>
      <div className="mt-1">
        모델 P(A) <span className="font-semibold text-text tabular">{pct(r.p)}</span> · 룩업{" "}
        <span className="tabular">{pct(r.base)}</span>
      </div>
      <div className="mt-1 flex items-center gap-1.5">
        <span className={`inline-block h-2 w-2 rounded-full ${r.winner === "A" ? "bg-team-a" : "bg-team-b"}`} aria-hidden />
        실제 승리: {r.winner === "A" ? teamA : teamB}
        {r.upset && <span className="ml-1 font-semibold text-text">· 이변</span>}
      </div>
    </div>
  );
}

/** 범례: 계열이 4개(모델선·룩업선·A 승리 점·B 승리 점)라 항상 표시한다. 색 견본 옆 글자는 텍스트 색. */
export function ReplayLegend({ teamA, teamB }: { teamA: string; teamB: string }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-secondary">
      <span className="flex items-center gap-1.5">
        <svg width="18" height="8" aria-hidden><line x1="0" y1="4" x2="18" y2="4" stroke={C.a} strokeWidth="2" /></svg>
        모델 P({teamA} 승)
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="18" height="8" aria-hidden><line x1="0" y1="4" x2="18" y2="4" stroke={C.secondary} strokeWidth="1.5" strokeDasharray="4 3" /></svg>
        룩업표
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-2 rounded-full bg-team-a" aria-hidden />
        {teamA} 승리
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-2 rounded-full bg-team-b" aria-hidden />
        {teamB} 승리
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-3 w-3 rounded-full border-2 border-text bg-muted" aria-hidden />
        이변 (이긴 팀 예측 30% 미만)
      </span>
    </div>
  );
}
