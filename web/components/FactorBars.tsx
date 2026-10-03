import type { Factor } from "@/lib/api";
import { signed } from "@/lib/format";

/**
 * 예측 요인(TreeSHAP 기여도) 발산 막대.
 * 0을 기준으로 오른쪽(+)은 Team A 쪽으로, 왼쪽(−)은 Team B 쪽으로 확률을 민 요인이다.
 * 막대 5개뿐이라 값을 모두 적어도 읽기 부담이 없고, 툴팁 없이도 모든 값이 보인다.
 */
export default function FactorBars({ factors }: { factors: Factor[] }) {
  const max = Math.max(...factors.map((f) => Math.abs(f.contribution)), 1e-6);
  return (
    <div>
      <div className="mb-2 grid grid-cols-[8rem_1fr_1fr_3.5rem] text-[11px] text-muted">
        <span />
        <span className="text-right pr-2">← Team B 쪽</span>
        <span className="pl-2">Team A 쪽 →</span>
        <span />
      </div>
      <ul className="space-y-2">
        {factors.map((f) => {
          const w = (Math.abs(f.contribution) / max) * 100;
          const pos = f.contribution >= 0;
          return (
            <li key={f.feature} className="grid grid-cols-[8rem_1fr_1fr_3.5rem] items-center text-sm">
              <span className="truncate text-secondary" title={f.feature}>
                {f.label}
              </span>
              <span className="flex h-3 justify-end border-r border-axis pr-px">
                {!pos && <span className="h-full rounded-l bg-team-b" style={{ width: `${w}%` }} />}
              </span>
              <span className="flex h-3 pl-px">
                {pos && <span className="h-full rounded-r bg-team-a" style={{ width: `${w}%` }} />}
              </span>
              <span className="text-right text-xs text-secondary tabular">{signed(f.contribution, 2)}</span>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[11px] text-muted">단위: 로그오즈(TreeSHAP). 크기는 보정 전 모델 기준의 상대적 영향력입니다.</p>
    </div>
  );
}
