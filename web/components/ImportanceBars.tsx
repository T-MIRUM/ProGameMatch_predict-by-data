"use client";

import { useHoverTip } from "@/components/HoverTip";

type Item = { feature: string; label: string; mean_abs_shap: number };

/**
 * 전역 피처 중요도 = 평가 데이터에서 |SHAP|의 평균.
 * 분할 횟수(split count) 중요도는 값의 종류가 많은 연속형 피처를 과대평가하므로,
 * 실제로 예측을 얼마나 움직였는지를 재는 SHAP을 쓴다. 계열이 하나라 색은 한 가지, 값은 막대 옆에 적는다.
 */
export default function ImportanceBars({ items, top = 12 }: { items: Item[]; top?: number }) {
  const { ref, bind, layer } = useHoverTip();
  const shown = items.slice(0, top);
  const max = Math.max(...shown.map((i) => i.mean_abs_shap), 1e-6);
  return (
    <div ref={ref} className="relative">
      <ul className="space-y-[2px]">
        {shown.map((i) => (
          <li
            key={i.feature}
            tabIndex={0}
            className="grid grid-cols-[8rem_1fr_3.5rem] items-center rounded py-1 text-sm outline-none hover:bg-raised/60 focus-visible:bg-raised sm:grid-cols-[10rem_1fr_4rem]"
            {...bind(
              <span>
                <span className="font-semibold text-text">{i.label}</span> ({i.feature}) · 평균 |SHAP| {i.mean_abs_shap.toFixed(4)}
              </span>,
            )}
          >
            <span className="truncate pl-1 text-secondary">{i.label}</span>
            <span className="flex h-3.5">
              <span className="h-full rounded-r bg-secondary" style={{ width: `${(i.mean_abs_shap / max) * 100}%` }} />
            </span>
            <span className="text-right text-xs text-secondary tabular">{i.mean_abs_shap.toFixed(3)}</span>
          </li>
        ))}
      </ul>
      {items.length > top && <p className="mt-2 text-[11px] text-muted">상위 {top}개만 표시 (전체 {items.length}개).</p>}
      {layer}
    </div>
  );
}
