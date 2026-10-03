"use client";

import { useEffect, useState } from "react";
import Card, { ErrorNote } from "@/components/Card";
import MatchList from "@/components/MatchList";
import ReplayChart, { ReplayLegend } from "@/components/ReplayChart";
import RoundTable from "@/components/RoundTable";
import ViewToggle from "@/components/ViewToggle";
import { query, type MapsResponse, type MatchRoundsResponse, type MatchSummary } from "@/lib/api";
import { pct } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { useDebounce } from "@/lib/useDebounce";

const inputCls = "mt-1 block w-full rounded-md border border-border bg-raised px-2 py-1.5 text-sm text-text";
// 모델은 2021–2023으로 학습, 2024로 조기 종료·확률 보정을 했다. 이 시즌들의 예측은 '본 적 있는 데이터'라 실제보다 좋아 보인다.
const LAST_FIT_SEASON = 2024;

/**
 * 화면 3 — 경기 리플레이.
 * 기본 시즌을 2025(테스트 시즌)로 둔다: 모델이 학습 중 한 번도 보지 않은 경기라 예측선이 정직하다.
 */
export default function ReplayPage() {
  const [season, setSeason] = useState("2025");
  const [team, setTeam] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [mapIdx, setMapIdx] = useState(0);
  const [view, setView] = useState<"chart" | "table">("chart");
  const teamQ = useDebounce(team.trim(), 300);

  const meta = useApi<MapsResponse>("/api/maps");
  const list = useApi<MatchSummary[]>(`/api/matches${query({ season, team: teamQ, limit: 50 })}`);
  const detail = useApi<MatchRoundsResponse>(selected === null ? null : `/api/matches/${selected}/rounds`);

  // 목록이 바뀌었는데 선택한 경기가 목록에 없으면 첫 경기를 자동 선택한다(빈 상세 화면을 피한다)
  useEffect(() => {
    if (list.data && !list.data.some((m) => m.match_id === selected)) setSelected(list.data[0]?.match_id ?? null);
  }, [list.data, selected]);
  useEffect(() => {
    setMapIdx(0);
  }, [selected]);

  const d = detail.data;
  const map = d?.maps[Math.min(mapIdx, (d?.maps.length ?? 1) - 1)];
  const inSample = Number(season) <= LAST_FIT_SEASON && season !== "";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">경기 리플레이</h1>
        <p className="mt-1 text-sm text-muted">
          실제 경기의 라운드마다, 그 라운드가 시작될 때 모델이 계산한 승리 확률과 실제 결과를 나란히 봅니다.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface px-4 py-3">
        <label className="w-36 text-xs text-muted">
          시즌
          <select value={season} onChange={(e) => setSeason(e.target.value)} className={inputCls}>
            <option value="">전체</option>
            {meta.data?.seasons.map((s) => (
              <option key={s} value={s}>
                {s}
                {s > LAST_FIT_SEASON ? " (테스트)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="w-56 text-xs text-muted">
          팀 이름
          <input value={team} onChange={(e) => setTeam(e.target.value)} placeholder="예: FNATIC" className={inputCls} />
        </label>
        {inSample && (
          <p className="max-w-md pb-1 text-[11px] text-muted">
            {season}년은 모델 학습·보정에 쓰인 시즌이라 예측이 실제 성능보다 좋아 보입니다. 정직한 비교는 2025·2026에서 보세요.
          </p>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <Card className="lg:max-h-[46rem] lg:overflow-y-auto" title="경기" subtitle="최근 경기부터, 최대 50개">
          {list.error && <ErrorNote message={list.error} />}
          <div className={`max-h-72 overflow-y-auto lg:max-h-none ${list.loading && list.data ? "opacity-60" : ""}`}>
            {list.data ? (
              <MatchList matches={list.data} selected={selected} onSelect={setSelected} />
            ) : (
              !list.error && <p className="text-sm text-muted">불러오는 중…</p>
            )}
          </div>
        </Card>

        <div className={`space-y-4 transition-opacity ${detail.loading && d ? "opacity-60" : ""}`}>
          {detail.error && <ErrorNote message={detail.error} />}
          {!d ? (
            <Card>
              <p className="text-sm text-muted">{selected === null ? "경기를 선택하세요." : "불러오는 중…"}</p>
            </Card>
          ) : (
            <>
              <Card>
                <div className="text-xs text-muted">
                  {d.match.season} · {d.match.tournament} · {d.match.stage} {d.match.match_type}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-lg font-semibold">
                  <span className="flex items-center gap-2">
                    <span className="inline-block h-3 w-3 rounded-sm bg-team-a" aria-hidden />
                    {d.match.team_a}
                  </span>
                  <span className="tabular text-secondary">
                    {d.match.score_a ?? "–"} : {d.match.score_b ?? "–"}
                  </span>
                  <span className="flex items-center gap-2">
                    {d.match.team_b}
                    <span className="inline-block h-3 w-3 rounded-sm bg-team-b" aria-hidden />
                  </span>
                </div>
                <p className="mt-2 text-xs text-muted">
                  경기 전 팀 강도(이전 경기 누적 라운드 승률, 표본이 적으면 50% 쪽으로 보정): {d.match.team_a}{" "}
                  <span className="tabular text-secondary">{pct(d.team_a_strength)}</span> · {d.match.team_b}{" "}
                  <span className="tabular text-secondary">{pct(d.team_b_strength)}</span>
                </p>
              </Card>

              {map && (
                <Card
                  title={`맵 ${map.map_order ?? mapIdx + 1} · ${map.map_name}`}
                  subtitle={
                    <>
                      맵 스코어 {map.score_a ?? "–"} : {map.score_b ?? "–"} · 이변{" "}
                      {map.rounds.filter((r) => r.upset).length}회
                      {map.rounds.some((r) => r.win_probability_a === null) &&
                        ` · 예측 없는 라운드 ${map.rounds.filter((r) => r.win_probability_a === null).length}개(이코노미 기록 없음)`}
                    </>
                  }
                  actions={<ViewToggle value={view} onChange={setView} />}
                >
                  {d.maps.length > 1 && (
                    <div role="tablist" aria-label="맵 선택" className="mb-4 flex flex-wrap gap-1">
                      {d.maps.map((m, i) => (
                        <button
                          key={m.map_game_id}
                          type="button"
                          role="tab"
                          aria-selected={i === mapIdx}
                          onClick={() => setMapIdx(i)}
                          className={`rounded-md border px-2.5 py-1 text-xs ${
                            i === mapIdx ? "border-secondary bg-raised font-semibold text-text" : "border-border text-secondary hover:bg-raised/60"
                          }`}
                        >
                          {m.map_name} <span className="tabular text-muted">{m.score_a}:{m.score_b}</span>
                        </button>
                      ))}
                    </div>
                  )}
                  {view === "chart" ? (
                    <div className="space-y-3">
                      <ReplayLegend teamA={d.match.team_a} teamB={d.match.team_b} />
                      <ReplayChart rounds={map.rounds} teamA={d.match.team_a} teamB={d.match.team_b} />
                    </div>
                  ) : (
                    <RoundTable rounds={map.rounds} teamA={d.match.team_a} teamB={d.match.team_b} />
                  )}
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
