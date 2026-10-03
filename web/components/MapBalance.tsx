"use client";

import type { MapBalance as MapBalanceRow } from "@/lib/api";
import { int, pct } from "@/lib/format";
import { useHoverTip } from "@/components/HoverTip";

/**
 * 맵별 공격 진영 승률을 50% 기준선에서 얼마나 벗어나는지로 그린다.
 * 47% vs 51%를 0~100% 축에 그리면 막대 길이가 거의 같아 보인다. 이 차트의 질문은 '어느 쪽으로 기울었나'라서
 * 50%를 0점으로 놓고 편차(%p)를 그린다. 방향은 위치(왼쪽 수비 / 오른쪽 공격)로 표현하고 색은 한 가지만 쓴다.
 * 진영은 승리 방식에서 추정한 값이라 진영을 모르는 라운드(약 0.7%)는 분모에서 뺀다.
 */
export default function MapBalance({ rows }: { rows: MapBalanceRow[] }) {
  const { ref, bind, layer } = useHoverTip();
  const valid = rows.filter((r) => r.attacker_win_rate !== null) as (MapBalanceRow & { attacker_win_rate: number })[];
  const sorted = [...valid].sort((a, b) => b.attacker_win_rate - a.attacker_win_rate);
  // 축 범위: 가장 큰 편차를 2%p 단위로 올림. 최소 ±4%p로 두어 편차가 작은 시즌에서 미세한 차이가 과장되지 않게 한다.
  const maxDev = Math.max(...sorted.map((r) => Math.abs(r.attacker_win_rate - 0.5) * 100), 0);
  const range = Math.max(4, Math.ceil(maxDev / 2) * 2);

  return (
    <div ref={ref} className="relative">
      <div className="mb-1 grid grid-cols-[5.5rem_1fr_1fr_3.5rem] text-[11px] text-muted sm:grid-cols-[7rem_1fr_1fr_4rem]">
        <span />
        <span className="pr-2 text-right">← 수비 유리</span>
        <span className="pl-2">공격 유리 →</span>
        <span />
      </div>
      <ul>
        {sorted.map((r) => {
          const dev = (r.attacker_win_rate - 0.5) * 100;
          const w = (Math.min(Math.abs(dev), range) / range) * 100;
          return (
            <li
              key={r.map_name}
              tabIndex={0}
              aria-label={`${r.map_name}: 공격 승률 ${pct(r.attacker_win_rate)}`}
              className="grid grid-cols-[5.5rem_1fr_1fr_3.5rem] items-center rounded py-[5px] text-sm outline-none hover:bg-raised/60 focus-visible:bg-raised sm:grid-cols-[7rem_1fr_1fr_4rem]"
              {...bind(
                <span>
                  <span className="font-semibold text-text">{r.map_name}</span> · 공격 승률 {pct(r.attacker_win_rate)} ·
                  진영 판별 {int(r.side_known_rounds)}라운드 · {int(r.map_games)}맵 · 맵당 평균 {r.avg_rounds_per_map}라운드
                </span>,
              )}
            >
              <span className="truncate pl-1 text-secondary">{r.map_name}</span>
              <span className="flex h-3.5 justify-end border-r border-axis">
                {dev < 0 && <span className="h-full rounded-l bg-aux" style={{ width: `${w}%` }} />}
              </span>
              <span className="flex h-3.5">{dev > 0 && <span className="h-full rounded-r bg-aux" style={{ width: `${w}%` }} />}</span>
              <span className="text-right text-xs text-secondary tabular">{pct(r.attacker_win_rate)}</span>
            </li>
          );
        })}
      </ul>
      <div className="mt-1 grid grid-cols-[5.5rem_1fr_1fr_3.5rem] text-[10px] text-muted tabular sm:grid-cols-[7rem_1fr_1fr_4rem]">
        <span />
        <span className="flex justify-between">
          <span>{50 - range}%</span>
          <span />
        </span>
        <span className="flex justify-between">
          <span className="-ml-3">50%</span>
          <span>{50 + range}%</span>
        </span>
        <span />
      </div>
      {layer}
    </div>
  );
}

export function MapBalanceTable({ rows }: { rows: MapBalanceRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-muted">
          <tr className="border-b border-border">
            <th className="py-1.5 text-left font-normal">맵</th>
            <th className="py-1.5 text-right font-normal">공격 승률</th>
            <th className="py-1.5 text-right font-normal">진영 판별 라운드</th>
            <th className="py-1.5 text-right font-normal">맵 수</th>
            <th className="py-1.5 text-right font-normal">맵당 평균 라운드</th>
          </tr>
        </thead>
        <tbody className="tabular">
          {rows.map((r) => (
            <tr key={r.map_name} className="border-b border-border/60">
              <td className="py-1.5 text-secondary">{r.map_name}</td>
              <td className="py-1.5 text-right">{pct(r.attacker_win_rate)}</td>
              <td className="py-1.5 text-right text-secondary">{int(r.side_known_rounds)}</td>
              <td className="py-1.5 text-right text-secondary">{int(r.map_games)}</td>
              <td className="py-1.5 text-right text-secondary">{r.avg_rounds_per_map}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
