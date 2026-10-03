import type { ReactNode } from "react";

/** 핵심 숫자 하나를 크게 보여 주는 타일. 차트로 그릴 필요가 없는 단일 값은 이쪽이 더 빨리 읽힌다. */
export default function StatTile({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-4 py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular">{value}</div>
      {note && <div className="mt-1 text-[11px] leading-snug text-muted">{note}</div>}
    </div>
  );
}
