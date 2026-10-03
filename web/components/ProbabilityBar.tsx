import { pct } from "@/lib/format";

/**
 * 승률 게이지: 한 줄 막대를 A/B 두 구간으로 나눈다(합 = 100%).
 * 두 구간 사이는 테두리 대신 2px 배경색 틈으로 구분하고, 끝만 4px로 둥글린다.
 * 숫자는 막대 밖에 텍스트 색으로 적는다(팀 색은 막대에만 써서 글자 대비 문제를 피한다).
 */
export function ProbabilityBar({ p, label, height = 14 }: { p: number; label?: string; height?: number }) {
  const a = Math.min(Math.max(p, 0), 1) * 100;
  return (
    <div>
      {label && <div className="mb-1 text-xs text-muted">{label}</div>}
      <div className="flex items-center gap-3">
        <span className="w-14 text-right text-sm font-semibold tabular">{pct(p)}</span>
        <div
          className="flex flex-1 gap-[2px]"
          style={{ height }}
          role="img"
          aria-label={`Team A ${pct(p)}, Team B ${pct(1 - p)}`}
        >
          <div className="rounded-l bg-team-a transition-[width] duration-300" style={{ width: `${a}%` }} />
          <div className="flex-1 rounded-r bg-team-b" />
        </div>
        <span className="w-14 text-sm font-semibold tabular">{pct(1 - p)}</span>
      </div>
    </div>
  );
}

/** 팀 범례: 색은 작은 사각 견본에만, 이름은 텍스트 색으로. */
export function TeamLegend({ a = "Team A", b = "Team B" }: { a?: string; b?: string }) {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-secondary">
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-team-a" aria-hidden />
        {a}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-team-b" aria-hidden />
        {b}
      </span>
    </div>
  );
}
