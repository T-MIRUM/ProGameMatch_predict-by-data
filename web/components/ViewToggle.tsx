"use client";

/** 차트 ↔ 표 전환. 색만으로 값을 읽기 어려운 사용자(색약·스크린리더)를 위해 모든 차트에 표 보기를 둔다. */
export default function ViewToggle({
  value,
  onChange,
  chartLabel = "차트",
}: {
  value: "chart" | "table";
  onChange: (v: "chart" | "table") => void;
  chartLabel?: string;
}) {
  return (
    <div role="radiogroup" aria-label="보기 방식" className="flex rounded-md border border-border p-0.5 text-xs">
      {([["chart", chartLabel], ["table", "표"]] as const).map(([v, l]) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={value === v}
          onClick={() => onChange(v)}
          className={`rounded px-2.5 py-1 ${value === v ? "bg-raised font-semibold text-text" : "text-muted hover:text-secondary"}`}
        >
          {l}
        </button>
      ))}
    </div>
  );
}
