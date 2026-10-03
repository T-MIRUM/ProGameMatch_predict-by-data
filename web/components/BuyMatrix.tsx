"use client";

import { BUY_LABELS, type BuyCell, type BuyMatrixResponse } from "@/lib/api";
import { divergingColor } from "@/lib/color";
import { int, pct } from "@/lib/format";
import { useHoverTip } from "@/components/HoverTip";

/** 이 수보다 표본이 적은 칸은 흐린 점선 칸으로 그린다. 30라운드면 승률 표준오차가 약 ±9%p라 색 차이를 믿기 어렵다. */
export const LOW_SAMPLE = 30;

/**
 * 구매 유형 매치업 히트맵 (행 = 우리 팀 구매, 열 = 상대 구매).
 * 칸 색은 '행 팀의 라운드 승률'을 발산 척도로 칠한다. 숫자를 칸 안에 함께 적어 색을 읽지 않아도 값을 알 수 있다.
 */
export default function BuyMatrix({ data }: { data: BuyMatrixResponse }) {
  const { ref, bind, layer } = useHoverTip();
  const cell = (row: string, col: string) => data.cells.find((c) => c.team_buy === row && c.opponent_buy === col);

  return (
    <div ref={ref} className="relative">
      <div className="grid grid-cols-[4.5rem_repeat(4,minmax(0,1fr))] gap-[2px] sm:grid-cols-[6rem_repeat(4,minmax(0,1fr))]">
        <div className="flex items-end pb-1 text-[11px] leading-tight text-muted">
          우리 ↓ / 상대 →
        </div>
        {data.buy_types.map((b) => (
          <div key={b} className="pb-1 text-center text-xs text-secondary">
            {BUY_LABELS[b]}
          </div>
        ))}
        {data.buy_types.map((row) => (
          <Row key={row} row={row} cols={data.buy_types} cell={cell} bind={bind} />
        ))}
      </div>
      {layer}
    </div>
  );
}

function Row({
  row,
  cols,
  cell,
  bind,
}: {
  row: BuyCell["team_buy"];
  cols: BuyCell["opponent_buy"][];
  cell: (r: string, c: string) => BuyCell | undefined;
  bind: ReturnType<typeof useHoverTip>["bind"];
}) {
  return (
    <>
      <div className="flex items-center text-xs text-secondary">{BUY_LABELS[row]}</div>
      {cols.map((col) => {
        const c = cell(row, col);
        const label = `${BUY_LABELS[row]} vs ${BUY_LABELS[col]}`;
        if (!c || c.win_rate === null) {
          return (
            <div
              key={col}
              tabIndex={0}
              aria-label={`${label}: 표본 없음`}
              className="flex h-16 items-center justify-center rounded border border-dashed border-axis text-[11px] text-muted sm:h-20"
              {...bind(<span>{label} · 표본 없음</span>)}
            >
              없음
            </div>
          );
        }
        const low = c.count < LOW_SAMPLE;
        return (
          <div
            key={col}
            tabIndex={0}
            aria-label={`${label}: 승률 ${pct(c.win_rate)}, ${int(c.count)}라운드`}
            className="flex h-16 flex-col items-center justify-center rounded outline-offset-2 hover:outline hover:outline-2 hover:outline-text/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-text sm:h-20"
            // 표본이 적으면 칸 채우기만 투명하게 하고 점선 테두리를 둔다. 글자는 그대로 읽혀야 한다.
            style={{
              background: low ? `color-mix(in oklab, ${divergingColor(c.win_rate)} 35%, transparent)` : divergingColor(c.win_rate),
              border: low ? "1px dashed var(--color-axis)" : undefined,
            }}
            {...bind(
              <span>
                <span className="font-semibold text-text">{label}</span> · 승률 {pct(c.win_rate)} · {int(c.count)}라운드
                {low && <span className="text-muted"> · 표본 적음</span>}
              </span>,
            )}
          >
            <span className="text-sm font-semibold text-text tabular sm:text-base">{pct(c.win_rate, 0)}</span>
            <span className="text-[10px] text-text/80 tabular">n={int(c.count)}</span>
          </div>
        );
      })}
    </>
  );
}

/** 발산 척도 범례: 0% — 50% — 100%. 색 띠는 칸과 같은 함수로 만든다. */
export function DivergingLegend() {
  const stops = [0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1].map(divergingColor).join(", ");
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-muted">
      <div className="flex items-center gap-2">
        <span>0%</span>
        <span className="h-2.5 w-40 rounded-sm" style={{ background: `linear-gradient(to right, ${stops})` }} aria-hidden />
        <span>100%</span>
        <span className="ml-1">(가운데 회색 = 50%)</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-sm border border-dashed border-axis bg-div-pos/35" aria-hidden />
        흐린 점선 칸 = 표본 {LOW_SAMPLE}라운드 미만(색을 믿기 어려움)
      </div>
    </div>
  );
}

export function BuyMatrixTable({ data }: { data: BuyMatrixResponse }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-muted">
          <tr className="border-b border-border">
            <th className="py-1.5 text-left font-normal">우리 팀 구매</th>
            <th className="py-1.5 text-left font-normal">상대 구매</th>
            <th className="py-1.5 text-right font-normal">승률</th>
            <th className="py-1.5 text-right font-normal">라운드 수</th>
          </tr>
        </thead>
        <tbody className="tabular">
          {data.cells.map((c) => (
            <tr key={`${c.team_buy}|${c.opponent_buy}`} className="border-b border-border/60">
              <td className="py-1.5 text-secondary">{BUY_LABELS[c.team_buy]}</td>
              <td className="py-1.5 text-secondary">{BUY_LABELS[c.opponent_buy]}</td>
              <td className="py-1.5 text-right">{pct(c.win_rate)}</td>
              <td className={`py-1.5 text-right ${c.count < LOW_SAMPLE ? "text-muted" : "text-secondary"}`}>{int(c.count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
