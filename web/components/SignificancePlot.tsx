"use client";

import type { Significance } from "@/lib/api";
import { signed } from "@/lib/format";
import { useHoverTip } from "@/components/HoverTip";

/**
 * 룩업표 대비 Brier 차이와 95% 신뢰구간(점 + 수염).
 * 라운드는 같은 경기 안에서 서로 독립이 아니라서(같은 팀·같은 흐름), 라운드 단위로 리샘플하면 구간이 실제보다 좁아진다.
 * 그래서 '경기' 단위로 부트스트랩했다. 구간 전체가 0보다 왼쪽이면 룩업표보다 낫다고 말할 수 있다.
 */
// 모바일에서는 이름·판정을 한 줄에, 구간 그림을 그 아래 전체 폭으로 둔다(세 열로 두면 그림 폭이 거의 남지 않는다)
export default function SignificancePlot({ rows }: { rows: { label: string; s: Significance }[] }) {
  const { ref, bind, layer } = useHoverTip();
  const ext = Math.max(...rows.flatMap((r) => [Math.abs(r.s.ci_low), Math.abs(r.s.ci_high)]), 1e-4) * 1.15;
  const x = (v: number) => ((v + ext) / (2 * ext)) * 100;

  return (
    <div ref={ref} className="relative">
      <div className="mb-1 grid grid-cols-1 text-[11px] text-muted sm:grid-cols-[11rem_1fr_6rem]">
        <span className="hidden sm:block" />
        <span className="flex justify-between whitespace-nowrap px-1">
          <span>← 룩업표보다 좋음</span>
          <span>나쁨 →</span>
        </span>
        <span className="hidden sm:block" />
      </div>
      <ul>
        {rows.map(({ label, s }) => {
          const sig = s.ci_high < 0 || s.ci_low > 0;
          return (
            <li
              key={label}
              tabIndex={0}
              aria-label={`${label}: 차이 ${signed(s.diff, 4)}, 95% 구간 ${signed(s.ci_low, 4)}에서 ${signed(s.ci_high, 4)}`}
              className="grid grid-cols-[1fr_auto] items-center gap-y-1 rounded py-2 text-sm outline-none hover:bg-raised/60 focus-visible:bg-raised sm:grid-cols-[11rem_1fr_6rem]"
              {...bind(
                <span>
                  <span className="font-semibold text-text">{label}</span> · Brier 차이 {signed(s.diff, 4)} · 95% CI [
                  {signed(s.ci_low, 4)}, {signed(s.ci_high, 4)}] · {s.n_groups}경기 리샘플
                </span>,
              )}
            >
              <span className="order-1 truncate pl-1 text-secondary">{label}</span>
              <span className="relative order-3 col-span-2 h-4 sm:order-2 sm:col-span-1">
                <span className="absolute inset-y-0 w-px bg-muted" style={{ left: `${x(0)}%` }} aria-hidden />
                <span
                  className="absolute top-1/2 h-0.5 -translate-y-1/2 rounded bg-secondary"
                  style={{ left: `${x(s.ci_low)}%`, width: `${x(s.ci_high) - x(s.ci_low)}%` }}
                  aria-hidden
                />
                <span
                  className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-text"
                  style={{ left: `${x(s.diff)}%` }}
                  aria-hidden
                />
              </span>
              <span className={`order-2 pr-1 text-right text-xs sm:order-3 ${sig ? "text-text" : "text-muted"}`}>{sig ? "유의함" : "차이 불확실"}</span>
            </li>
          );
        })}
      </ul>
      <div className="mt-1 grid grid-cols-1 text-[10px] text-muted tabular sm:grid-cols-[11rem_1fr_6rem]">
        <span className="hidden sm:block" />
        <span className="relative h-3">
          <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: `${x(0)}%` }}>
            0 (룩업과 같음)
          </span>
        </span>
        <span className="hidden sm:block" />
      </div>
      {layer}
    </div>
  );
}
