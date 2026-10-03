import type { MatchSummary } from "@/lib/api";

/**
 * 경기 목록. 이코노미 기록이 없는 경기(대부분 2021년 초)는 예측선을 그릴 수 없어서
 * 숨기지 않고 '예측 없음'으로 표시한다 — 데이터가 없는 이유를 사용자가 알 수 있게.
 */
export default function MatchList({
  matches,
  selected,
  onSelect,
}: {
  matches: MatchSummary[];
  selected: number | null;
  onSelect: (id: number) => void;
}) {
  if (!matches.length) return <p className="px-1 py-4 text-sm text-muted">조건에 맞는 경기가 없습니다.</p>;
  return (
    <ul className="space-y-1" aria-label="경기 목록">
      {matches.map((m) => {
        const active = m.match_id === selected;
        const aWon = (m.score_a ?? 0) > (m.score_b ?? 0);
        return (
          <li key={m.match_id}>
            <button
              type="button"
              aria-current={active}
              onClick={() => onSelect(m.match_id)}
              className={`w-full rounded-md border px-3 py-2 text-left ${
                active ? "border-secondary bg-raised" : "border-transparent hover:bg-raised/60"
              }`}
            >
              <div className="truncate text-[11px] text-muted">
                {m.season} · {m.tournament.replace(/^Valorant /, "")} · {m.match_type || m.stage}
              </div>
              <div className="mt-0.5 flex items-center justify-between gap-2 text-sm">
                <span className={`truncate ${aWon ? "font-semibold text-text" : "text-secondary"}`}>{m.team_a}</span>
                <span className="shrink-0 tabular text-secondary">
                  {m.score_a ?? "–"} : {m.score_b ?? "–"}
                </span>
                <span className={`truncate text-right ${!aWon ? "font-semibold text-text" : "text-secondary"}`}>{m.team_b}</span>
              </div>
              {m.economy_rounds === 0 && <div className="mt-0.5 text-[11px] text-muted">이코노미 기록 없음 · 예측 없음</div>}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
