"use client";

import { BUY_LABELS, BUY_TYPES, type BuyType } from "@/lib/api";
import { credits as fmtCredits } from "@/lib/format";

/**
 * 한 팀의 이코노미 입력: 구매 유형 버튼 + 장비 가치 슬라이더 + 잔여 크레딧 슬라이더.
 *
 * 구매 유형은 원본 데이터에서 장비 가치 구간으로 정해진다(Eco = 0~5k …, DB 기준 99~100% 일치).
 * 두 입력이 따로 놀면 'Full buy인데 장비 3,000' 같은 불가능한 상태가 생기므로 서로 연동한다:
 * - 버튼을 누르면 장비 가치를 그 유형의 실제 중앙값으로 옮긴다.
 * - 슬라이더를 움직이면 해당 구간의 버튼이 선택된다.
 * 장비 가치를 '모름'으로 두면(2026 데이터처럼) 구매 유형만으로 예측한다.
 */
export type TeamEcon = { buy: BuyType; loadout: number | null; credits: number };

export const LOADOUT_MEDIAN: Record<BuyType, number> = {
  "Eco: 0-5k": 3600,
  "Semi-eco: 5-10k": 8100,
  "Semi-buy: 10-20k": 16700,
  "Full buy: 20k+": 23000,
};
const MAX_LOADOUT = 40000;
const MAX_CREDITS = 45000;

export function buyFromLoadout(v: number): BuyType {
  if (v < 5000) return "Eco: 0-5k";
  if (v < 10000) return "Semi-eco: 5-10k";
  if (v < 20000) return "Semi-buy: 10-20k";
  return "Full buy: 20k+";
}

export default function TeamEconomy({
  team,
  value,
  onChange,
}: {
  team: "a" | "b";
  value: TeamEcon;
  onChange: (v: TeamEcon) => void;
}) {
  const name = team === "a" ? "Team A" : "Team B";
  const swatch = team === "a" ? "bg-team-a" : "bg-team-b";
  const known = value.loadout !== null;
  return (
    <fieldset className="space-y-3">
      <legend className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <span className={`inline-block h-2.5 w-2.5 rounded-sm ${swatch}`} aria-hidden />
        {name}
      </legend>

      <div role="radiogroup" aria-label={`${name} 구매 유형`} className="grid grid-cols-4 gap-1">
        {BUY_TYPES.map((bt) => {
          const on = value.buy === bt;
          return (
            <button
              key={bt}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange({ ...value, buy: bt, loadout: known ? LOADOUT_MEDIAN[bt] : null })}
              className={`rounded-md border px-1 py-1.5 text-xs transition-colors ${
                on ? "border-secondary bg-raised font-semibold text-text" : "border-border text-secondary hover:bg-raised/60"
              }`}
            >
              {BUY_LABELS[bt]}
            </button>
          );
        })}
      </div>

      <label className="block text-xs text-muted">
        <span className="flex justify-between">
          <span>장비 가치</span>
          <span className="flex items-center gap-2">
            <span className="text-secondary tabular">{fmtCredits(value.loadout)}</span>
            <span className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={!known}
                onChange={(e) =>
                  onChange({ ...value, loadout: e.target.checked ? null : LOADOUT_MEDIAN[value.buy] })
                }
              />
              모름
            </span>
          </span>
        </span>
        <input
          type="range"
          className={`mt-1 w-full ${team === "b" ? "team-b" : ""}`}
          min={0}
          max={MAX_LOADOUT}
          step={100}
          disabled={!known}
          value={value.loadout ?? LOADOUT_MEDIAN[value.buy]}
          onChange={(e) => {
            const v = Number(e.target.value);
            onChange({ ...value, loadout: v, buy: buyFromLoadout(v) });
          }}
          aria-label={`${name} 장비 가치`}
        />
      </label>

      <label className="block text-xs text-muted">
        <span className="flex justify-between">
          <span>잔여 크레딧 (팀 합계)</span>
          <span className="text-secondary tabular">{fmtCredits(value.credits)}</span>
        </span>
        <input
          type="range"
          className={`mt-1 w-full ${team === "b" ? "team-b" : ""}`}
          min={0}
          max={MAX_CREDITS}
          step={100}
          value={value.credits}
          onChange={(e) => onChange({ ...value, credits: Number(e.target.value) })}
          aria-label={`${name} 잔여 크레딧`}
        />
      </label>
    </fieldset>
  );
}
