import { BUY_LABELS, type ReplayRound } from "@/lib/api";
import { credits, pct } from "@/lib/format";

/** 리플레이 차트의 표 보기. 차트의 모든 값을 그대로 담고, 이변 라운드는 행 배경으로 표시한다. */
export default function RoundTable({ rounds, teamA, teamB }: { rounds: ReplayRound[]; teamA: string; teamB: string }) {
  // 장비 가치가 없는 시즌(2026 등)은 괄호 없이 구매 유형만 적는다
  const buy = (b: ReplayRound["team_a_buy_type"], l: number | null) =>
    b ? (l === null ? BUY_LABELS[b] : `${BUY_LABELS[b]} (${credits(l)})`) : "–";
  return (
    <div className="max-h-96 overflow-auto">
      <table className="w-full min-w-[42rem] text-sm">
        <thead className="sticky top-0 bg-surface text-xs text-muted">
          <tr className="border-b border-border">
            <th className="w-10 py-1.5 text-left font-normal">R</th>
            <th className="py-1.5 text-left font-normal">시작 스코어</th>
            <th className="py-1.5 text-left font-normal">{teamA} 진영</th>
            <th className="py-1.5 text-left font-normal">{teamA} 구매</th>
            <th className="py-1.5 text-left font-normal">{teamB} 구매</th>
            <th className="py-1.5 text-right font-normal">모델 P(A)</th>
            <th className="py-1.5 text-right font-normal">룩업 P(A)</th>
            <th className="py-1.5 pl-3 text-left font-normal">승리</th>
          </tr>
        </thead>
        <tbody className="tabular">
          {rounds.map((r) => (
            <tr key={r.round_number} className={`border-b border-border/60 ${r.upset ? "bg-raised" : ""}`}>
              <td className="py-1.5 text-secondary">{r.round_number}</td>
              <td className="py-1.5 text-secondary">
                {r.score_a}:{r.score_b}
              </td>
              <td className="py-1.5 text-secondary">{r.team_a_side === "atk" ? "공격" : r.team_a_side === "def" ? "수비" : "모름"}</td>
              <td className="py-1.5 text-secondary">{buy(r.team_a_buy_type, r.team_a_loadout)}</td>
              <td className="py-1.5 text-secondary">{buy(r.team_b_buy_type, r.team_b_loadout)}</td>
              <td className="py-1.5 text-right">{pct(r.win_probability_a)}</td>
              <td className="py-1.5 text-right text-secondary">{pct(r.baseline_probability_a)}</td>
              <td className="py-1.5 pl-3">
                <span className="inline-flex items-center gap-1.5">
                  <span className={`inline-block h-2 w-2 rounded-full ${r.winner === "A" ? "bg-team-a" : "bg-team-b"}`} aria-hidden />
                  {r.winner === "A" ? teamA : teamB}
                  {r.upset && <span className="text-xs font-semibold">이변</span>}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
